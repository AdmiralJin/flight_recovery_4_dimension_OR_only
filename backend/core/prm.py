from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from backend.config.costs import (
    FixedColumnCostConfig,
    PassengerItineraryCostBreakdown,
    passenger_itinerary_cost,
)
from backend.config.passenger_capacity import (
    PassengerCapacityError,
    PassengerCapacityProfile,
    validate_passenger_capacity_profile,
)
from backend.schemas.columns import (
    FlightOperationType,
    PassengerItineraryStatus,
    PassengerSegmentType,
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

from .indices import RecoveryIndices, build_recovery_indices
from .passenger_incidence import (
    PassengerRecoveryIncidence,
    build_passenger_recovery_incidence,
)


PRM_C01_GROUP_SELECTION = "PRM-C01-PASSENGER-GROUP-SELECTION"
PRM_C02_SCHEDULE_CONSISTENCY = "PRM-C02-SCHEDULE-CONSISTENCY"
PRM_C03_SEAT_CAPACITY = "PRM-C03-SEAT-CAPACITY"
PRM_C04_ITINERARY_FEASIBILITY = "PRM-C04-ITINERARY-FEASIBILITY"

PRM_MODEL_NAME = "fixed_column_prm"
PRM_FEASIBILITY_TOLERANCE = 1e-6

CONSTRAINT_PROVENANCE = MappingProxyType(
    {
        PRM_C01_GROUP_SELECTION: (
            "paper_constraint:(3.18)+explicit_unserved_itinerary_mapping:A-049"
        ),
        PRM_C02_SCHEDULE_CONSISTENCY: ("implementation_guard:A-047"),
        PRM_C03_SEAT_CAPACITY: (
            "paper_constraint:(3.17)+external_residual_capacity_mapping:A-048"
        ),
        PRM_C04_ITINERARY_FEASIBILITY: ("fixed-column_validation:A-050"),
    }
)


class PrmBuildError(ValueError):
    """Validated inputs cannot be mapped to the Fixed-Column PRM contract."""


@dataclass(frozen=True)
class PassengerRecoveryRequest:
    scenario_id: str
    required_operated_option_ids: tuple[str, ...]
    capacity_profile_id: str

    def __post_init__(self) -> None:
        if not self.scenario_id:
            raise ValueError("scenario_id must not be empty")
        if not self.capacity_profile_id:
            raise ValueError("capacity_profile_id must not be empty")
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
        capacity_profile_id: str,
    ) -> PassengerRecoveryRequest:
        return cls(scenario_id, tuple(option_ids), capacity_profile_id)


@dataclass(frozen=True)
class FixedColumnPrmModel:
    scenario: Scenario
    columns: RecoveryColumns
    request: PassengerRecoveryRequest
    capacity_profile: PassengerCapacityProfile
    indices: RecoveryIndices
    incidence: PassengerRecoveryIncidence
    variables: Mapping[str, VariableHandle]
    itinerary_costs: Mapping[str, PassengerItineraryCostBreakdown]
    schedule_eligible: Mapping[str, bool]


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
        raise PrmBuildError(_validation_message("scenario", scenario_issues))
    columns, column_issues = validate_recovery_columns(scenario, columns_data)
    if columns is None or column_issues:
        raise PrmBuildError(_validation_message("columns", column_issues))
    return scenario, columns


def _validate_request(
    scenario: Scenario,
    columns: RecoveryColumns,
    request: PassengerRecoveryRequest,
    capacity_profile: PassengerCapacityProfile,
) -> None:
    if request.scenario_id != scenario.scenario_id:
        raise PrmBuildError(
            "PRM request scenario_id differs from validated Scenario: "
            f"{request.scenario_id!r} != {scenario.scenario_id!r}"
        )
    if request.capacity_profile_id != capacity_profile.capacity_profile_id:
        raise PrmBuildError(
            "PRM request capacity_profile_id differs from capacity profile: "
            f"{request.capacity_profile_id!r} != "
            f"{capacity_profile.capacity_profile_id!r}"
        )

    try:
        validate_passenger_capacity_profile(capacity_profile, scenario, columns)
    except PassengerCapacityError as exc:
        raise PrmBuildError(f"capacity profile validation failed: {exc}") from exc

    options = {option.option_id: option for option in columns.flight_options}
    base_flights: dict[str, str] = {}
    for option_id in request.required_operated_option_ids:
        option = options.get(option_id)
        if option is None:
            raise PrmBuildError(
                f"PRM request references unknown flight option {option_id!r}"
            )
        if (
            option.operation_type is not FlightOperationType.OPERATE
            or option.base_flight_id is None
        ):
            raise PrmBuildError(
                "PRM request accepts only revenue OPERATE options; "
                f"got {option.operation_type.value} option {option_id!r}"
            )
        if option.base_flight_id in base_flights:
            raise PrmBuildError(
                "PRM request contains multiple options for base flight "
                f"{option.base_flight_id!r}: "
                f"{base_flights[option.base_flight_id]!r}, {option_id!r}"
            )
        base_flights[option.base_flight_id] = option_id
        if option_id not in capacity_profile.seat_capacity_by_option_id:
            raise PrmBuildError(
                f"missing seat capacity for required operated option {option_id!r}"
            )


def _constraint_name(constraint_id: str, instance: str) -> str:
    return f"{constraint_id}[{instance}]"


def build_fixed_column_prm(
    scenario: Scenario,
    columns: RecoveryColumns,
    request: PassengerRecoveryRequest,
    capacity_profile: PassengerCapacityProfile,
    costs: FixedColumnCostConfig,
    solver: SolverAdapter,
) -> FixedColumnPrmModel:
    """Build, but do not solve, the Phase 2.5 Fixed-Column PRM."""

    _validate_request(scenario, columns, request, capacity_profile)
    try:
        indices = build_recovery_indices(scenario, columns)
        incidence = build_passenger_recovery_incidence(scenario, columns, indices)
    except (KeyError, ValueError) as exc:
        raise PrmBuildError(f"PRM incidence build failed: {exc}") from exc

    passengers = {item.pax_group_id: item for item in scenario.passengers}
    itineraries = {
        item.itinerary_id: item for item in columns.passenger_itineraries
    }
    for group_id in indices.passenger_groups.ids:
        if not incidence.group_to_itineraries.columns_for_row(group_id):
            raise PrmBuildError(
                f"{PRM_C01_GROUP_SELECTION}: passenger group {group_id!r} has no "
                "explicit candidate itinerary"
            )

    required = set(request.required_operated_option_ids)
    schedule_eligible = {
        itinerary_id: (
            itinerary_id in incidence.unserved_itineraries
            or set(incidence.itinerary_to_flight_options[itinerary_id]).issubset(
                required
            )
        )
        for itinerary_id in indices.passenger_itineraries.ids
    }

    try:
        itinerary_costs = {
            itinerary_id: passenger_itinerary_cost(
                passengers[itineraries[itinerary_id].pax_group_id].count,
                itineraries[itinerary_id],
                costs,
            )
            for itinerary_id in indices.passenger_itineraries.ids
        }
    except (KeyError, ValueError) as exc:
        raise PrmBuildError(f"PRM itinerary cost build failed: {exc}") from exc

    solver.create_model(PRM_MODEL_NAME)
    variables = {
        itinerary_id: solver.add_variable(
            f"w[{itinerary_id}]", variable_type=VariableType.BINARY
        )
        for itinerary_id in indices.passenger_itineraries.ids
    }
    solver.set_objective(
        {
            variables[itinerary_id]: breakdown.total
            for itinerary_id, breakdown in itinerary_costs.items()
        }
    )

    for group_id in indices.passenger_groups.ids:
        candidate_ids = incidence.group_to_itineraries.columns_for_row(group_id)
        solver.add_linear_constraint(
            {variables[itinerary_id]: 1.0 for itinerary_id in candidate_ids},
            ConstraintSense.EQUAL,
            1.0,
            name=_constraint_name(PRM_C01_GROUP_SELECTION, group_id),
        )

    for itinerary_id in indices.passenger_itineraries.ids:
        if schedule_eligible[itinerary_id]:
            continue
        solver.add_linear_constraint(
            {variables[itinerary_id]: 1.0},
            ConstraintSense.EQUAL,
            0.0,
            name=_constraint_name(PRM_C02_SCHEDULE_CONSISTENCY, itinerary_id),
        )

    for option_id in request.required_operated_option_ids:
        coefficients = {}
        for itinerary_id in incidence.option_to_itineraries.columns_for_row(option_id):
            itinerary = itineraries[itinerary_id]
            coefficients[variables[itinerary_id]] = float(
                passengers[itinerary.pax_group_id].count
            )
        solver.add_linear_constraint(
            coefficients,
            ConstraintSense.LESS_EQUAL,
            float(capacity_profile.seat_capacity_by_option_id[option_id]),
            name=_constraint_name(PRM_C03_SEAT_CAPACITY, option_id),
        )

    return FixedColumnPrmModel(
        scenario=scenario,
        columns=columns,
        request=request,
        capacity_profile=capacity_profile,
        indices=indices,
        incidence=incidence,
        variables=MappingProxyType(variables),
        itinerary_costs=MappingProxyType(itinerary_costs),
        schedule_eligible=MappingProxyType(schedule_eligible),
    )


def analyze_prm_fixed_columns(model: FixedColumnPrmModel) -> dict[str, Any]:
    eligible_by_group: dict[str, list[str]] = {}
    for group_id in model.indices.passenger_groups.ids:
        eligible_by_group[group_id] = [
            itinerary_id
            for itinerary_id in model.incidence.group_to_itineraries.columns_for_row(
                group_id
            )
            if model.schedule_eligible[itinerary_id]
        ]
    return {
        "schedule_eligible_itinerary_ids_by_group": eligible_by_group,
        "groups_without_schedule_compatible_itinerary": [
            group_id
            for group_id, itinerary_ids in eligible_by_group.items()
            if not itinerary_ids
        ],
        "schedule_ineligible_itinerary_ids": [
            itinerary_id
            for itinerary_id in model.indices.passenger_itineraries.ids
            if not model.schedule_eligible[itinerary_id]
        ],
    }


def _equality_check(
    constraint_id: str,
    instance: str,
    lhs: float,
    rhs: float,
) -> dict[str, Any]:
    satisfied = abs(lhs - rhs) <= PRM_FEASIBILITY_TOLERANCE
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


def _capacity_check(
    option_id: str,
    load: float,
    capacity: float,
) -> dict[str, Any]:
    return {
        "constraint_id": PRM_C03_SEAT_CAPACITY,
        "instance": option_id,
        "lhs": load,
        "sense": "<=",
        "rhs": capacity,
        "slack": capacity - load,
        "satisfied": load <= capacity + PRM_FEASIBILITY_TOLERANCE,
        "provenance": CONSTRAINT_PROVENANCE[PRM_C03_SEAT_CAPACITY],
    }


def _is_reaccommodated(
    model: FixedColumnPrmModel,
    itinerary_id: str,
) -> bool:
    itineraries = {
        item.itinerary_id: item for item in model.columns.passenger_itineraries
    }
    passengers = {item.pax_group_id: item for item in model.scenario.passengers}
    options = {item.option_id: item for item in model.columns.flight_options}
    itinerary = itineraries[itinerary_id]
    if itinerary.status is PassengerItineraryStatus.UNSERVED:
        return False
    if any(
        segment.segment_type is PassengerSegmentType.SURFACE
        for segment in itinerary.segments
    ):
        return True
    base_flight_sequence = tuple(
        options[option_id].base_flight_id
        for option_id in model.incidence.itinerary_to_flight_options[itinerary_id]
    )
    passenger = passengers[itinerary.pax_group_id]
    return base_flight_sequence != tuple(passenger.original_itinerary)


def recompute_prm_diagnostics(
    model: FixedColumnPrmModel,
    itinerary_values: Mapping[str, float],
    costs: FixedColumnCostConfig,
) -> dict[str, Any]:
    """Independently recalculate every Phase 2.5 PRM constraint and cost."""

    expected_ids = set(model.variables)
    actual_ids = set(itinerary_values)
    if actual_ids != expected_ids:
        raise PrmBuildError(
            "PRM audit itinerary IDs differ from model; "
            f"unknown={sorted(actual_ids - expected_ids)}, "
            f"missing={sorted(expected_ids - actual_ids)}"
        )

    passengers = {item.pax_group_id: item for item in model.scenario.passengers}
    itineraries = {
        item.itinerary_id: item for item in model.columns.passenger_itineraries
    }
    selected_ids = {
        itinerary_id
        for itinerary_id, value in itinerary_values.items()
        if value > 0.5
    }

    variable_domain_checks = [
        {
            "constraint_id": PRM_C01_GROUP_SELECTION,
            "instance": f"binary:{itinerary_id}",
            "lhs": value,
            "sense": "in",
            "rhs": "{0,1}",
            "slack": 0.0,
            "satisfied": min(abs(value), abs(value - 1.0))
            <= PRM_FEASIBILITY_TOLERANCE,
            "provenance": (
                "binary_fixed-group_mapping:A-049; paper domain is nonnegative integer"
            ),
        }
        for itinerary_id, value in itinerary_values.items()
    ]

    selected_by_group: dict[str, str] = {}
    group_checks = []
    group_details = []
    for group_id in model.indices.passenger_groups.ids:
        candidate_ids = model.incidence.group_to_itineraries.columns_for_row(group_id)
        lhs = sum(itinerary_values[item] for item in candidate_ids)
        group_checks.append(
            _equality_check(PRM_C01_GROUP_SELECTION, group_id, lhs, 1.0)
        )
        selected = [item for item in candidate_ids if item in selected_ids]
        if len(selected) != 1:
            continue
        itinerary_id = selected[0]
        selected_by_group[group_id] = itinerary_id
        itinerary = itineraries[itinerary_id]
        passenger = passengers[group_id]
        group_details.append(
            {
                "pax_group_id": group_id,
                "selected_itinerary_id": itinerary_id,
                "status": itinerary.status.value,
                "count": passenger.count,
                "arrival_delay_minutes": itinerary.arrival_delay_minutes,
                "weighted_delay": (
                    passenger.count * (itinerary.arrival_delay_minutes or 0)
                    if itinerary.status is PassengerItineraryStatus.TRANSPORTED
                    else 0
                ),
                "reaccommodated": _is_reaccommodated(model, itinerary_id),
            }
        )

    schedule_checks = [
        _equality_check(
            PRM_C02_SCHEDULE_CONSISTENCY,
            itinerary_id,
            itinerary_values[itinerary_id],
            0.0,
        )
        for itinerary_id in model.indices.passenger_itineraries.ids
        if not model.schedule_eligible[itinerary_id]
    ]

    flight_seat_load: dict[str, float] = {}
    capacity_checks = []
    for option_id in model.request.required_operated_option_ids:
        load = sum(
            passengers[itineraries[itinerary_id].pax_group_id].count
            * itinerary_values[itinerary_id]
            for itinerary_id in model.incidence.option_to_itineraries.columns_for_row(
                option_id
            )
        )
        capacity = float(
            model.capacity_profile.seat_capacity_by_option_id[option_id]
        )
        flight_seat_load[option_id] = load
        capacity_checks.append(_capacity_check(option_id, load, capacity))

    selected_breakdowns = {
        itinerary_id: passenger_itinerary_cost(
            passengers[itineraries[itinerary_id].pax_group_id].count,
            itineraries[itinerary_id],
            costs,
        )
        for itinerary_id in selected_ids
    }
    delay_cost = sum(item.delay_cost for item in selected_breakdowns.values())
    unserved_cost = sum(item.unserved_cost for item in selected_breakdowns.values())
    objective_breakdown = {
        "passenger_delay": delay_cost,
        "unserved_passenger": unserved_cost,
        "total": delay_cost + unserved_cost,
    }
    all_checks = (
        variable_domain_checks + group_checks + schedule_checks + capacity_checks
    )
    required = set(model.request.required_operated_option_ids)
    unexpected = [
        option_id
        for option_id in model.indices.revenue_operate_options.ids
        if option_id not in required
        and any(
            itinerary_id in selected_ids
            for itinerary_id in model.incidence.option_to_itineraries.columns_for_row(
                option_id
            )
        )
    ]
    capacity_by_option = {
        option_id: model.capacity_profile.seat_capacity_by_option_id[option_id]
        for option_id in model.request.required_operated_option_ids
    }
    return {
        "model": "PRM",
        "single_model_only": True,
        "constraint_contract": dict(CONSTRAINT_PROVENANCE),
        "paper_objective": "(3.16):fixed-column group mapping",
        "paper_variable_domain": (
            "paper nonnegative integer passenger flow mapped to binary, "
            "indivisible passenger-group itinerary selection"
        ),
        "fixed_column_analysis": analyze_prm_fixed_columns(model),
        "required_operated_option_ids": list(
            model.request.required_operated_option_ids
        ),
        "capacity_profile_id": model.capacity_profile.capacity_profile_id,
        "capacity_source": model.capacity_profile.source.value,
        "selected_itinerary_by_group": selected_by_group,
        "group_details": group_details,
        "transported_passengers": sum(
            item["count"] for item in group_details if item["status"] == "transported"
        ),
        "unserved_passengers": sum(
            item["count"] for item in group_details if item["status"] == "unserved"
        ),
        "reaccommodated_passengers": sum(
            item["count"] for item in group_details if item["reaccommodated"]
        ),
        "weighted_passenger_delay_minutes": sum(
            item["weighted_delay"] for item in group_details
        ),
        "flight_seat_load": flight_seat_load,
        "flight_seat_capacity": capacity_by_option,
        "flight_seat_slack": {
            option_id: capacity_by_option[option_id] - flight_seat_load[option_id]
            for option_id in model.request.required_operated_option_ids
        },
        "capacity_violations": [
            item["instance"] for item in capacity_checks if not item["satisfied"]
        ],
        "unexpected_flight_options": unexpected,
        "group_selection_constraints": group_checks,
        "variable_domain_checks": variable_domain_checks,
        "schedule_consistency_constraints": schedule_checks,
        "seat_capacity_constraints": capacity_checks,
        "itinerary_feasibility_status": {
            "constraint_id": PRM_C04_ITINERARY_FEASIBILITY,
            "validated_before_model_build": True,
            "selected_itinerary_ids": sorted(selected_ids),
            "minimum_connection_time_modeled": False,
            "provenance": CONSTRAINT_PROVENANCE[PRM_C04_ITINERARY_FEASIBILITY],
        },
        "objective_breakdown": objective_breakdown,
        "all_constraints_satisfied": all(item["satisfied"] for item in all_checks),
        "constraint_violation_count": sum(not item["satisfied"] for item in all_checks),
    }


def solve_fixed_column_prm(
    scenario_data: Any,
    columns_data: Any,
    request: PassengerRecoveryRequest,
    capacity_profile: PassengerCapacityProfile,
    costs: FixedColumnCostConfig,
    solver: SolverAdapter,
    *,
    solver_parameters: Mapping[str, bool | int | float | str] | None = None,
) -> ModelSolveResult:
    """Validate, build, solve, and independently audit the Fixed-Column PRM."""

    scenario, columns = _validated_inputs(scenario_data, columns_data)
    model = build_fixed_column_prm(
        scenario,
        columns,
        request,
        capacity_profile,
        costs,
        solver,
    )
    outcome = solver.solve(solver_parameters)
    selected_variables: dict[str, float] = {}
    diagnostics: dict[str, Any] = {
        "model": "PRM",
        "single_model_only": True,
        "constraint_contract": dict(CONSTRAINT_PROVENANCE),
        "paper_objective": "(3.16):fixed-column group mapping",
        "paper_variable_domain": (
            "paper nonnegative integer passenger flow mapped to binary, "
            "indivisible passenger-group itinerary selection"
        ),
        "required_operated_option_ids": list(request.required_operated_option_ids),
        "capacity_profile_id": capacity_profile.capacity_profile_id,
        "capacity_source": capacity_profile.source.value,
        "fixed_column_analysis": analyze_prm_fixed_columns(model),
        "solver": dict(outcome.diagnostics),
    }

    if outcome.has_solution:
        itinerary_values = {
            itinerary_id: solver.get_variable_value(variable)
            for itinerary_id, variable in model.variables.items()
        }
        selected_variables = {
            model.variables[itinerary_id].name: value
            for itinerary_id, value in itinerary_values.items()
            if value > 0.5
        }
        diagnostics = recompute_prm_diagnostics(model, itinerary_values, costs)
        diagnostics["solver"] = dict(outcome.diagnostics)
        recomputed_objective = diagnostics["objective_breakdown"]["total"]
        if outcome.objective_value is None or not math.isclose(
            recomputed_objective,
            outcome.objective_value,
            rel_tol=PRM_FEASIBILITY_TOLERANCE,
            abs_tol=PRM_FEASIBILITY_TOLERANCE,
        ):
            raise RuntimeError(
                "PRM objective audit differs from Solver outcome: "
                f"audit={recomputed_objective}, solver={outcome.objective_value}"
            )
        if not diagnostics["all_constraints_satisfied"]:
            raise RuntimeError("PRM independent constraint audit found a violation")

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
