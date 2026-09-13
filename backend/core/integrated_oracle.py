from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from backend.config import (
    FixedColumnCostConfig,
    PassengerCapacityError,
    PassengerCapacityProfile,
    aircraft_string_cost,
    crew_pairing_cost,
    passenger_itinerary_cost,
    schedule_flight_option_cost,
    validate_passenger_capacity_profile,
)
from backend.schemas.columns import FlightOperationType, RecoveryColumns
from backend.schemas.model_result import ModelSolveResult
from backend.schemas.scenario import Scenario
from backend.services.column_validator import validate_recovery_columns
from backend.services.validator import validate_scenario
from backend.solver import (
    ConstraintSense,
    ObjectiveSense,
    SolverAdapter,
    VariableHandle,
    VariableType,
)

from . import arm, crm, prm, srm
from .arm import AircraftRecoveryRequest, FixedColumnArmModel
from .crm import CrewRecoveryRequest, FixedColumnCrmModel
from .crew_incidence import CrewRecoveryIncidence, build_crew_recovery_incidence
from .gate_inventory import GateInventoryData, build_gate_inventory_data
from .incidence import RecoveryIncidence, build_recovery_incidence
from .indices import CapacityIntervalKey, RecoveryIndices, build_recovery_indices
from .passenger_incidence import (
    PassengerRecoveryIncidence,
    build_passenger_recovery_incidence,
)
from .prm import FixedColumnPrmModel, PassengerRecoveryRequest
from .srm import FixedColumnSrmModel


INTEGRATED_MODEL_NAME = "full_integrated_fixed_column_oracle"
INTEGRATED_FEASIBILITY_TOLERANCE = 1e-6

INTEGRATED_L01_SCHEDULE_AIRCRAFT = "INTEGRATED-L01-SCHEDULE-AIRCRAFT"
INTEGRATED_L02_SCHEDULE_CREW = "INTEGRATED-L02-SCHEDULE-CREW"
INTEGRATED_L03_DEADHEAD_SCHEDULE = "INTEGRATED-L03-DEADHEAD-SCHEDULE"
INTEGRATED_L04_PASSENGER_SCHEDULE = "INTEGRATED-L04-PASSENGER-SCHEDULE"
INTEGRATED_L05_SEAT_SCHEDULE = "INTEGRATED-L05-SEAT-SCHEDULE"

LINKING_CONSTRAINTS = MappingProxyType(
    {
        INTEGRATED_L01_SCHEDULE_AIRCRAFT: "sum(A_FS[o,s] * y[s]) = x[o]",
        INTEGRATED_L02_SCHEDULE_CREW: "sum(A_FC_operate[o,p] * z[p]) = x[o]",
        INTEGRATED_L03_DEADHEAD_SCHEDULE: "z[p] <= x[o] for each deadhead incidence",
        INTEGRATED_L04_PASSENGER_SCHEDULE: "w[i] <= x[o] for each flight segment",
        INTEGRATED_L05_SEAT_SCHEDULE: "sum(pax[g(i)] * A_PI[o,i] * w[i]) <= capacity[o] * x[o]",
    }
)


class IntegratedOracleBuildError(ValueError):
    """Validated inputs cannot be mapped to the Phase 3 v1 oracle contract."""


@dataclass(frozen=True)
class IntegratedRecoveryRequest:
    scenario_id: str
    cost_profile_id: str
    capacity_profile_id: str

    def __post_init__(self) -> None:
        for name, value in (
            ("scenario_id", self.scenario_id),
            ("cost_profile_id", self.cost_profile_id),
            ("capacity_profile_id", self.capacity_profile_id),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")


@dataclass(frozen=True)
class IntegratedFixedColumnModel:
    scenario: Scenario
    columns: RecoveryColumns
    request: IntegratedRecoveryRequest
    costs: FixedColumnCostConfig
    capacity_profile: PassengerCapacityProfile
    indices: RecoveryIndices
    incidence: RecoveryIncidence
    crew_incidence: CrewRecoveryIncidence
    passenger_incidence: PassengerRecoveryIncidence
    gate_inventory: GateInventoryData
    x_variables: Mapping[str, VariableHandle]
    y_variables: Mapping[str, VariableHandle]
    z_variables: Mapping[str, VariableHandle]
    w_variables: Mapping[str, VariableHandle]
    schedule_costs: Mapping[str, float]
    string_costs: Mapping[str, Any]
    pairing_costs: Mapping[str, Any]
    itinerary_costs: Mapping[str, Any]


def _validation_message(scope: str, issues: list[Any]) -> str:
    details = "; ".join(
        f"{item.code}@{item.location}: {item.message}" for item in issues
    )
    return f"{scope} validation failed: {details}"


def _validated_inputs(
    scenario_data: Any,
    columns_data: Any,
    request: IntegratedRecoveryRequest,
    capacity_profile: PassengerCapacityProfile,
    costs: FixedColumnCostConfig,
) -> tuple[Scenario, RecoveryColumns]:
    scenario, scenario_issues = validate_scenario(scenario_data)
    if scenario is None or scenario_issues:
        raise IntegratedOracleBuildError(
            _validation_message("scenario", scenario_issues)
        )
    columns, column_issues = validate_recovery_columns(scenario, columns_data)
    if columns is None or column_issues:
        raise IntegratedOracleBuildError(
            _validation_message("columns", column_issues)
        )
    identities = {
        "request scenario": (request.scenario_id, scenario.scenario_id),
        "request cost profile": (request.cost_profile_id, costs.cost_profile_id),
        "request capacity profile": (
            request.capacity_profile_id,
            capacity_profile.capacity_profile_id,
        ),
    }
    for label, (actual, expected) in identities.items():
        if actual != expected:
            raise IntegratedOracleBuildError(
                f"{label} differs from validated input: {actual!r} != {expected!r}"
            )
    try:
        validate_passenger_capacity_profile(capacity_profile, scenario, columns)
    except PassengerCapacityError as exc:
        raise IntegratedOracleBuildError(
            f"capacity profile validation failed: {exc}"
        ) from exc
    return scenario, columns


def _name(constraint_id: str, instance: str, side: str = "") -> str:
    suffix = f":{side}" if side else ""
    return f"{constraint_id}[{instance}{suffix}]"


def _capacity_instance(index: int, key: CapacityIntervalKey) -> str:
    return (
        f"{index:03d}:{key.airport}:"
        f"{key.start_time.isoformat()}:{key.end_time.isoformat()}"
    )


def _require_candidates(
    indices: RecoveryIndices,
    incidence: RecoveryIncidence,
) -> None:
    for flight_id in indices.flights.ids:
        candidates = incidence.base_flight_to_options.columns_for_row(flight_id)
        if not candidates:
            raise IntegratedOracleBuildError(
                f"{srm.SRM_C01_FLIGHT_COVERAGE}: flight {flight_id!r} has no option"
            )
    for aircraft_id in indices.aircraft.ids:
        if not incidence.aircraft_to_strings.columns_for_row(aircraft_id):
            raise IntegratedOracleBuildError(
                f"{arm.ARM_C01_STRING_SELECTION}: aircraft {aircraft_id!r} has no string"
            )
    for crew_id in indices.crew.ids:
        if not incidence.crew_to_pairings.columns_for_row(crew_id):
            raise IntegratedOracleBuildError(
                f"{crm.CRM_C01_PAIRING_SELECTION}: crew {crew_id!r} has no pairing"
            )
    for group_id in indices.passenger_groups.ids:
        if not incidence.passenger_group_to_itineraries.columns_for_row(group_id):
            raise IntegratedOracleBuildError(
                f"{prm.PRM_C01_GROUP_SELECTION}: group {group_id!r} has no itinerary"
            )


def build_integrated_fixed_column_oracle(
    scenario: Scenario,
    columns: RecoveryColumns,
    request: IntegratedRecoveryRequest,
    capacity_profile: PassengerCapacityProfile,
    costs: FixedColumnCostConfig,
    solver: SolverAdapter,
) -> IntegratedFixedColumnModel:
    """Build one MIP containing Phase 3 v1 x/y/z/w decisions."""

    indices = build_recovery_indices(scenario, columns)
    try:
        incidence = build_recovery_incidence(scenario, columns, indices)
        crew_incidence = build_crew_recovery_incidence(scenario, columns, indices)
        passenger_incidence = build_passenger_recovery_incidence(
            scenario, columns, indices
        )
        gate_inventory = build_gate_inventory_data(scenario, columns)
    except (KeyError, ValueError) as exc:
        raise IntegratedOracleBuildError(
            f"integrated incidence build failed: {exc}"
        ) from exc
    _require_candidates(indices, incidence)

    options = {item.option_id: item for item in columns.flight_options}
    aircraft = {item.tail_id: item for item in scenario.aircraft}
    strings = {item.string_id: item for item in columns.aircraft_strings}
    crews = {item.crew_id: item for item in scenario.crew}
    pairings = {item.pairing_id: item for item in columns.crew_pairings}
    passengers = {item.pax_group_id: item for item in scenario.passengers}
    itineraries = {item.itinerary_id: item for item in columns.passenger_itineraries}
    schedule_option_ids = tuple(
        item.option_id
        for item in columns.flight_options
        if item.operation_type
        in {FlightOperationType.OPERATE, FlightOperationType.CANCEL}
    )

    referenced_passenger_options = {
        option_id
        for values in passenger_incidence.itinerary_to_flight_options.values()
        for option_id in values
    }
    missing_capacity = sorted(
        referenced_passenger_options
        - set(capacity_profile.seat_capacity_by_option_id)
    )
    if missing_capacity:
        raise IntegratedOracleBuildError(
            "passenger itineraries reference options without test/residual capacity: "
            f"{missing_capacity}"
        )

    schedule_costs = {
        option_id: schedule_flight_option_cost(scenario, options[option_id], costs)
        for option_id in schedule_option_ids
    }
    try:
        string_costs = {
            string_id: aircraft_string_cost(
                scenario, options, strings[string_id], costs
            )
            for string_id in indices.aircraft_strings.ids
        }
        pairing_costs = {
            pairing_id: crew_pairing_cost(
                scenario, options, pairings[pairing_id], costs
            )
            for pairing_id in indices.crew_pairings.ids
        }
        itinerary_costs = {
            itinerary_id: passenger_itinerary_cost(
                passengers[itineraries[itinerary_id].pax_group_id].count,
                itineraries[itinerary_id],
                costs,
            )
            for itinerary_id in indices.passenger_itineraries.ids
        }
    except (KeyError, ValueError) as exc:
        raise IntegratedOracleBuildError(
            f"integrated cost build failed: {exc}"
        ) from exc

    solver.create_model(INTEGRATED_MODEL_NAME)
    x = {
        option_id: solver.add_variable(
            f"x[{option_id}]", variable_type=VariableType.BINARY
        )
        for option_id in schedule_option_ids
    }
    y = {
        string_id: solver.add_variable(
            f"y[{string_id}]", variable_type=VariableType.BINARY
        )
        for string_id in indices.aircraft_strings.ids
    }
    z = {
        pairing_id: solver.add_variable(
            f"z[{pairing_id}]", variable_type=VariableType.BINARY
        )
        for pairing_id in indices.crew_pairings.ids
    }
    w = {
        itinerary_id: solver.add_variable(
            f"w[{itinerary_id}]", variable_type=VariableType.BINARY
        )
        for itinerary_id in indices.passenger_itineraries.ids
    }

    objective = {x[key]: value for key, value in schedule_costs.items()}
    objective.update({y[key]: value.total for key, value in string_costs.items()})
    objective.update({z[key]: value.total for key, value in pairing_costs.items()})
    objective.update({w[key]: value.total for key, value in itinerary_costs.items()})
    solver.set_objective(objective, ObjectiveSense.MINIMIZE)

    # SRM local constraints.
    for flight_id in indices.flights.ids:
        option_ids = tuple(
            option_id
            for option_id in incidence.base_flight_to_options.columns_for_row(flight_id)
            if option_id in x
        )
        solver.add_linear_constraint(
            {x[option_id]: 1.0 for option_id in option_ids},
            ConstraintSense.EQUAL,
            1.0,
            name=_name(srm.SRM_C01_FLIGHT_COVERAGE, flight_id),
        )
    for flight in scenario.flights:
        operated = tuple(
            option_id
            for option_id in incidence.base_flight_to_options.columns_for_row(
                flight.flight_id
            )
            if option_id in x
            and options[option_id].operation_type is FlightOperationType.OPERATE
        )
        if flight.strategic_flag:
            solver.add_linear_constraint(
                {x[option_id]: 1.0 for option_id in operated},
                ConstraintSense.EQUAL,
                1.0,
                name=_name(srm.SRM_C02_STRATEGIC_FLIGHT, flight.flight_id),
            )
        if flight.market_flag and flight.min_seats > 0:
            solver.add_linear_constraint(
                {x[option_id]: 1.0 for option_id in operated},
                ConstraintSense.GREATER_EQUAL,
                1.0,
                name=_name(srm.SRM_C06_MARKET_SEAT, flight.flight_id),
            )
    for index, (key, interval) in enumerate(
        zip(indices.capacity_intervals.ids, scenario.airport_intervals)
    ):
        instance = _capacity_instance(index, key)
        arrivals = tuple(
            option_id
            for option_id in incidence.arrival_capacity_to_options.columns_for_row(key)
            if option_id in x
            and options[option_id].operation_type is FlightOperationType.OPERATE
        )
        departures = tuple(
            option_id
            for option_id in incidence.departure_capacity_to_options.columns_for_row(key)
            if option_id in x
            and options[option_id].operation_type is FlightOperationType.OPERATE
        )
        solver.add_linear_constraint(
            {x[option_id]: 1.0 for option_id in arrivals},
            ConstraintSense.LESS_EQUAL,
            float(interval.arr_capacity),
            name=_name(srm.SRM_C03_ARRIVAL_CAPACITY, instance),
        )
        solver.add_linear_constraint(
            {x[option_id]: 1.0 for option_id in departures},
            ConstraintSense.LESS_EQUAL,
            float(interval.dep_capacity),
            name=_name(srm.SRM_C04_DEPARTURE_CAPACITY, instance),
        )
    for checkpoint in gate_inventory.checkpoints:
        coefficients = {
            x[option_id]: float(coefficient)
            for option_id, coefficient in checkpoint.coefficient_by_option.items()
            if option_id in x
        }
        solver.add_linear_constraint(
            coefficients,
            ConstraintSense.LESS_EQUAL,
            float(checkpoint.gate_capacity - checkpoint.initial_ground),
            name=_name(
                srm.SRM_C05_GATE_INVENTORY, checkpoint.checkpoint_id, "upper"
            ),
        )
        solver.add_linear_constraint(
            coefficients,
            ConstraintSense.GREATER_EQUAL,
            float(-checkpoint.initial_ground),
            name=_name(
                srm.SRM_C05_GATE_INVENTORY, checkpoint.checkpoint_id, "lower"
            ),
        )

    # ARM, CRM, and PRM local resource-choice constraints.
    for aircraft_id in indices.aircraft.ids:
        candidate_ids = incidence.aircraft_to_strings.columns_for_row(aircraft_id)
        solver.add_linear_constraint(
            {y[string_id]: 1.0 for string_id in candidate_ids},
            ConstraintSense.EQUAL,
            1.0,
            name=_name(arm.ARM_C01_STRING_SELECTION, aircraft_id),
        )
        terminal_ids = tuple(
            string_id
            for string_id in candidate_ids
            if strings[string_id].end_station
            == aircraft[aircraft_id].required_station_at_T_end
        )
        solver.add_linear_constraint(
            {y[string_id]: 1.0 for string_id in terminal_ids},
            ConstraintSense.EQUAL,
            1.0,
            name=_name(arm.ARM_C03_TERMINAL_STATION, aircraft_id),
        )
    for aircraft_id in indices.maintenance_aircraft.ids:
        compatible = incidence.maintenance_to_strings.columns_for_row(aircraft_id)
        solver.add_linear_constraint(
            {y[string_id]: 1.0 for string_id in compatible},
            ConstraintSense.EQUAL,
            1.0,
            name=_name(arm.ARM_C04_MAINTENANCE, aircraft_id),
        )
    for crew_id in indices.crew.ids:
        candidate_ids = incidence.crew_to_pairings.columns_for_row(crew_id)
        solver.add_linear_constraint(
            {z[pairing_id]: 1.0 for pairing_id in candidate_ids},
            ConstraintSense.EQUAL,
            1.0,
            name=_name(crm.CRM_C01_PAIRING_SELECTION, crew_id),
        )
        terminal_ids = tuple(
            pairing_id
            for pairing_id in candidate_ids
            if pairings[pairing_id].end_station
            == crews[crew_id].required_station_at_T_end
        )
        solver.add_linear_constraint(
            {z[pairing_id]: 1.0 for pairing_id in terminal_ids},
            ConstraintSense.EQUAL,
            1.0,
            name=_name(crm.CRM_C05_TERMINAL_OWNERSHIP, crew_id),
        )
    for group_id in indices.passenger_groups.ids:
        candidate_ids = passenger_incidence.group_to_itineraries.columns_for_row(
            group_id
        )
        solver.add_linear_constraint(
            {w[itinerary_id]: 1.0 for itinerary_id in candidate_ids},
            ConstraintSense.EQUAL,
            1.0,
            name=_name(prm.PRM_C01_GROUP_SELECTION, group_id),
        )

    # Cross-model linking replaces the Phase 2 external schedule requests.
    for option_id in indices.revenue_operate_options.ids:
        aircraft_coefficients = {
            y[string_id]: 1.0
            for string_id in incidence.option_to_aircraft_strings.columns_for_row(
                option_id
            )
        }
        aircraft_coefficients[x[option_id]] = -1.0
        solver.add_linear_constraint(
            aircraft_coefficients,
            ConstraintSense.EQUAL,
            0.0,
            name=_name(INTEGRATED_L01_SCHEDULE_AIRCRAFT, option_id),
        )
        crew_coefficients = {
            z[pairing_id]: 1.0
            for pairing_id in crew_incidence.operated_option_to_pairings.columns_for_row(
                option_id
            )
        }
        crew_coefficients[x[option_id]] = -1.0
        solver.add_linear_constraint(
            crew_coefficients,
            ConstraintSense.EQUAL,
            0.0,
            name=_name(INTEGRATED_L02_SCHEDULE_CREW, option_id),
        )
        for pairing_id in crew_incidence.deadhead_option_to_pairings.columns_for_row(
            option_id
        ):
            solver.add_linear_constraint(
                {z[pairing_id]: 1.0, x[option_id]: -1.0},
                ConstraintSense.LESS_EQUAL,
                0.0,
                name=_name(
                    INTEGRATED_L03_DEADHEAD_SCHEDULE,
                    f"{option_id}:{pairing_id}",
                ),
            )

    for itinerary_id, option_ids in passenger_incidence.itinerary_to_flight_options.items():
        for option_id in option_ids:
            solver.add_linear_constraint(
                {w[itinerary_id]: 1.0, x[option_id]: -1.0},
                ConstraintSense.LESS_EQUAL,
                0.0,
                name=_name(
                    INTEGRATED_L04_PASSENGER_SCHEDULE,
                    f"{itinerary_id}:{option_id}",
                ),
            )
    for option_id in sorted(referenced_passenger_options):
        coefficients = {
            w[itinerary_id]: float(
                passengers[itineraries[itinerary_id].pax_group_id].count
            )
            for itinerary_id in passenger_incidence.option_to_itineraries.columns_for_row(
                option_id
            )
        }
        coefficients[x[option_id]] = -float(
            capacity_profile.seat_capacity_by_option_id[option_id]
        )
        solver.add_linear_constraint(
            coefficients,
            ConstraintSense.LESS_EQUAL,
            0.0,
            name=_name(INTEGRATED_L05_SEAT_SCHEDULE, option_id),
        )

    return IntegratedFixedColumnModel(
        scenario=scenario,
        columns=columns,
        request=request,
        costs=costs,
        capacity_profile=capacity_profile,
        indices=indices,
        incidence=incidence,
        crew_incidence=crew_incidence,
        passenger_incidence=passenger_incidence,
        gate_inventory=gate_inventory,
        x_variables=MappingProxyType(x),
        y_variables=MappingProxyType(y),
        z_variables=MappingProxyType(z),
        w_variables=MappingProxyType(w),
        schedule_costs=MappingProxyType(schedule_costs),
        string_costs=MappingProxyType(string_costs),
        pairing_costs=MappingProxyType(pairing_costs),
        itinerary_costs=MappingProxyType(itinerary_costs),
    )


def _link_check(
    constraint_id: str,
    instance: str,
    lhs: float,
    sense: str,
    rhs: float,
) -> dict[str, Any]:
    if sense == "==":
        satisfied = math.isclose(
            lhs,
            rhs,
            rel_tol=INTEGRATED_FEASIBILITY_TOLERANCE,
            abs_tol=INTEGRATED_FEASIBILITY_TOLERANCE,
        )
        slack = -abs(lhs - rhs)
    else:
        satisfied = lhs <= rhs + INTEGRATED_FEASIBILITY_TOLERANCE
        slack = rhs - lhs
    return {
        "constraint_id": constraint_id,
        "instance": instance,
        "lhs": lhs,
        "sense": sense,
        "rhs": rhs,
        "slack": slack,
        "satisfied": satisfied,
        "formula": LINKING_CONSTRAINTS[constraint_id],
    }


def recompute_integrated_diagnostics(
    model: IntegratedFixedColumnModel,
    x_values: Mapping[str, float],
    y_values: Mapping[str, float],
    z_values: Mapping[str, float],
    w_values: Mapping[str, float],
) -> dict[str, Any]:
    """Independently audit all local blocks, linking, and owner costs."""

    supplied = (
        ("x", set(x_values), set(model.x_variables)),
        ("y", set(y_values), set(model.y_variables)),
        ("z", set(z_values), set(model.z_variables)),
        ("w", set(w_values), set(model.w_variables)),
    )
    for name, actual, expected in supplied:
        if actual != expected:
            raise IntegratedOracleBuildError(
                f"integrated audit {name} IDs differ; "
                f"unknown={sorted(actual - expected)}, missing={sorted(expected - actual)}"
            )

    selected_operated = tuple(
        option_id
        for option_id in model.indices.revenue_operate_options.ids
        if x_values[option_id] > 0.5
    )
    arm_request = AircraftRecoveryRequest(model.scenario.scenario_id, selected_operated)
    crm_request = CrewRecoveryRequest(model.scenario.scenario_id, selected_operated)
    prm_request = PassengerRecoveryRequest(
        model.scenario.scenario_id,
        selected_operated,
        model.capacity_profile.capacity_profile_id,
    )
    schedule_eligible = {
        itinerary_id: (
            itinerary_id in model.passenger_incidence.unserved_itineraries
            or set(
                model.passenger_incidence.itinerary_to_flight_options[itinerary_id]
            ).issubset(selected_operated)
        )
        for itinerary_id in model.indices.passenger_itineraries.ids
    }
    srm_model = FixedColumnSrmModel(
        scenario=model.scenario,
        columns=model.columns,
        indices=model.indices,
        incidence=model.incidence,
        gate_inventory=model.gate_inventory,
        variables=model.x_variables,
        option_costs=model.schedule_costs,
    )
    arm_model = FixedColumnArmModel(
        scenario=model.scenario,
        columns=model.columns,
        request=arm_request,
        indices=model.indices,
        incidence=model.incidence,
        variables=model.y_variables,
        string_costs=model.string_costs,
    )
    crm_model = FixedColumnCrmModel(
        scenario=model.scenario,
        columns=model.columns,
        request=crm_request,
        indices=model.indices,
        incidence=model.crew_incidence,
        variables=model.z_variables,
        pairing_costs=model.pairing_costs,
    )
    prm_model = FixedColumnPrmModel(
        scenario=model.scenario,
        columns=model.columns,
        request=prm_request,
        capacity_profile=model.capacity_profile,
        indices=model.indices,
        incidence=model.passenger_incidence,
        variables=model.w_variables,
        itinerary_costs=model.itinerary_costs,
        schedule_eligible=MappingProxyType(schedule_eligible),
    )

    srm_audit = srm.recompute_srm_diagnostics(srm_model, x_values, model.costs)
    arm_audit = arm.recompute_arm_diagnostics(arm_model, y_values, model.costs)
    crm_audit = crm.recompute_crm_diagnostics(crm_model, z_values, model.costs)
    prm_audit = prm.recompute_prm_diagnostics(prm_model, w_values, model.costs)
    for audit in (srm_audit, arm_audit, crm_audit, prm_audit):
        audit["single_model_only"] = False
        audit["audit_context"] = "integrated_selected_values"

    aircraft_checks = []
    crew_checks = []
    deadhead_checks = []
    passenger_checks = []
    seat_checks = []
    passengers = {item.pax_group_id: item for item in model.scenario.passengers}
    itineraries = {
        item.itinerary_id: item for item in model.columns.passenger_itineraries
    }
    referenced_options = {
        option_id
        for values in model.passenger_incidence.itinerary_to_flight_options.values()
        for option_id in values
    }
    for option_id in model.indices.revenue_operate_options.ids:
        aircraft_coverage = sum(
            y_values[string_id]
            for string_id in model.incidence.option_to_aircraft_strings.columns_for_row(
                option_id
            )
        )
        aircraft_checks.append(
            _link_check(
                INTEGRATED_L01_SCHEDULE_AIRCRAFT,
                option_id,
                aircraft_coverage,
                "==",
                x_values[option_id],
            )
        )
        crew_coverage = sum(
            z_values[pairing_id]
            for pairing_id in model.crew_incidence.operated_option_to_pairings.columns_for_row(
                option_id
            )
        )
        crew_checks.append(
            _link_check(
                INTEGRATED_L02_SCHEDULE_CREW,
                option_id,
                crew_coverage,
                "==",
                x_values[option_id],
            )
        )
        for pairing_id in model.crew_incidence.deadhead_option_to_pairings.columns_for_row(
            option_id
        ):
            deadhead_checks.append(
                _link_check(
                    INTEGRATED_L03_DEADHEAD_SCHEDULE,
                    f"{option_id}:{pairing_id}",
                    z_values[pairing_id],
                    "<=",
                    x_values[option_id],
                )
            )
    for itinerary_id, option_ids in model.passenger_incidence.itinerary_to_flight_options.items():
        for option_id in option_ids:
            passenger_checks.append(
                _link_check(
                    INTEGRATED_L04_PASSENGER_SCHEDULE,
                    f"{itinerary_id}:{option_id}",
                    w_values[itinerary_id],
                    "<=",
                    x_values[option_id],
                )
            )
    for option_id in sorted(referenced_options):
        load = sum(
            passengers[itineraries[itinerary_id].pax_group_id].count
            * w_values[itinerary_id]
            for itinerary_id in model.passenger_incidence.option_to_itineraries.columns_for_row(
                option_id
            )
        )
        rhs = (
            model.capacity_profile.seat_capacity_by_option_id[option_id]
            * x_values[option_id]
        )
        seat_checks.append(
            _link_check(
                INTEGRATED_L05_SEAT_SCHEDULE,
                option_id,
                float(load),
                "<=",
                float(rhs),
            )
        )

    cross_checks = (
        aircraft_checks
        + crew_checks
        + deadhead_checks
        + passenger_checks
        + seat_checks
    )
    objective_breakdown = {
        "srm": srm_audit["objective_breakdown"],
        "arm": arm_audit["objective_breakdown"],
        "crm": crm_audit["objective_breakdown"],
        "prm": prm_audit["objective_breakdown"],
        "srm_total": srm_audit["objective_breakdown"]["total"],
        "arm_total": arm_audit["objective_breakdown"]["total"],
        "crm_total": crm_audit["objective_breakdown"]["total"],
        "prm_total": prm_audit["objective_breakdown"]["total"],
    }
    objective_breakdown["grand_total"] = sum(
        objective_breakdown[key]
        for key in ("srm_total", "arm_total", "crm_total", "prm_total")
    )
    local_ok = all(
        audit["all_constraints_satisfied"]
        for audit in (srm_audit, arm_audit, crm_audit, prm_audit)
    )
    cross_ok = all(item["satisfied"] for item in cross_checks)
    return {
        "model": "INTEGRATED",
        "single_model_only": False,
        "phase": "3-v1-full-integrated-fixed-column-oracle",
        "linking_contract": dict(LINKING_CONSTRAINTS),
        "capacity_semantics": "TEST / RESIDUAL CAPACITY; NOT AIRCRAFT PHYSICAL CAPACITY",
        "selected_option_by_flight": srm_audit["selected_option_by_flight"],
        "selected_string_by_aircraft": arm_audit["selected_string_by_aircraft"],
        "selected_pairing_by_crew": crm_audit["selected_pairing_by_crew"],
        "selected_itinerary_by_group": prm_audit["selected_itinerary_by_group"],
        "srm_audit": srm_audit,
        "arm_audit": arm_audit,
        "crm_audit": crm_audit,
        "prm_audit": prm_audit,
        "cross_model_audit": {
            "schedule_aircraft": aircraft_checks,
            "schedule_crew": crew_checks,
            "deadhead_schedule": deadhead_checks,
            "passenger_schedule": passenger_checks,
            "seat_schedule": seat_checks,
            "all_constraints_satisfied": cross_ok,
            "constraint_violation_count": sum(
                not item["satisfied"] for item in cross_checks
            ),
        },
        "objective_breakdown": objective_breakdown,
        "all_constraints_satisfied": local_ok and cross_ok,
        "constraint_violation_count": (
            sum(
                audit["constraint_violation_count"]
                for audit in (srm_audit, arm_audit, crm_audit, prm_audit)
            )
            + sum(not item["satisfied"] for item in cross_checks)
        ),
    }


def audit_integrated_candidate(
    model: IntegratedFixedColumnModel,
    *,
    selected_option_by_flight: Mapping[str, str],
    selected_string_by_aircraft: Mapping[str, str],
    selected_pairing_by_crew: Mapping[str, str],
    selected_itinerary_by_group: Mapping[str, str],
) -> dict[str, Any]:
    """Audit a fully specified candidate without trusting a Solver objective."""

    ownership = (
        (
            "flight",
            selected_option_by_flight,
            set(model.indices.flights.ids),
            model.x_variables,
            {
                item.option_id: item.base_flight_id
                for item in model.columns.flight_options
                if item.option_id in model.x_variables
            },
        ),
        (
            "aircraft",
            selected_string_by_aircraft,
            set(model.indices.aircraft.ids),
            model.y_variables,
            {
                item.string_id: item.aircraft_id
                for item in model.columns.aircraft_strings
            },
        ),
        (
            "crew",
            selected_pairing_by_crew,
            set(model.indices.crew.ids),
            model.z_variables,
            {item.pairing_id: item.crew_id for item in model.columns.crew_pairings},
        ),
        (
            "passenger",
            selected_itinerary_by_group,
            set(model.indices.passenger_groups.ids),
            model.w_variables,
            {
                item.itinerary_id: item.pax_group_id
                for item in model.columns.passenger_itineraries
            },
        ),
    )
    for (
        label,
        selected_by_owner,
        expected_owners,
        variables,
        owner_by_candidate,
    ) in ownership:
        actual_owners = set(selected_by_owner)
        if actual_owners != expected_owners:
            raise IntegratedOracleBuildError(
                f"manual {label} candidate owner IDs differ; "
                f"unknown={sorted(actual_owners - expected_owners)}, "
                f"missing={sorted(expected_owners - actual_owners)}"
            )
        unknown = sorted(set(selected_by_owner.values()) - set(variables))
        if unknown:
            raise IntegratedOracleBuildError(
                f"manual {label} candidate selects unknown IDs: {unknown}"
            )
        wrong_owner = sorted(
            (owner_id, candidate_id)
            for owner_id, candidate_id in selected_by_owner.items()
            if owner_by_candidate[candidate_id] != owner_id
        )
        if wrong_owner:
            raise IntegratedOracleBuildError(
                f"manual {label} candidate ownership mismatch: {wrong_owner}"
            )
    x_values = {
        option_id: float(option_id in set(selected_option_by_flight.values()))
        for option_id in model.x_variables
    }
    y_values = {
        string_id: float(string_id in set(selected_string_by_aircraft.values()))
        for string_id in model.y_variables
    }
    z_values = {
        pairing_id: float(pairing_id in set(selected_pairing_by_crew.values()))
        for pairing_id in model.z_variables
    }
    w_values = {
        itinerary_id: float(
            itinerary_id in set(selected_itinerary_by_group.values())
        )
        for itinerary_id in model.w_variables
    }
    return recompute_integrated_diagnostics(
        model, x_values, y_values, z_values, w_values
    )


def solve_integrated_fixed_column_oracle(
    scenario_data: Any,
    columns_data: Any,
    request: IntegratedRecoveryRequest,
    capacity_profile: PassengerCapacityProfile,
    costs: FixedColumnCostConfig,
    solver: SolverAdapter,
    *,
    solver_parameters: Mapping[str, bool | int | float | str] | None = None,
) -> ModelSolveResult:
    """Validate, solve, and independently audit the Phase 3 v1 oracle."""

    scenario, columns = _validated_inputs(
        scenario_data, columns_data, request, capacity_profile, costs
    )
    model = build_integrated_fixed_column_oracle(
        scenario, columns, request, capacity_profile, costs, solver
    )
    outcome = solver.solve(solver_parameters)
    selected_variables: dict[str, float] = {}
    diagnostics: dict[str, Any] = {
        "model": "INTEGRATED",
        "single_model_only": False,
        "phase": "3-v1-full-integrated-fixed-column-oracle",
        "linking_contract": dict(LINKING_CONSTRAINTS),
        "capacity_semantics": "TEST / RESIDUAL CAPACITY; NOT AIRCRAFT PHYSICAL CAPACITY",
        "solver": dict(outcome.diagnostics),
    }
    if outcome.has_solution:
        values = {
            "x": {
                key: solver.get_variable_value(variable)
                for key, variable in model.x_variables.items()
            },
            "y": {
                key: solver.get_variable_value(variable)
                for key, variable in model.y_variables.items()
            },
            "z": {
                key: solver.get_variable_value(variable)
                for key, variable in model.z_variables.items()
            },
            "w": {
                key: solver.get_variable_value(variable)
                for key, variable in model.w_variables.items()
            },
        }
        diagnostics = recompute_integrated_diagnostics(
            model, values["x"], values["y"], values["z"], values["w"]
        )
        diagnostics["solver"] = dict(outcome.diagnostics)
        for variable_map, value_map in (
            (model.x_variables, values["x"]),
            (model.y_variables, values["y"]),
            (model.z_variables, values["z"]),
            (model.w_variables, values["w"]),
        ):
            selected_variables.update(
                {
                    variable_map[key].name: value
                    for key, value in value_map.items()
                    if value > 0.5
                }
            )
        recomputed = diagnostics["objective_breakdown"]["grand_total"]
        if outcome.objective_value is None or not math.isclose(
            recomputed,
            outcome.objective_value,
            rel_tol=INTEGRATED_FEASIBILITY_TOLERANCE,
            abs_tol=INTEGRATED_FEASIBILITY_TOLERANCE,
        ):
            raise RuntimeError(
                "Integrated objective audit differs from Solver outcome: "
                f"audit={recomputed}, solver={outcome.objective_value}"
            )
        if not diagnostics["all_constraints_satisfied"]:
            raise RuntimeError(
                "Integrated independent constraint audit found a violation"
            )

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
