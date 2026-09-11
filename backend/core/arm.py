from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from backend.config.costs import (
    AircraftStringCostBreakdown,
    FixedColumnCostConfig,
    aircraft_string_cost,
)
from backend.schemas.columns import FlightOperationType, RecoveryColumns
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

from .incidence import RecoveryIncidence, build_recovery_incidence
from .indices import RecoveryIndices, build_recovery_indices


ARM_C01_STRING_SELECTION = "ARM-C01-AIRCRAFT-STRING-SELECTION"
ARM_C02_OPTION_COVERAGE = "ARM-C02-FLIGHT-OPTION-COVERAGE"
ARM_C03_TERMINAL_STATION = "ARM-C03-TERMINAL-STATION"
ARM_C04_MAINTENANCE = "ARM-C04-MAINTENANCE"
ARM_C05_STRING_FEASIBILITY = "ARM-C05-STRING-FEASIBILITY"

ARM_MODEL_NAME = "fixed_column_arm"
ARM_FEASIBILITY_TOLERANCE = 1e-6

CONSTRAINT_PROVENANCE = MappingProxyType(
    {
        ARM_C01_STRING_SELECTION: (
            "paper_defined:(3.10)+implementation_mapping_assumption:A-034"
        ),
        ARM_C02_OPTION_COVERAGE: (
            "paper_defined:(3.9)+fixed_option_mapping_assumption:A-035"
        ),
        ARM_C03_TERMINAL_STATION: (
            "paper_prose+implementation_mapping_assumption:A-036"
        ),
        ARM_C04_MAINTENANCE: (
            "paper_defined:(3.11)+fixed_column_flag_assumption:A-037"
        ),
        ARM_C05_STRING_FEASIBILITY: (
            "pre_model_semantic_validation+implementation_assumption:A-036"
        ),
    }
)


class ArmBuildError(ValueError):
    """Validated inputs cannot be mapped to the Fixed-Column ARM contract."""


@dataclass(frozen=True)
class AircraftRecoveryRequest:
    scenario_id: str
    required_operated_option_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.scenario_id:
            raise ValueError("scenario_id must not be empty")
        if isinstance(self.required_operated_option_ids, str):
            raise TypeError("required_operated_option_ids must be an iterable of IDs")
        option_ids = tuple(self.required_operated_option_ids)
        if any(not option_id for option_id in option_ids):
            raise ValueError("required operated option IDs must not be empty")
        if len(option_ids) != len(set(option_ids)):
            raise ValueError("required_operated_option_ids must be unique")
        object.__setattr__(self, "required_operated_option_ids", option_ids)

    @classmethod
    def from_option_ids(
        cls,
        scenario_id: str,
        option_ids: Iterable[str],
    ) -> AircraftRecoveryRequest:
        return cls(scenario_id, tuple(option_ids))


@dataclass(frozen=True)
class FixedColumnArmModel:
    scenario: Scenario
    columns: RecoveryColumns
    request: AircraftRecoveryRequest
    indices: RecoveryIndices
    incidence: RecoveryIncidence
    variables: Mapping[str, VariableHandle]
    string_costs: Mapping[str, AircraftStringCostBreakdown]


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
        raise ArmBuildError(_validation_message("scenario", scenario_issues))
    columns, column_issues = validate_recovery_columns(scenario, columns_data)
    if columns is None or column_issues:
        raise ArmBuildError(_validation_message("columns", column_issues))
    return scenario, columns


def _validate_request(
    scenario: Scenario,
    columns: RecoveryColumns,
    request: AircraftRecoveryRequest,
) -> None:
    if request.scenario_id != scenario.scenario_id:
        raise ArmBuildError(
            "ARM request scenario_id differs from validated Scenario: "
            f"{request.scenario_id!r} != {scenario.scenario_id!r}"
        )

    options = {option.option_id: option for option in columns.flight_options}
    base_flights: dict[str, str] = {}
    for option_id in request.required_operated_option_ids:
        option = options.get(option_id)
        if option is None:
            raise ArmBuildError(f"unknown required operated option: {option_id!r}")
        if (
            option.operation_type is not FlightOperationType.OPERATE
            or option.base_flight_id is None
        ):
            raise ArmBuildError(
                f"required option {option_id!r} is not a revenue operate option"
            )
        previous = base_flights.get(option.base_flight_id)
        if previous is not None:
            raise ArmBuildError(
                "ARM request contains conflicting schedule options for base flight "
                f"{option.base_flight_id!r}: {previous!r}, {option_id!r}"
            )
        base_flights[option.base_flight_id] = option_id


def _constraint_name(constraint_id: str, instance: str) -> str:
    return f"{constraint_id}[{instance}]"


def build_fixed_column_arm(
    scenario: Scenario,
    columns: RecoveryColumns,
    request: AircraftRecoveryRequest,
    costs: FixedColumnCostConfig,
    solver: SolverAdapter,
) -> FixedColumnArmModel:
    """Build, but do not solve, the Phase 2.3 Fixed-Column ARM."""

    _validate_request(scenario, columns, request)
    try:
        indices = build_recovery_indices(scenario, columns)
        incidence = build_recovery_incidence(scenario, columns, indices)
    except (KeyError, ValueError) as exc:
        raise ArmBuildError(f"ARM incidence build failed: {exc}") from exc

    aircraft_by_id = {aircraft.tail_id: aircraft for aircraft in scenario.aircraft}
    strings_by_id = {
        aircraft_string.string_id: aircraft_string
        for aircraft_string in columns.aircraft_strings
    }
    options_by_id = {option.option_id: option for option in columns.flight_options}

    for aircraft_id in indices.aircraft.ids:
        candidate_ids = incidence.aircraft_to_strings.columns_for_row(aircraft_id)
        if not candidate_ids:
            raise ArmBuildError(
                f"{ARM_C01_STRING_SELECTION}: aircraft {aircraft_id!r} has no "
                "explicit candidate string"
            )

    string_costs = {
        string_id: aircraft_string_cost(
            scenario,
            options_by_id,
            strings_by_id[string_id],
            costs,
        )
        for string_id in indices.aircraft_strings.ids
    }

    solver.create_model(ARM_MODEL_NAME)
    variables = {
        string_id: solver.add_variable(
            f"y[{string_id}]", variable_type=VariableType.BINARY
        )
        for string_id in indices.aircraft_strings.ids
    }
    solver.set_objective(
        {
            variables[string_id]: breakdown.total
            for string_id, breakdown in string_costs.items()
        }
    )

    for aircraft_id in indices.aircraft.ids:
        candidate_ids = incidence.aircraft_to_strings.columns_for_row(aircraft_id)
        solver.add_linear_constraint(
            {variables[string_id]: 1.0 for string_id in candidate_ids},
            ConstraintSense.EQUAL,
            1.0,
            name=_constraint_name(ARM_C01_STRING_SELECTION, aircraft_id),
        )

    required = set(request.required_operated_option_ids)
    for option_id in request.required_operated_option_ids:
        covering_strings = incidence.option_to_aircraft_strings.columns_for_row(
            option_id
        )
        solver.add_linear_constraint(
            {variables[string_id]: 1.0 for string_id in covering_strings},
            ConstraintSense.EQUAL,
            1.0,
            name=_constraint_name(ARM_C02_OPTION_COVERAGE, f"required:{option_id}"),
        )
    for option_id in indices.revenue_operate_options.ids:
        if option_id in required:
            continue
        covering_strings = incidence.option_to_aircraft_strings.columns_for_row(
            option_id
        )
        solver.add_linear_constraint(
            {variables[string_id]: 1.0 for string_id in covering_strings},
            ConstraintSense.EQUAL,
            0.0,
            name=_constraint_name(ARM_C02_OPTION_COVERAGE, f"not-required:{option_id}"),
        )

    for aircraft_id in indices.aircraft.ids:
        aircraft = aircraft_by_id[aircraft_id]
        terminal_compatible = tuple(
            string_id
            for string_id in incidence.aircraft_to_strings.columns_for_row(aircraft_id)
            if strings_by_id[string_id].end_station
            == aircraft.required_station_at_T_end
        )
        solver.add_linear_constraint(
            {variables[string_id]: 1.0 for string_id in terminal_compatible},
            ConstraintSense.EQUAL,
            1.0,
            name=_constraint_name(ARM_C03_TERMINAL_STATION, aircraft_id),
        )

    for aircraft_id in indices.maintenance_aircraft.ids:
        maintenance_compatible = incidence.maintenance_to_strings.columns_for_row(
            aircraft_id
        )
        solver.add_linear_constraint(
            {variables[string_id]: 1.0 for string_id in maintenance_compatible},
            ConstraintSense.EQUAL,
            1.0,
            name=_constraint_name(ARM_C04_MAINTENANCE, aircraft_id),
        )

    return FixedColumnArmModel(
        scenario=scenario,
        columns=columns,
        request=request,
        indices=indices,
        incidence=incidence,
        variables=MappingProxyType(variables),
        string_costs=MappingProxyType(string_costs),
    )


def _check(
    constraint_id: str,
    instance: str,
    lhs: float,
    rhs: float,
) -> dict[str, Any]:
    satisfied = abs(lhs - rhs) <= ARM_FEASIBILITY_TOLERANCE
    return {
        "constraint_id": constraint_id,
        "instance": instance,
        "lhs": lhs,
        "sense": "==",
        "rhs": rhs,
        "slack": -abs(lhs - rhs),
        "satisfied": satisfied,
        "provenance": CONSTRAINT_PROVENANCE[constraint_id],
    }


def analyze_arm_fixed_columns(model: FixedColumnArmModel) -> dict[str, Any]:
    """Report schedule-compatible candidate availability before optimization."""

    required = set(model.request.required_operated_option_ids)
    aircraft_by_id = {
        aircraft.tail_id: aircraft for aircraft in model.scenario.aircraft
    }
    strings_by_id = {
        aircraft_string.string_id: aircraft_string
        for aircraft_string in model.columns.aircraft_strings
    }
    options_by_id = {
        option.option_id: option for option in model.columns.flight_options
    }
    eligible_by_aircraft: dict[str, list[str]] = {}
    eligible_string_ids: set[str] = set()
    rejected_for_schedule_leakage: dict[str, list[str]] = {}

    for aircraft_id in model.indices.aircraft.ids:
        aircraft = aircraft_by_id[aircraft_id]
        eligible_by_aircraft[aircraft_id] = []
        for string_id in model.incidence.aircraft_to_strings.columns_for_row(
            aircraft_id
        ):
            aircraft_string = strings_by_id[string_id]
            unexpected = [
                option_id
                for option_id in aircraft_string.leg_option_ids
                if options_by_id[option_id].operation_type
                is FlightOperationType.OPERATE
                and option_id not in required
            ]
            if unexpected:
                rejected_for_schedule_leakage[string_id] = unexpected
                continue
            if aircraft_string.end_station != aircraft.required_station_at_T_end:
                continue
            if aircraft.maintenance_required and string_id not in set(
                model.incidence.maintenance_to_strings.columns_for_row(aircraft_id)
            ):
                continue
            eligible_by_aircraft[aircraft_id].append(string_id)
            eligible_string_ids.add(string_id)

    required_covering_eligible_strings = {
        option_id: [
            string_id
            for string_id in model.incidence.option_to_aircraft_strings.columns_for_row(
                option_id
            )
            if string_id in eligible_string_ids
        ]
        for option_id in model.request.required_operated_option_ids
    }
    return {
        "eligible_string_ids_by_aircraft": eligible_by_aircraft,
        "aircraft_without_schedule_compatible_string": [
            aircraft_id
            for aircraft_id, string_ids in eligible_by_aircraft.items()
            if not string_ids
        ],
        "required_option_covering_eligible_strings": (
            required_covering_eligible_strings
        ),
        "required_options_without_eligible_string": [
            option_id
            for option_id, string_ids in required_covering_eligible_strings.items()
            if not string_ids
        ],
        "strings_rejected_for_schedule_leakage": rejected_for_schedule_leakage,
    }


def recompute_arm_diagnostics(
    model: FixedColumnArmModel,
    string_values: Mapping[str, float],
    costs: FixedColumnCostConfig,
) -> dict[str, Any]:
    """Independently recalculate every Phase 2.3 ARM constraint and cost."""

    scenario = model.scenario
    columns = model.columns
    incidence = model.incidence
    aircraft_by_id = {aircraft.tail_id: aircraft for aircraft in scenario.aircraft}
    strings_by_id = {
        aircraft_string.string_id: aircraft_string
        for aircraft_string in columns.aircraft_strings
    }
    options_by_id = {option.option_id: option for option in columns.flight_options}

    selected_string_by_aircraft: dict[str, str] = {}
    selection_checks = []
    terminal_checks = []
    maintenance_checks = []
    selected_string_ids = {
        string_id for string_id, value in string_values.items() if value > 0.5
    }

    for aircraft_id in model.indices.aircraft.ids:
        candidate_ids = incidence.aircraft_to_strings.columns_for_row(aircraft_id)
        lhs = sum(string_values[string_id] for string_id in candidate_ids)
        selection_checks.append(_check(ARM_C01_STRING_SELECTION, aircraft_id, lhs, 1.0))
        selected = [
            string_id for string_id in candidate_ids if string_id in selected_string_ids
        ]
        if len(selected) == 1:
            selected_string_by_aircraft[aircraft_id] = selected[0]

        aircraft = aircraft_by_id[aircraft_id]
        terminal_lhs = sum(
            string_values[string_id]
            for string_id in candidate_ids
            if strings_by_id[string_id].end_station
            == aircraft.required_station_at_T_end
        )
        terminal_check = _check(
            ARM_C03_TERMINAL_STATION, aircraft_id, terminal_lhs, 1.0
        )
        terminal_check["required_station"] = aircraft.required_station_at_T_end
        terminal_check["selected_string_id"] = (
            selected[0] if len(selected) == 1 else None
        )
        terminal_check["selected_end_station"] = (
            strings_by_id[selected[0]].end_station if len(selected) == 1 else None
        )
        terminal_checks.append(terminal_check)

        if aircraft.maintenance_required:
            compatible = incidence.maintenance_to_strings.columns_for_row(aircraft_id)
            maintenance_lhs = sum(string_values[string_id] for string_id in compatible)
            maintenance_check = _check(
                ARM_C04_MAINTENANCE, aircraft_id, maintenance_lhs, 1.0
            )
            maintenance_check["selected_string_id"] = (
                selected[0] if len(selected) == 1 else None
            )
            maintenance_check["maintenance_satisfied_flag"] = (
                strings_by_id[selected[0]].maintenance_satisfied
                if len(selected) == 1
                else None
            )
            maintenance_check["eligible_stations"] = list(aircraft.maintenance_stations)
            maintenance_checks.append(maintenance_check)

    required_checks = []
    option_coverage: dict[str, float] = {}
    for option_id in model.indices.revenue_operate_options.ids:
        covering = incidence.option_to_aircraft_strings.columns_for_row(option_id)
        option_coverage[option_id] = sum(
            string_values[string_id] for string_id in covering
        )

    required_set = set(model.request.required_operated_option_ids)
    for option_id in model.request.required_operated_option_ids:
        required_checks.append(
            _check(
                ARM_C02_OPTION_COVERAGE,
                f"required:{option_id}",
                option_coverage[option_id],
                1.0,
            )
        )
    leakage_checks = [
        _check(
            ARM_C02_OPTION_COVERAGE,
            f"not-required:{option_id}",
            option_coverage[option_id],
            0.0,
        )
        for option_id in model.indices.revenue_operate_options.ids
        if option_id not in required_set
    ]

    selected_breakdowns = {
        string_id: aircraft_string_cost(
            scenario,
            options_by_id,
            strings_by_id[string_id],
            costs,
        )
        for string_id in selected_string_ids
    }
    ferry_legs = []
    for string_id in model.indices.aircraft_strings.ids:
        if string_id not in selected_string_ids:
            continue
        aircraft_string = strings_by_id[string_id]
        for option_id in aircraft_string.leg_option_ids:
            option = options_by_id[option_id]
            if option.operation_type is FlightOperationType.FERRY:
                ferry_legs.append(
                    {
                        "aircraft_id": aircraft_string.aircraft_id,
                        "string_id": string_id,
                        "option_id": option_id,
                        "minutes": option.block_minutes,
                        "cost": float(option.block_minutes or 0)
                        * float(costs.coefficients.ferry_per_minute.value),
                    }
                )

    objective_breakdown = {
        "aircraft_reassignment": sum(
            item.reassignment_cost for item in selected_breakdowns.values()
        ),
        "ferry": sum(item.ferry_cost for item in selected_breakdowns.values()),
    }
    objective_breakdown["total"] = sum(objective_breakdown.values())
    all_checks = (
        selection_checks
        + required_checks
        + leakage_checks
        + terminal_checks
        + maintenance_checks
    )
    return {
        "model": "ARM",
        "single_model_only": True,
        "constraint_contract": dict(CONSTRAINT_PROVENANCE),
        "paper_variable_domain": "binary:(3.12)",
        "fixed_column_analysis": analyze_arm_fixed_columns(model),
        "required_operated_option_ids": list(
            model.request.required_operated_option_ids
        ),
        "selected_string_by_aircraft": selected_string_by_aircraft,
        "covered_required_options": [
            option_id
            for option_id in model.request.required_operated_option_ids
            if abs(option_coverage[option_id] - 1.0) <= ARM_FEASIBILITY_TOLERANCE
        ],
        "uncovered_required_options": [
            option_id
            for option_id in model.request.required_operated_option_ids
            if option_coverage[option_id] < 1.0 - ARM_FEASIBILITY_TOLERANCE
        ],
        "duplicate_coverage": [
            option_id
            for option_id in model.request.required_operated_option_ids
            if option_coverage[option_id] > 1.0 + ARM_FEASIBILITY_TOLERANCE
        ],
        "unexpected_revenue_options": [
            option_id
            for option_id in model.indices.revenue_operate_options.ids
            if option_id not in required_set
            and option_coverage[option_id] > ARM_FEASIBILITY_TOLERANCE
        ],
        "option_coverage": option_coverage,
        "string_selection_constraints": selection_checks,
        "required_option_constraints": required_checks,
        "schedule_leakage_constraints": leakage_checks,
        "terminal_status": terminal_checks,
        "maintenance_status": maintenance_checks,
        "string_feasibility": {
            "constraint_id": ARM_C05_STRING_FEASIBILITY,
            "validated_before_model_build": True,
            "selected_string_ids": sorted(selected_string_ids),
            "provenance": CONSTRAINT_PROVENANCE[ARM_C05_STRING_FEASIBILITY],
        },
        "ferry_legs": ferry_legs,
        "ferry_minutes": sum(
            item.ferry_minutes for item in selected_breakdowns.values()
        ),
        "aircraft_reassignment_count": sum(
            item.reassignment_count for item in selected_breakdowns.values()
        ),
        "objective_breakdown": objective_breakdown,
        "all_constraints_satisfied": all(item["satisfied"] for item in all_checks),
        "constraint_violation_count": sum(not item["satisfied"] for item in all_checks),
    }


def solve_fixed_column_arm(
    scenario_data: Any,
    columns_data: Any,
    request: AircraftRecoveryRequest,
    costs: FixedColumnCostConfig,
    solver: SolverAdapter,
    *,
    solver_parameters: Mapping[str, bool | int | float | str] | None = None,
) -> ModelSolveResult:
    """Validate, build, solve, and independently audit the Fixed-Column ARM."""

    scenario, columns = _validated_inputs(scenario_data, columns_data)
    model = build_fixed_column_arm(scenario, columns, request, costs, solver)
    outcome = solver.solve(solver_parameters)
    selected_variables: dict[str, float] = {}
    diagnostics: dict[str, Any] = {
        "model": "ARM",
        "single_model_only": True,
        "constraint_contract": dict(CONSTRAINT_PROVENANCE),
        "paper_variable_domain": "binary:(3.12)",
        "required_operated_option_ids": list(request.required_operated_option_ids),
        "fixed_column_analysis": analyze_arm_fixed_columns(model),
        "solver": dict(outcome.diagnostics),
    }

    if outcome.has_solution:
        string_values = {
            string_id: solver.get_variable_value(variable)
            for string_id, variable in model.variables.items()
        }
        selected_variables = {
            model.variables[string_id].name: value
            for string_id, value in string_values.items()
            if value > 0.5
        }
        diagnostics = recompute_arm_diagnostics(model, string_values, costs)
        diagnostics["solver"] = dict(outcome.diagnostics)
        recomputed_objective = diagnostics["objective_breakdown"]["total"]
        if outcome.objective_value is None or not math.isclose(
            recomputed_objective,
            outcome.objective_value,
            rel_tol=ARM_FEASIBILITY_TOLERANCE,
            abs_tol=ARM_FEASIBILITY_TOLERANCE,
        ):
            raise RuntimeError(
                "ARM objective audit differs from Solver outcome: "
                f"audit={recomputed_objective}, solver={outcome.objective_value}"
            )
        if not diagnostics["all_constraints_satisfied"]:
            raise RuntimeError("ARM independent constraint audit found a violation")

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
