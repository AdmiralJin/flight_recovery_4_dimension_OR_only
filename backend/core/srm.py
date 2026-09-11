from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from backend.config.costs import FixedColumnCostConfig, schedule_flight_option_cost
from backend.schemas.columns import (
    FlightChangeType,
    FlightOperationType,
    RecoveryColumns,
)
from backend.schemas.model_result import ModelSolveResult
from backend.schemas.scenario import Scenario
from backend.services.column_validator import validate_recovery_columns
from backend.services.validator import validate_scenario
from backend.solver.base import (
    ConstraintSense,
    SolverAdapter,
    VariableHandle,
    VariableType,
)

from .gate_inventory import GateInventoryData, build_gate_inventory_data
from .incidence import RecoveryIncidence, build_recovery_incidence
from .indices import CapacityIntervalKey, RecoveryIndices, build_recovery_indices


SRM_C01_FLIGHT_COVERAGE = "SRM-C01-FLIGHT-COVERAGE"
SRM_C02_STRATEGIC_FLIGHT = "SRM-C02-STRATEGIC-FLIGHT"
SRM_C03_ARRIVAL_CAPACITY = "SRM-C03-ARRIVAL-CAPACITY"
SRM_C04_DEPARTURE_CAPACITY = "SRM-C04-DEPARTURE-CAPACITY"
SRM_C05_GATE_INVENTORY = "SRM-C05-GATE-INVENTORY"
SRM_C06_MARKET_SEAT = "SRM-C06-MARKET-SEAT"

MARKET_SEAT_MODE = "MARKET_SEAT_PROXY"
GATE_INVENTORY_MODE = "PROVISIONAL_AGGREGATE_GATE_INVENTORY"
SRM_MODEL_NAME = "fixed_column_srm"
SRM_FEASIBILITY_TOLERANCE = 1e-6

CONSTRAINT_PROVENANCE = MappingProxyType(
    {
        SRM_C01_FLIGHT_COVERAGE: "paper_defined:(3.2)",
        SRM_C02_STRATEGIC_FLIGHT: (
            "paper_defined:(3.3)+implementation_mapping_assumption:A-028"
        ),
        SRM_C03_ARRIVAL_CAPACITY: "paper_defined:(3.4)",
        SRM_C04_DEPARTURE_CAPACITY: "paper_defined:(3.5)",
        SRM_C05_GATE_INVENTORY: (
            "implementation_assumption:generated_provisional:A-029/A-030"
        ),
        SRM_C06_MARKET_SEAT: ("implementation_assumption:generated_provisional:A-031"),
    }
)


class SrmBuildError(ValueError):
    """Validated inputs cannot be mapped to the Fixed-Column SRM contract."""


@dataclass(frozen=True)
class FixedColumnSrmModel:
    scenario: Scenario
    columns: RecoveryColumns
    indices: RecoveryIndices
    incidence: RecoveryIncidence
    gate_inventory: GateInventoryData
    variables: Mapping[str, VariableHandle]
    option_costs: Mapping[str, float]


def _validation_message(scope: str, issues) -> str:
    details = "; ".join(
        f"{item.code}@{item.location}: {item.message}" for item in issues
    )
    return f"{scope} validation failed: {details}"


def _validated_inputs(
    scenario_data: Any,
    columns_data: Any,
) -> tuple[Scenario, RecoveryColumns]:
    scenario, scenario_issues = validate_scenario(scenario_data)
    if scenario is None or scenario_issues:
        raise SrmBuildError(_validation_message("scenario", scenario_issues))
    columns, column_issues = validate_recovery_columns(scenario, columns_data)
    if columns is None or column_issues:
        raise SrmBuildError(_validation_message("columns", column_issues))
    return scenario, columns


def _capacity_instance(index: int, key: CapacityIntervalKey) -> str:
    return (
        f"{index:03d}:{key.airport}:"
        f"{key.start_time.isoformat()}:{key.end_time.isoformat()}"
    )


def _constraint_name(constraint_id: str, instance: str, side: str = "") -> str:
    suffix = f":{side}" if side else ""
    return f"{constraint_id}[{instance}{suffix}]"


def build_fixed_column_srm(
    scenario: Scenario,
    columns: RecoveryColumns,
    costs: FixedColumnCostConfig,
    solver: SolverAdapter,
) -> FixedColumnSrmModel:
    """Build, but do not solve, the Phase 2.2 Fixed-Column SRM."""

    indices = build_recovery_indices(scenario, columns)
    incidence = build_recovery_incidence(scenario, columns, indices)
    gate_inventory = build_gate_inventory_data(scenario, columns)
    options = {option.option_id: option for option in columns.flight_options}
    flights = {flight.flight_id: flight for flight in scenario.flights}
    srm_option_ids = tuple(
        option.option_id
        for option in columns.flight_options
        if option.operation_type
        in {FlightOperationType.OPERATE, FlightOperationType.CANCEL}
    )

    for flight_id in indices.flights.ids:
        option_ids = tuple(
            option_id
            for option_id in incidence.base_flight_to_options.columns_for_row(flight_id)
            if option_id in srm_option_ids
        )
        if not option_ids:
            raise SrmBuildError(
                f"{SRM_C01_FLIGHT_COVERAGE}: flight {flight_id!r} has no "
                "operate/cancel option"
            )
    for option_id in srm_option_ids:
        base_flight_id = options[option_id].base_flight_id
        if base_flight_id not in flights:
            raise SrmBuildError(
                f"option {option_id!r} references unknown base flight "
                f"{base_flight_id!r}"
            )

    solver.create_model(SRM_MODEL_NAME)
    variables = {
        option_id: solver.add_variable(
            f"x[{option_id}]", variable_type=VariableType.BINARY
        )
        for option_id in srm_option_ids
    }
    option_costs = {
        option_id: schedule_flight_option_cost(scenario, options[option_id], costs)
        for option_id in srm_option_ids
    }
    solver.set_objective(
        {variables[option_id]: cost for option_id, cost in option_costs.items()}
    )

    for flight_id in indices.flights.ids:
        option_ids = tuple(
            option_id
            for option_id in incidence.base_flight_to_options.columns_for_row(flight_id)
            if option_id in variables
        )
        solver.add_linear_constraint(
            {variables[option_id]: 1.0 for option_id in option_ids},
            ConstraintSense.EQUAL,
            1.0,
            name=_constraint_name(SRM_C01_FLIGHT_COVERAGE, flight_id),
        )

    for flight in scenario.flights:
        if not flight.strategic_flag:
            continue
        operated = tuple(
            option_id
            for option_id in incidence.base_flight_to_options.columns_for_row(
                flight.flight_id
            )
            if option_id in variables
            and options[option_id].operation_type is FlightOperationType.OPERATE
        )
        solver.add_linear_constraint(
            {variables[option_id]: 1.0 for option_id in operated},
            ConstraintSense.EQUAL,
            1.0,
            name=_constraint_name(SRM_C02_STRATEGIC_FLIGHT, flight.flight_id),
        )

    for index, (key, interval) in enumerate(
        zip(indices.capacity_intervals.ids, scenario.airport_intervals)
    ):
        instance = _capacity_instance(index, key)
        arrival_options = tuple(
            option_id
            for option_id in incidence.arrival_capacity_to_options.columns_for_row(key)
            if option_id in variables
            and options[option_id].operation_type is FlightOperationType.OPERATE
        )
        departure_options = tuple(
            option_id
            for option_id in incidence.departure_capacity_to_options.columns_for_row(
                key
            )
            if option_id in variables
            and options[option_id].operation_type is FlightOperationType.OPERATE
        )
        solver.add_linear_constraint(
            {variables[option_id]: 1.0 for option_id in arrival_options},
            ConstraintSense.LESS_EQUAL,
            float(interval.arr_capacity),
            name=_constraint_name(SRM_C03_ARRIVAL_CAPACITY, instance),
        )
        solver.add_linear_constraint(
            {variables[option_id]: 1.0 for option_id in departure_options},
            ConstraintSense.LESS_EQUAL,
            float(interval.dep_capacity),
            name=_constraint_name(SRM_C04_DEPARTURE_CAPACITY, instance),
        )

    for checkpoint in gate_inventory.checkpoints:
        coefficients = {
            variables[option_id]: float(coefficient)
            for option_id, coefficient in checkpoint.coefficient_by_option.items()
            if option_id in variables
        }
        solver.add_linear_constraint(
            coefficients,
            ConstraintSense.LESS_EQUAL,
            float(checkpoint.gate_capacity - checkpoint.initial_ground),
            name=_constraint_name(
                SRM_C05_GATE_INVENTORY, checkpoint.checkpoint_id, "upper"
            ),
        )
        solver.add_linear_constraint(
            coefficients,
            ConstraintSense.GREATER_EQUAL,
            float(-checkpoint.initial_ground),
            name=_constraint_name(
                SRM_C05_GATE_INVENTORY, checkpoint.checkpoint_id, "lower"
            ),
        )

    for flight in scenario.flights:
        if not (flight.market_flag and flight.min_seats > 0):
            continue
        operated = tuple(
            option_id
            for option_id in incidence.base_flight_to_options.columns_for_row(
                flight.flight_id
            )
            if option_id in variables
            and options[option_id].operation_type is FlightOperationType.OPERATE
        )
        solver.add_linear_constraint(
            {variables[option_id]: 1.0 for option_id in operated},
            ConstraintSense.GREATER_EQUAL,
            1.0,
            name=_constraint_name(SRM_C06_MARKET_SEAT, flight.flight_id),
        )

    return FixedColumnSrmModel(
        scenario=scenario,
        columns=columns,
        indices=indices,
        incidence=incidence,
        gate_inventory=gate_inventory,
        variables=MappingProxyType(variables),
        option_costs=MappingProxyType(option_costs),
    )


def _check(
    constraint_id: str,
    instance: str,
    lhs: float,
    sense: str,
    rhs: float,
) -> dict[str, Any]:
    if sense == "==":
        slack = -abs(lhs - rhs)
        satisfied = abs(lhs - rhs) <= SRM_FEASIBILITY_TOLERANCE
    elif sense == "<=":
        slack = rhs - lhs
        satisfied = lhs <= rhs + SRM_FEASIBILITY_TOLERANCE
    else:
        slack = lhs - rhs
        satisfied = lhs + SRM_FEASIBILITY_TOLERANCE >= rhs
    return {
        "constraint_id": constraint_id,
        "instance": instance,
        "lhs": lhs,
        "sense": sense,
        "rhs": rhs,
        "slack": slack,
        "satisfied": satisfied,
        "provenance": CONSTRAINT_PROVENANCE[constraint_id],
    }


def _capacity_key_json(key: CapacityIntervalKey) -> dict[str, str]:
    return {
        "airport": key.airport,
        "start_time": key.start_time.isoformat(),
        "end_time": key.end_time.isoformat(),
    }


def recompute_srm_diagnostics(
    model: FixedColumnSrmModel,
    option_values: Mapping[str, float],
    costs: FixedColumnCostConfig,
) -> dict[str, Any]:
    """Independently recalculate every Phase 2.2 SRM constraint and cost."""

    scenario = model.scenario
    columns = model.columns
    incidence = model.incidence
    options = {option.option_id: option for option in columns.flight_options}

    coverage_checks = []
    strategic_checks = []
    arrival_checks = []
    departure_checks = []
    gate_checks = []
    market_checks = []
    selected_option_by_flight: dict[str, str] = {}
    cancelled_flights: list[str] = []
    delay_by_flight: dict[str, int] = {}

    for flight in scenario.flights:
        option_ids = tuple(
            option_id
            for option_id in incidence.base_flight_to_options.columns_for_row(
                flight.flight_id
            )
            if option_id in option_values
        )
        lhs = sum(option_values[option_id] for option_id in option_ids)
        coverage_checks.append(
            _check(
                SRM_C01_FLIGHT_COVERAGE,
                flight.flight_id,
                lhs,
                "==",
                1.0,
            )
        )
        selected = [
            option_id for option_id in option_ids if option_values[option_id] > 0.5
        ]
        if len(selected) == 1:
            selected_id = selected[0]
            selected_option_by_flight[flight.flight_id] = selected_id
            selected_option = options[selected_id]
            if selected_option.operation_type is FlightOperationType.CANCEL:
                cancelled_flights.append(flight.flight_id)
                delay_by_flight[flight.flight_id] = 0
            else:
                delay_by_flight[flight.flight_id] = int(
                    selected_option.departure_delay_minutes or 0
                )
        if flight.strategic_flag:
            operated_lhs = sum(
                option_values[option_id]
                for option_id in option_ids
                if options[option_id].operation_type is FlightOperationType.OPERATE
            )
            strategic_checks.append(
                _check(
                    SRM_C02_STRATEGIC_FLIGHT,
                    flight.flight_id,
                    operated_lhs,
                    "==",
                    1.0,
                )
            )
        if flight.market_flag and flight.min_seats > 0:
            operated_lhs = sum(
                option_values[option_id]
                for option_id in option_ids
                if options[option_id].operation_type is FlightOperationType.OPERATE
            )
            check = _check(
                SRM_C06_MARKET_SEAT,
                flight.flight_id,
                operated_lhs,
                ">=",
                1.0,
            )
            check["mode"] = MARKET_SEAT_MODE
            check["min_seats_preserved_as_metadata"] = flight.min_seats
            market_checks.append(check)

    for index, (key, interval) in enumerate(
        zip(model.indices.capacity_intervals.ids, scenario.airport_intervals)
    ):
        instance = _capacity_instance(index, key)
        arrivals = tuple(
            option_id
            for option_id in incidence.arrival_capacity_to_options.columns_for_row(key)
            if option_id in option_values
            and options[option_id].operation_type is FlightOperationType.OPERATE
        )
        departures = tuple(
            option_id
            for option_id in incidence.departure_capacity_to_options.columns_for_row(
                key
            )
            if option_id in option_values
            and options[option_id].operation_type is FlightOperationType.OPERATE
        )
        arrival_check = _check(
            SRM_C03_ARRIVAL_CAPACITY,
            instance,
            sum(option_values[option_id] for option_id in arrivals),
            "<=",
            float(interval.arr_capacity),
        )
        arrival_check["capacity_interval"] = _capacity_key_json(key)
        arrival_checks.append(arrival_check)
        departure_check = _check(
            SRM_C04_DEPARTURE_CAPACITY,
            instance,
            sum(option_values[option_id] for option_id in departures),
            "<=",
            float(interval.dep_capacity),
        )
        departure_check["capacity_interval"] = _capacity_key_json(key)
        departure_checks.append(departure_check)

    for checkpoint in model.gate_inventory.checkpoints:
        net_change = sum(
            coefficient * option_values.get(option_id, 0.0)
            for option_id, coefficient in checkpoint.coefficient_by_option.items()
        )
        inventory = checkpoint.initial_ground + net_change
        gate_checks.append(
            {
                "constraint_id": SRM_C05_GATE_INVENTORY,
                "instance": checkpoint.checkpoint_id,
                "airport": checkpoint.airport,
                "timestamp": checkpoint.timestamp.isoformat(),
                "inventory": inventory,
                "gate_capacity": checkpoint.gate_capacity,
                "lower_slack": inventory,
                "upper_slack": checkpoint.gate_capacity - inventory,
                "satisfied": (
                    inventory >= -SRM_FEASIBILITY_TOLERANCE
                    and inventory
                    <= checkpoint.gate_capacity + SRM_FEASIBILITY_TOLERANCE
                ),
                "mode": GATE_INVENTORY_MODE,
                "capacity_source_key": _capacity_key_json(
                    checkpoint.capacity_source_key
                ),
                "provenance": CONSTRAINT_PROVENANCE[SRM_C05_GATE_INVENTORY],
            }
        )

    coefficients = costs.coefficients
    objective_breakdown = {
        "flight_delay": sum(
            option_values.get(option.option_id, 0.0)
            * float(option.departure_delay_minutes or 0)
            * float(coefficients.flight_delay_per_minute.value)
            for option in columns.flight_options
            if option.operation_type is FlightOperationType.OPERATE
        ),
        "flight_cancellation": sum(
            option_values.get(option.option_id, 0.0)
            * float(coefficients.flight_cancellation.value)
            for option in columns.flight_options
            if option.operation_type is FlightOperationType.CANCEL
        ),
        "origin_change": sum(
            option_values.get(option.option_id, 0.0)
            * float(coefficients.origin_change.value)
            for option in columns.flight_options
            if FlightChangeType.ORIGIN_CHANGE in option.change_types
        ),
        "destination_change": sum(
            option_values.get(option.option_id, 0.0)
            * float(coefficients.destination_change.value)
            for option in columns.flight_options
            if FlightChangeType.DESTINATION_CHANGE in option.change_types
        ),
    }
    objective_breakdown["total"] = sum(objective_breakdown.values())
    all_checks = (
        coverage_checks
        + strategic_checks
        + arrival_checks
        + departure_checks
        + gate_checks
        + market_checks
    )
    return {
        "model": "SRM",
        "single_model_only": True,
        "constraint_contract": dict(CONSTRAINT_PROVENANCE),
        "gate_constraint_mode": GATE_INVENTORY_MODE,
        "market_constraint_mode": MARKET_SEAT_MODE,
        "selected_option_by_flight": selected_option_by_flight,
        "cancelled_flights": cancelled_flights,
        "flight_delay_minutes": delay_by_flight,
        "total_flight_delay_minutes": sum(delay_by_flight.values()),
        "arrival_capacity_load": arrival_checks,
        "departure_capacity_load": departure_checks,
        "gate_inventory": gate_checks,
        "strategic_constraints": strategic_checks,
        "market_proxy_constraints": market_checks,
        "flight_coverage_constraints": coverage_checks,
        "objective_breakdown": objective_breakdown,
        "all_constraints_satisfied": all(item["satisfied"] for item in all_checks),
        "constraint_violation_count": sum(not item["satisfied"] for item in all_checks),
    }


def solve_fixed_column_srm(
    scenario_data: Any,
    columns_data: Any,
    costs: FixedColumnCostConfig,
    solver: SolverAdapter,
    *,
    solver_parameters: Mapping[str, bool | int | float | str] | None = None,
) -> ModelSolveResult:
    """Validate, build, solve, and independently audit the Fixed-Column SRM."""

    scenario, columns = _validated_inputs(scenario_data, columns_data)
    model = build_fixed_column_srm(scenario, columns, costs, solver)
    outcome = solver.solve(solver_parameters)
    selected_variables: dict[str, float] = {}
    diagnostics: dict[str, Any] = {
        "model": "SRM",
        "single_model_only": True,
        "constraint_contract": dict(CONSTRAINT_PROVENANCE),
        "gate_constraint_mode": GATE_INVENTORY_MODE,
        "market_constraint_mode": MARKET_SEAT_MODE,
        "solver": dict(outcome.diagnostics),
    }

    if outcome.has_solution:
        option_values = {
            option_id: solver.get_variable_value(variable)
            for option_id, variable in model.variables.items()
        }
        selected_variables = {
            model.variables[option_id].name: value
            for option_id, value in option_values.items()
            if value > 0.5
        }
        diagnostics = recompute_srm_diagnostics(model, option_values, costs)
        diagnostics["solver"] = dict(outcome.diagnostics)
        recomputed_objective = diagnostics["objective_breakdown"]["total"]
        if outcome.objective_value is None or not math.isclose(
            recomputed_objective,
            outcome.objective_value,
            rel_tol=SRM_FEASIBILITY_TOLERANCE,
            abs_tol=SRM_FEASIBILITY_TOLERANCE,
        ):
            raise RuntimeError(
                "SRM objective audit differs from Solver outcome: "
                f"audit={recomputed_objective}, solver={outcome.objective_value}"
            )
        if not diagnostics["all_constraints_satisfied"]:
            raise RuntimeError("SRM independent constraint audit found a violation")

    return ModelSolveResult(
        model_name=outcome.model_name,
        scenario_id=scenario.scenario_id,
        status=outcome.status,
        objective_value=outcome.objective_value,
        best_bound=outcome.best_bound,
        mip_gap=outcome.mip_gap,
        runtime_seconds=outcome.runtime_seconds,
        selected_variables=selected_variables,
        continuous_variables={},
        solver_name=solver.solver_name,
        solver_version=solver.solver_version,
        raw_status=outcome.raw_status,
        termination_reason=outcome.termination_reason,
        diagnostics=diagnostics,
    )
