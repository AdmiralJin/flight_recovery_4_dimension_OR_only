from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any

from backend.config import (
    FixedColumnBendersConfig,
    FixedColumnCostConfig,
    PassengerCapacityError,
    PassengerCapacityProfile,
    aircraft_string_cost,
    crew_pairing_cost,
    passenger_itinerary_cost,
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
    SolverStatus,
    VariableHandle,
    VariableType,
)

from .arm import AircraftRecoveryRequest, solve_fixed_column_arm
from .crm import CrewRecoveryRequest, solve_fixed_column_crm
from .integrated_oracle import (
    IntegratedRecoveryRequest,
    build_integrated_fixed_column_oracle,
    recompute_integrated_diagnostics,
)
from .prm import PassengerRecoveryRequest, solve_fixed_column_prm
from .scope import (
    OriginalCandidates,
    RecoveryScope,
    resolve_original_candidates,
    validate_recovery_scope,
)
from .srm import FixedColumnSrmModel, build_fixed_column_srm


BENDERS_MASTER_MODEL_NAME = "fixed_column_benders_master"
BENDERS_FEASIBILITY_TOLERANCE = 1e-6


class BendersSubproblem(str, Enum):
    ARM = "arm"
    CRM = "crm"
    PRM = "prm"


class BendersCutType(str, Enum):
    FEASIBILITY = "feasibility"
    OPTIMALITY = "optimality"


class BendersStatus(str, Enum):
    OPTIMAL = "optimal"
    INFEASIBLE = "infeasible"
    NOT_CONVERGED = "not_converged"
    ABORTED = "aborted"


class FixedColumnBendersError(ValueError):
    """The fixed-column decomposition contract cannot be applied safely."""


@dataclass(frozen=True)
class BendersCut:
    cut_type: BendersCutType
    subproblem: BendersSubproblem | None
    schedule_signature: tuple[str, ...]
    recourse_value: float | None = None
    big_m: float | None = None

    def __post_init__(self) -> None:
        signature = tuple(self.schedule_signature)
        if not signature or any(not item for item in signature):
            raise FixedColumnBendersError("Benders cut requires a non-empty signature")
        if len(signature) != len(set(signature)):
            raise FixedColumnBendersError(
                "Benders cut signature must contain unique IDs"
            )
        object.__setattr__(self, "schedule_signature", signature)
        if self.cut_type is BendersCutType.FEASIBILITY:
            if self.subproblem is not None:
                raise FixedColumnBendersError(
                    "feasibility cut must represent the complete schedule"
                )
            if self.recourse_value is not None or self.big_m is not None:
                raise FixedColumnBendersError(
                    "feasibility cut cannot carry recourse_value or big_m"
                )
            return
        if self.subproblem is None:
            raise FixedColumnBendersError("optimality cut requires a subproblem")
        if self.recourse_value is None or self.big_m is None:
            raise FixedColumnBendersError(
                "optimality cut requires recourse_value and big_m"
            )
        if not math.isfinite(self.recourse_value) or self.recourse_value < 0:
            raise FixedColumnBendersError(
                "recourse_value must be finite and nonnegative"
            )
        if not math.isfinite(self.big_m) or self.big_m < self.recourse_value:
            raise FixedColumnBendersError(
                "big_m must be finite and at least recourse_value"
            )

    @property
    def key(self) -> tuple[str, str | None, tuple[str, ...]]:
        return (
            self.cut_type.value,
            self.subproblem.value if self.subproblem is not None else None,
            self.schedule_signature,
        )

    @property
    def cut_id(self) -> str:
        digest = hashlib.sha256(
            json.dumps(self.key, separators=(",", ":")).encode("utf-8")
        ).hexdigest()[:16]
        if self.cut_type is BendersCutType.FEASIBILITY:
            return f"BEND_F_{digest}"
        assert self.subproblem is not None
        return f"BEND_O_{self.subproblem.value.upper()}_{digest}"


@dataclass(frozen=True)
class BendersIterationRecord:
    iteration: int
    master_objective: float
    lower_bound: float
    candidate_upper_bound: float | None
    incumbent_upper_bound: float | None
    absolute_gap: float | None
    relative_gap: float | None
    schedule_signature: tuple[str, ...]
    arm_status: str
    crm_status: str
    prm_status: str
    arm_objective: float | None
    crm_objective: float | None
    prm_objective: float | None
    infeasible_subproblems: tuple[str, ...]
    feasibility_cuts_added: int
    optimality_cuts_added: int
    total_unique_cuts: int


@dataclass(frozen=True)
class FixedColumnBendersResult:
    status: BendersStatus
    objective_value: float | None
    lower_bound: float | None
    upper_bound: float | None
    iterations: tuple[BendersIterationRecord, ...]
    cuts: tuple[BendersCut, ...]
    x_values: Mapping[str, float]
    y_values: Mapping[str, float]
    z_values: Mapping[str, float]
    w_values: Mapping[str, float]
    selected_flight_options: tuple[str, ...]
    selected_aircraft_strings: tuple[str, ...]
    selected_crew_pairings: tuple[str, ...]
    selected_passenger_itineraries: tuple[str, ...]
    diagnostics: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "objective_value": self.objective_value,
            "lower_bound": self.lower_bound,
            "upper_bound": self.upper_bound,
            "iterations": [asdict(item) for item in self.iterations],
            "cuts": [
                {
                    "cut_id": item.cut_id,
                    "cut_type": item.cut_type.value,
                    "subproblem": (
                        item.subproblem.value if item.subproblem is not None else None
                    ),
                    "schedule_signature": list(item.schedule_signature),
                    "recourse_value": item.recourse_value,
                    "big_m": item.big_m,
                }
                for item in self.cuts
            ],
            "x_values": dict(self.x_values),
            "y_values": dict(self.y_values),
            "z_values": dict(self.z_values),
            "w_values": dict(self.w_values),
            "selected_flight_options": list(self.selected_flight_options),
            "selected_aircraft_strings": list(self.selected_aircraft_strings),
            "selected_crew_pairings": list(self.selected_crew_pairings),
            "selected_passenger_itineraries": list(self.selected_passenger_itineraries),
            "diagnostics": dict(self.diagnostics),
        }


@dataclass(frozen=True)
class BendersRecourseBounds:
    arm: float
    crm: float
    prm: float

    def for_subproblem(self, subproblem: BendersSubproblem) -> float:
        return float(getattr(self, subproblem.value))

    def to_dict(self) -> dict[str, float]:
        return {"arm": self.arm, "crm": self.crm, "prm": self.prm}


@dataclass(frozen=True)
class FixedColumnBendersMaster:
    srm_model: FixedColumnSrmModel
    theta_variables: Mapping[BendersSubproblem, VariableHandle]
    cuts: tuple[BendersCut, ...]
    original_candidates: OriginalCandidates | None = None


@dataclass(frozen=True)
class _SubproblemResult:
    status: SolverStatus | None
    objective: float | None
    values: Mapping[str, float] = field(default_factory=dict)
    diagnostics: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class _Incumbent:
    objective: float
    x_values: Mapping[str, float]
    y_values: Mapping[str, float]
    z_values: Mapping[str, float]
    w_values: Mapping[str, float]
    schedule_signature: tuple[str, ...]


def _validation_message(label: str, issues: Sequence[Any]) -> str:
    details = "; ".join(
        f"{item.code}@{item.location}: {item.message}" for item in issues
    )
    return f"{label} validation failed: {details}"


def _validated_inputs(
    scenario_data: Any,
    columns_data: Any,
    capacity_profile: PassengerCapacityProfile,
) -> tuple[Scenario, RecoveryColumns]:
    scenario, scenario_issues = validate_scenario(scenario_data)
    if scenario is None or scenario_issues:
        raise FixedColumnBendersError(_validation_message("scenario", scenario_issues))
    columns, column_issues = validate_recovery_columns(scenario, columns_data)
    if columns is None or column_issues:
        raise FixedColumnBendersError(_validation_message("columns", column_issues))
    try:
        validate_passenger_capacity_profile(capacity_profile, scenario, columns)
    except PassengerCapacityError as exc:
        raise FixedColumnBendersError(
            f"capacity profile validation failed: {exc}"
        ) from exc
    return scenario, columns


def schedule_signature(
    scenario: Scenario,
    columns: RecoveryColumns,
    x_values: Mapping[str, float],
) -> tuple[str, ...]:
    """Return exactly one selected schedule option per sorted base flight."""

    options_by_flight: dict[str, list[str]] = {
        flight.flight_id: [] for flight in scenario.flights
    }
    schedule_ids = set()
    for option in columns.flight_options:
        if option.operation_type not in {
            FlightOperationType.OPERATE,
            FlightOperationType.CANCEL,
        }:
            continue
        if option.base_flight_id not in options_by_flight:
            raise FixedColumnBendersError(
                f"schedule option {option.option_id!r} has unknown base flight"
            )
        options_by_flight[option.base_flight_id].append(option.option_id)
        schedule_ids.add(option.option_id)
    if set(x_values) != schedule_ids:
        raise FixedColumnBendersError(
            "schedule x IDs differ from the fixed schedule universe; "
            f"unknown={sorted(set(x_values) - schedule_ids)}, "
            f"missing={sorted(schedule_ids - set(x_values))}"
        )
    selected: list[str] = []
    for flight_id in sorted(options_by_flight):
        chosen = [
            option_id
            for option_id in options_by_flight[flight_id]
            if x_values[option_id] > 0.5
        ]
        if len(chosen) != 1:
            raise FixedColumnBendersError(
                f"schedule requires exactly one option for {flight_id!r}; got {chosen}"
            )
        selected.append(chosen[0])
    return tuple(selected)


def audit_benders_cut(
    cut: BendersCut,
    candidate_signature: Sequence[str],
    *,
    theta_value: float = 0.0,
) -> dict[str, Any]:
    candidate = tuple(candidate_signature)
    if len(candidate) != len(cut.schedule_signature):
        raise FixedColumnBendersError("candidate and cut signatures differ in length")
    matches = sum(
        candidate_id == visited_id
        for candidate_id, visited_id in zip(candidate, cut.schedule_signature)
    )
    size = len(candidate)
    if cut.cut_type is BendersCutType.FEASIBILITY:
        rhs = size - 1
        return {
            "cut_id": cut.cut_id,
            "matching_options": matches,
            "lhs": float(matches),
            "sense": "<=",
            "rhs": float(rhs),
            "satisfied": matches <= rhs,
        }
    assert cut.recourse_value is not None and cut.big_m is not None
    required_theta = cut.recourse_value - cut.big_m * (size - matches)
    return {
        "cut_id": cut.cut_id,
        "matching_options": matches,
        "required_theta": required_theta,
        "theta_value": theta_value,
        "sense": ">=",
        "satisfied": theta_value + BENDERS_FEASIBILITY_TOLERANCE >= required_theta,
    }


def build_scope_restricted_columns(
    scenario: Scenario,
    columns: RecoveryColumns,
    scope: RecoveryScope | None,
) -> RecoveryColumns:
    """Return a new owner-restricted view without mutating the fixed universe."""

    if scope is None:
        return RecoveryColumns.model_validate(columns.model_dump(mode="python"))
    try:
        validate_recovery_scope(scenario, columns, scope)
        original = resolve_original_candidates(scenario, columns)
    except (KeyError, ValueError) as exc:
        raise FixedColumnBendersError(f"scope restriction failed: {exc}") from exc
    scoped_aircraft = set(scope.aircraft_ids)
    scoped_crew = set(scope.crew_ids)
    scoped_passengers = set(scope.passenger_group_ids)
    payload = columns.model_dump(mode="python")
    payload["aircraft_strings"] = [
        item.model_dump(mode="python")
        for item in columns.aircraft_strings
        if item.aircraft_id in scoped_aircraft
        or item.string_id == original.aircraft_string_by_aircraft[item.aircraft_id]
    ]
    payload["crew_pairings"] = [
        item.model_dump(mode="python")
        for item in columns.crew_pairings
        if item.crew_id in scoped_crew
        or item.pairing_id == original.crew_pairing_by_crew[item.crew_id]
    ]
    payload["passenger_itineraries"] = [
        item.model_dump(mode="python")
        for item in columns.passenger_itineraries
        if item.pax_group_id in scoped_passengers
        or item.itinerary_id == original.passenger_itinerary_by_group[item.pax_group_id]
    ]
    return RecoveryColumns.model_validate(payload)


def _owner_maximum_sum(
    owners: Sequence[str],
    candidates_by_owner: Mapping[str, Sequence[float]],
    label: str,
) -> float:
    total = 0.0
    for owner_id in sorted(owners):
        values = tuple(candidates_by_owner.get(owner_id, ()))
        if not values:
            raise FixedColumnBendersError(
                f"invalid candidate universe: {label} owner {owner_id!r} has no candidate"
            )
        if any(not math.isfinite(value) or value < 0 for value in values):
            raise FixedColumnBendersError(
                f"invalid nonnegative {label} recourse costs for owner {owner_id!r}"
            )
        total += max(values)
    return total


def compute_benders_big_m(
    scenario: Scenario,
    columns: RecoveryColumns,
    costs: FixedColumnCostConfig,
) -> BendersRecourseBounds:
    """Compute safe owner-selection upper bounds from the actual fixed columns."""

    options = {item.option_id: item for item in columns.flight_options}
    passengers = {item.pax_group_id: item for item in scenario.passengers}
    arm_values: dict[str, list[float]] = {}
    for item in columns.aircraft_strings:
        arm_values.setdefault(item.aircraft_id, []).append(
            aircraft_string_cost(scenario, options, item, costs).total
        )
    crm_values: dict[str, list[float]] = {}
    for item in columns.crew_pairings:
        crm_values.setdefault(item.crew_id, []).append(
            crew_pairing_cost(scenario, options, item, costs).total
        )
    prm_values: dict[str, list[float]] = {}
    for item in columns.passenger_itineraries:
        passenger = passengers.get(item.pax_group_id)
        if passenger is None:
            raise FixedColumnBendersError(
                f"itinerary {item.itinerary_id!r} has unknown passenger owner"
            )
        prm_values.setdefault(item.pax_group_id, []).append(
            passenger_itinerary_cost(passenger.count, item, costs).total
        )
    return BendersRecourseBounds(
        arm=_owner_maximum_sum(
            [item.tail_id for item in scenario.aircraft], arm_values, "aircraft"
        ),
        crm=_owner_maximum_sum(
            [item.crew_id for item in scenario.crew], crm_values, "crew"
        ),
        prm=_owner_maximum_sum(
            [item.pax_group_id for item in scenario.passengers],
            prm_values,
            "passenger",
        ),
    )


def _enabled(config: FixedColumnBendersConfig, item: BendersSubproblem) -> bool:
    return bool(getattr(config, f"enable_{item.value}"))


def build_fixed_column_benders_master(
    scenario: Scenario,
    columns: RecoveryColumns,
    costs: FixedColumnCostConfig,
    config: FixedColumnBendersConfig,
    cuts: Sequence[BendersCut],
    solver: SolverAdapter,
    *,
    scope: RecoveryScope | None = None,
) -> FixedColumnBendersMaster:
    """Build a fresh SRM master and append theta variables and immutable cuts."""

    srm_model = build_fixed_column_srm(scenario, columns, costs, solver)
    theta = {
        item: solver.add_variable(
            f"theta[{item.value}]",
            lower_bound=0.0,
            upper_bound=None if _enabled(config, item) else 0.0,
            variable_type=VariableType.CONTINUOUS,
        )
        for item in BendersSubproblem
    }
    objective = {
        srm_model.variables[option_id]: value
        for option_id, value in srm_model.option_costs.items()
    }
    objective.update(
        {theta[item]: 1.0 for item in BendersSubproblem if _enabled(config, item)}
    )
    solver.set_objective(objective, ObjectiveSense.MINIMIZE)

    original = None
    if scope is not None:
        try:
            validate_recovery_scope(scenario, columns, scope)
            original = resolve_original_candidates(scenario, columns)
        except (KeyError, ValueError) as exc:
            raise FixedColumnBendersError(
                f"master scope validation failed: {exc}"
            ) from exc
        scoped_flights = set(scope.flight_ids)
        for flight in sorted(scenario.flights, key=lambda item: item.flight_id):
            if flight.flight_id in scoped_flights:
                continue
            option_id = original.flight_option_by_flight[flight.flight_id]
            solver.add_linear_constraint(
                {srm_model.variables[option_id]: 1.0},
                ConstraintSense.EQUAL,
                1.0,
                name=f"BEND-SCOPE-FLIGHT[{flight.flight_id}]",
            )

    seen: set[tuple[str, str | None, tuple[str, ...]]] = set()
    for cut in cuts:
        if cut.key in seen:
            raise FixedColumnBendersError(f"duplicate cut key: {cut.key!r}")
        seen.add(cut.key)
        unknown = set(cut.schedule_signature) - set(srm_model.variables)
        if unknown or len(cut.schedule_signature) != len(scenario.flights):
            raise FixedColumnBendersError(
                f"invalid cut {cut.cut_id}: unknown={sorted(unknown)}, "
                f"signature_size={len(cut.schedule_signature)}"
            )
        canonical_signature = schedule_signature(
            scenario,
            columns,
            {
                option_id: float(option_id in cut.schedule_signature)
                for option_id in srm_model.variables
            },
        )
        if canonical_signature != cut.schedule_signature:
            raise FixedColumnBendersError(
                f"invalid cut {cut.cut_id}: schedule signature is not canonical"
            )
        selected_coefficients = {
            srm_model.variables[option_id]: 1.0 for option_id in cut.schedule_signature
        }
        if cut.cut_type is BendersCutType.FEASIBILITY:
            solver.add_linear_constraint(
                selected_coefficients,
                ConstraintSense.LESS_EQUAL,
                float(len(cut.schedule_signature) - 1),
                name=cut.cut_id,
            )
            continue
        assert cut.subproblem is not None
        assert cut.big_m is not None and cut.recourse_value is not None
        coefficients = {variable: -cut.big_m for variable in selected_coefficients}
        coefficients[theta[cut.subproblem]] = 1.0
        solver.add_linear_constraint(
            coefficients,
            ConstraintSense.GREATER_EQUAL,
            cut.recourse_value - cut.big_m * len(cut.schedule_signature),
            name=cut.cut_id,
        )
    return FixedColumnBendersMaster(
        srm_model=srm_model,
        theta_variables=MappingProxyType(theta),
        cuts=tuple(cuts),
        original_candidates=original,
    )


def _solver_run(
    factory: Callable[[], SolverAdapter],
    solve: Callable[[SolverAdapter], ModelSolveResult],
) -> ModelSolveResult:
    solver = factory()
    try:
        return solve(solver)
    finally:
        solver.close()


def _values_from_result(
    result: ModelSolveResult,
    all_ids: Sequence[str],
    diagnostic_key: str,
) -> Mapping[str, float]:
    selected_by_owner = result.diagnostics.get(diagnostic_key, {})
    if not isinstance(selected_by_owner, Mapping):
        raise FixedColumnBendersError(
            f"{result.model_name} diagnostics.{diagnostic_key} is not a mapping"
        )
    selected = set(selected_by_owner.values())
    unknown = selected - set(all_ids)
    if unknown:
        raise FixedColumnBendersError(
            f"{result.model_name} returned unknown candidate IDs: {sorted(unknown)}"
        )
    return MappingProxyType(
        {item_id: float(item_id in selected) for item_id in all_ids}
    )


def _solve_subproblems(
    scenario: Scenario,
    original_columns: RecoveryColumns,
    restricted_columns: RecoveryColumns,
    required_operated: tuple[str, ...],
    capacity: PassengerCapacityProfile,
    costs: FixedColumnCostConfig,
    config: FixedColumnBendersConfig,
    solver_factory: Callable[[], SolverAdapter],
    solver_parameters: Mapping[str, bool | int | float | str] | None,
    *,
    iteration: int,
    schedule: tuple[str, ...],
) -> Mapping[BendersSubproblem, _SubproblemResult]:
    output: dict[BendersSubproblem, _SubproblemResult] = {}
    specs = (
        (
            BendersSubproblem.ARM,
            lambda solver: solve_fixed_column_arm(
                scenario,
                restricted_columns,
                AircraftRecoveryRequest(scenario.scenario_id, required_operated),
                costs,
                solver,
                solver_parameters=solver_parameters,
            ),
            [item.string_id for item in original_columns.aircraft_strings],
            "selected_string_by_aircraft",
        ),
        (
            BendersSubproblem.CRM,
            lambda solver: solve_fixed_column_crm(
                scenario,
                restricted_columns,
                CrewRecoveryRequest(scenario.scenario_id, required_operated),
                costs,
                solver,
                solver_parameters=solver_parameters,
            ),
            [item.pairing_id for item in original_columns.crew_pairings],
            "selected_pairing_by_crew",
        ),
        (
            BendersSubproblem.PRM,
            lambda solver: solve_fixed_column_prm(
                scenario,
                restricted_columns,
                PassengerRecoveryRequest(
                    scenario.scenario_id,
                    required_operated,
                    capacity.capacity_profile_id,
                ),
                capacity,
                costs,
                solver,
                solver_parameters=solver_parameters,
            ),
            [item.itinerary_id for item in original_columns.passenger_itineraries],
            "selected_itinerary_by_group",
        ),
    )
    for subproblem, solve, all_ids, diagnostic_key in specs:
        if not _enabled(config, subproblem):
            output[subproblem] = _SubproblemResult(None, 0.0)
            continue
        try:
            result = _solver_run(solver_factory, solve)
        except Exception as exc:
            raise FixedColumnBendersError(
                f"iteration {iteration}, schedule={schedule}, "
                f"subproblem={subproblem.value}: {exc}"
            ) from exc
        if result.status is SolverStatus.OPTIMAL:
            assert result.objective_value is not None
            values = _values_from_result(result, all_ids, diagnostic_key)
        else:
            values = MappingProxyType({})
        output[subproblem] = _SubproblemResult(
            result.status,
            result.objective_value,
            values,
            MappingProxyType(dict(result.diagnostics)),
        )
    return MappingProxyType(output)


def _status_text(result: _SubproblemResult) -> str:
    return result.status.value if result.status is not None else "disabled"


def _input_fingerprint(
    scenario: Scenario,
    columns: RecoveryColumns,
    costs: FixedColumnCostConfig,
    capacity: PassengerCapacityProfile,
    scope: RecoveryScope | None,
    config: FixedColumnBendersConfig,
) -> str:
    payload = {
        "scenario_id": scenario.scenario_id,
        "flight_options": sorted(item.option_id for item in columns.flight_options),
        "aircraft_strings": sorted(item.string_id for item in columns.aircraft_strings),
        "crew_pairings": sorted(item.pairing_id for item in columns.crew_pairings),
        "passenger_itineraries": sorted(
            item.itinerary_id for item in columns.passenger_itineraries
        ),
        "costs": costs.model_dump(mode="json"),
        "capacity": capacity.model_dump(mode="json"),
        "scope": (
            {
                "direct_flight_ids": list(scope.direct_flight_ids),
                "flight_ids": list(scope.flight_ids),
                "aircraft_ids": list(scope.aircraft_ids),
                "crew_ids": list(scope.crew_ids),
                "passenger_group_ids": list(scope.passenger_group_ids),
                "flight_option_ids": list(scope.flight_option_ids),
                "aircraft_string_ids": list(scope.aircraft_string_ids),
                "crew_pairing_ids": list(scope.crew_pairing_ids),
                "passenger_itinerary_ids": list(scope.passenger_itinerary_ids),
                "propagation_reasons": dict(scope.propagation_reasons),
                "iteration_count": scope.iteration_count,
            }
            if scope is not None
            else None
        ),
        "config": config.model_dump(mode="json"),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def recompute_benders_solution_audit(
    scenario: Scenario,
    columns: RecoveryColumns,
    capacity_profile: PassengerCapacityProfile,
    costs: FixedColumnCostConfig,
    x_values: Mapping[str, float],
    y_values: Mapping[str, float],
    z_values: Mapping[str, float],
    w_values: Mapping[str, float],
    *,
    solver_factory: Callable[[], SolverAdapter],
    scope: RecoveryScope | None = None,
) -> dict[str, Any]:
    """Reuse the integrated model metadata to audit a Benders incumbent."""

    solver = solver_factory()
    try:
        request = IntegratedRecoveryRequest(
            scenario.scenario_id,
            costs.cost_profile_id,
            capacity_profile.capacity_profile_id,
        )
        model = build_integrated_fixed_column_oracle(
            scenario,
            columns,
            request,
            capacity_profile,
            costs,
            solver,
            scope=scope,
        )
        return recompute_integrated_diagnostics(
            model, x_values, y_values, z_values, w_values
        )
    finally:
        solver.close()


def _empty_result(
    status: BendersStatus,
    iterations: Sequence[BendersIterationRecord],
    cuts: Sequence[BendersCut],
    *,
    lower_bound: float | None,
    incumbent: _Incumbent | None,
    diagnostics: Mapping[str, Any],
) -> FixedColumnBendersResult:
    empty: Mapping[str, float] = MappingProxyType({})
    chosen = incumbent
    return FixedColumnBendersResult(
        status=status,
        objective_value=chosen.objective if chosen is not None else None,
        lower_bound=lower_bound,
        upper_bound=chosen.objective if chosen is not None else None,
        iterations=tuple(iterations),
        cuts=tuple(cuts),
        x_values=chosen.x_values if chosen is not None else empty,
        y_values=chosen.y_values if chosen is not None else empty,
        z_values=chosen.z_values if chosen is not None else empty,
        w_values=chosen.w_values if chosen is not None else empty,
        selected_flight_options=(
            chosen.schedule_signature if chosen is not None else ()
        ),
        selected_aircraft_strings=(
            tuple(key for key, value in chosen.y_values.items() if value > 0.5)
            if chosen is not None
            else ()
        ),
        selected_crew_pairings=(
            tuple(key for key, value in chosen.z_values.items() if value > 0.5)
            if chosen is not None
            else ()
        ),
        selected_passenger_itineraries=(
            tuple(key for key, value in chosen.w_values.items() if value > 0.5)
            if chosen is not None
            else ()
        ),
        diagnostics=MappingProxyType(dict(diagnostics)),
    )


def solve_fixed_column_benders(
    scenario_data: Any,
    columns_data: Any,
    capacity_profile: PassengerCapacityProfile,
    costs: FixedColumnCostConfig,
    config: FixedColumnBendersConfig,
    *,
    solver_factory: Callable[[], SolverAdapter],
    scope: RecoveryScope | None = None,
    solver_parameters: Mapping[str, bool | int | float | str] | None = None,
) -> FixedColumnBendersResult:
    """Solve the immutable candidate universe with exact-schedule logic cuts."""

    scenario, columns = _validated_inputs(scenario_data, columns_data, capacity_profile)
    if scope is not None:
        try:
            validate_recovery_scope(scenario, columns, scope)
        except (KeyError, ValueError) as exc:
            raise FixedColumnBendersError(f"scope validation failed: {exc}") from exc
    restricted = build_scope_restricted_columns(scenario, columns, scope)
    bounds = compute_benders_big_m(scenario, restricted, costs)
    fingerprint = _input_fingerprint(
        scenario, columns, costs, capacity_profile, scope, config
    )
    initial_fingerprint = fingerprint
    cuts: list[BendersCut] = []
    cut_keys: set[tuple[str, str | None, tuple[str, ...]]] = set()
    iterations: list[BendersIterationRecord] = []
    incumbent: _Incumbent | None = None
    lower_bound = -math.inf
    solve_counts = {item.value: 0 for item in BendersSubproblem}
    visited: set[tuple[str, ...]] = set()
    terminal_reason = "max_iterations"

    for iteration in range(1, config.max_iterations + 1):
        solver = solver_factory()
        try:
            master = build_fixed_column_benders_master(
                scenario,
                columns,
                costs,
                config,
                cuts,
                solver,
                scope=scope,
            )
            outcome = solver.solve(solver_parameters)
            if outcome.status is SolverStatus.INFEASIBLE:
                terminal_reason = "master_infeasible"
                status = (
                    BendersStatus.OPTIMAL
                    if incumbent is not None
                    else BendersStatus.INFEASIBLE
                )
                if incumbent is not None:
                    lower_bound = incumbent.objective
                return _empty_result(
                    status,
                    iterations,
                    cuts,
                    lower_bound=(lower_bound if math.isfinite(lower_bound) else None),
                    incumbent=incumbent,
                    diagnostics={
                        "algorithm": config.algorithm,
                        "implementation": "logic_based_fixed_column_benders",
                        "terminal_reason": terminal_reason,
                        "input_fingerprint": fingerprint,
                        "big_m": bounds.to_dict(),
                        "visited_schedule_count": len(visited),
                        "subproblem_solve_counts": solve_counts,
                    },
                )
            if outcome.status is not SolverStatus.OPTIMAL:
                terminal_reason = f"master_nonoptimal:{outcome.status.value}"
                return _empty_result(
                    BendersStatus.ABORTED,
                    iterations,
                    cuts,
                    lower_bound=(lower_bound if math.isfinite(lower_bound) else None),
                    incumbent=incumbent,
                    diagnostics={
                        "algorithm": config.algorithm,
                        "terminal_reason": terminal_reason,
                        "iteration": iteration,
                        "input_fingerprint": fingerprint,
                        "big_m": bounds.to_dict(),
                    },
                )
            if outcome.objective_value is None:
                raise FixedColumnBendersError(
                    f"iteration {iteration}: optimal master has no objective"
                )
            x_values = MappingProxyType(
                {
                    option_id: solver.get_variable_value(variable)
                    for option_id, variable in master.srm_model.variables.items()
                }
            )
            signature = schedule_signature(scenario, columns, x_values)
            master_objective = float(outcome.objective_value)
            lower_bound = max(lower_bound, master_objective)
            schedule_cost = sum(
                master.srm_model.option_costs[option_id] * value
                for option_id, value in x_values.items()
            )
        finally:
            solver.close()

        visited.add(signature)
        option_by_id = {item.option_id: item for item in columns.flight_options}
        required_operated = tuple(
            option_id
            for option_id in signature
            if option_by_id[option_id].operation_type is FlightOperationType.OPERATE
        )
        subresults = _solve_subproblems(
            scenario,
            columns,
            restricted,
            required_operated,
            capacity_profile,
            costs,
            config,
            solver_factory,
            solver_parameters,
            iteration=iteration,
            schedule=signature,
        )
        for item in BendersSubproblem:
            if _enabled(config, item):
                solve_counts[item.value] += 1

        invalid = [
            item
            for item, result in subresults.items()
            if result.status
            not in {None, SolverStatus.OPTIMAL, SolverStatus.INFEASIBLE}
        ]
        if invalid:
            reason = ",".join(
                f"{item.value}:{_status_text(subresults[item])}" for item in invalid
            )
            terminal_reason = f"subproblem_nonoptimal:{reason}"
            return _empty_result(
                BendersStatus.ABORTED,
                iterations,
                cuts,
                lower_bound=lower_bound,
                incumbent=incumbent,
                diagnostics={
                    "algorithm": config.algorithm,
                    "terminal_reason": terminal_reason,
                    "iteration": iteration,
                    "schedule_signature": signature,
                    "input_fingerprint": fingerprint,
                    "big_m": bounds.to_dict(),
                    "subproblem_solve_counts": solve_counts,
                },
            )
        infeasible = tuple(
            item
            for item, result in subresults.items()
            if result.status is SolverStatus.INFEASIBLE
        )
        feasibility_added = 0
        optimality_added = 0
        candidate_upper: float | None = None
        if infeasible:
            cut = BendersCut(BendersCutType.FEASIBILITY, None, signature)
            if cut.key not in cut_keys:
                cuts.append(cut)
                cut_keys.add(cut.key)
                feasibility_added = 1
        else:
            recourse = sum(result.objective or 0.0 for result in subresults.values())
            candidate_upper = schedule_cost + recourse
            y_values = subresults[BendersSubproblem.ARM].values
            z_values = subresults[BendersSubproblem.CRM].values
            w_values = subresults[BendersSubproblem.PRM].values
            if incumbent is None or candidate_upper < (
                incumbent.objective - BENDERS_FEASIBILITY_TOLERANCE
            ):
                incumbent = _Incumbent(
                    candidate_upper,
                    x_values,
                    y_values,
                    z_values,
                    w_values,
                    signature,
                )
            for item in BendersSubproblem:
                if not _enabled(config, item):
                    continue
                objective = subresults[item].objective
                assert objective is not None
                cut = BendersCut(
                    BendersCutType.OPTIMALITY,
                    item,
                    signature,
                    float(objective),
                    bounds.for_subproblem(item),
                )
                if cut.key not in cut_keys:
                    cuts.append(cut)
                    cut_keys.add(cut.key)
                    optimality_added += 1

        upper_bound = incumbent.objective if incumbent is not None else None
        absolute_gap = (
            max(0.0, upper_bound - lower_bound) if upper_bound is not None else None
        )
        relative_gap = (
            absolute_gap / max(1.0, abs(upper_bound))
            if absolute_gap is not None and upper_bound is not None
            else None
        )
        iterations.append(
            BendersIterationRecord(
                iteration=iteration,
                master_objective=master_objective,
                lower_bound=lower_bound,
                candidate_upper_bound=candidate_upper,
                incumbent_upper_bound=upper_bound,
                absolute_gap=absolute_gap,
                relative_gap=relative_gap,
                schedule_signature=signature,
                arm_status=_status_text(subresults[BendersSubproblem.ARM]),
                crm_status=_status_text(subresults[BendersSubproblem.CRM]),
                prm_status=_status_text(subresults[BendersSubproblem.PRM]),
                arm_objective=subresults[BendersSubproblem.ARM].objective,
                crm_objective=subresults[BendersSubproblem.CRM].objective,
                prm_objective=subresults[BendersSubproblem.PRM].objective,
                infeasible_subproblems=tuple(item.value for item in infeasible),
                feasibility_cuts_added=feasibility_added,
                optimality_cuts_added=optimality_added,
                total_unique_cuts=len(cuts),
            )
        )
        converged = (
            incumbent is not None
            and absolute_gap is not None
            and relative_gap is not None
            and (
                absolute_gap <= config.absolute_gap_tolerance
                or relative_gap <= config.relative_gap_tolerance
            )
        )
        if not converged:
            continue

        terminal_reason = "gap_tolerance"
        audit: dict[str, Any] | None = None
        all_components = all(_enabled(config, item) for item in BendersSubproblem)
        if all_components:
            audit = recompute_benders_solution_audit(
                scenario,
                columns,
                capacity_profile,
                costs,
                incumbent.x_values,
                incumbent.y_values,
                incumbent.z_values,
                incumbent.w_values,
                solver_factory=solver_factory,
                scope=scope,
            )
            if not audit["all_constraints_satisfied"]:
                raise FixedColumnBendersError(
                    f"iteration {iteration}, schedule={signature}: integrated audit failed"
                )
            audited_objective = float(audit["objective_breakdown"]["grand_total"])
            if not math.isclose(
                audited_objective,
                incumbent.objective,
                rel_tol=BENDERS_FEASIBILITY_TOLERANCE,
                abs_tol=BENDERS_FEASIBILITY_TOLERANCE,
            ):
                raise FixedColumnBendersError(
                    f"iteration {iteration}, schedule={signature}: objective mismatch; "
                    f"Benders={incumbent.objective}, audit={audited_objective}"
                )
        if (
            _input_fingerprint(
                scenario, columns, costs, capacity_profile, scope, config
            )
            != initial_fingerprint
        ):
            raise FixedColumnBendersError(
                "fixed candidate universe changed during solve"
            )
        cut_counts = {
            "feasibility": sum(
                item.cut_type is BendersCutType.FEASIBILITY for item in cuts
            ),
            **{
                f"{subproblem.value}_optimality": sum(
                    item.cut_type is BendersCutType.OPTIMALITY
                    and item.subproblem is subproblem
                    for item in cuts
                )
                for subproblem in BendersSubproblem
            },
        }
        return _empty_result(
            BendersStatus.OPTIMAL,
            iterations,
            cuts,
            lower_bound=lower_bound,
            incumbent=incumbent,
            diagnostics={
                "algorithm": config.algorithm,
                "implementation": "logic_based_fixed_column_benders",
                "classical_lp_dual_cuts": False,
                "candidate_universe_frozen": True,
                "terminal_reason": terminal_reason,
                "input_fingerprint": fingerprint,
                "big_m": bounds.to_dict(),
                "visited_schedule_count": len(visited),
                "subproblem_solve_counts": solve_counts,
                "cut_counts": cut_counts,
                "scope_restricted_candidate_counts": {
                    "aircraft_strings": len(restricted.aircraft_strings),
                    "crew_pairings": len(restricted.crew_pairings),
                    "passenger_itineraries": len(restricted.passenger_itineraries),
                },
                "integrated_audit": audit,
            },
        )

    return _empty_result(
        BendersStatus.NOT_CONVERGED,
        iterations,
        cuts,
        lower_bound=(lower_bound if math.isfinite(lower_bound) else None),
        incumbent=incumbent,
        diagnostics={
            "algorithm": config.algorithm,
            "implementation": "logic_based_fixed_column_benders",
            "terminal_reason": terminal_reason,
            "max_iterations": config.max_iterations,
            "input_fingerprint": fingerprint,
            "big_m": bounds.to_dict(),
            "visited_schedule_count": len(visited),
            "subproblem_solve_counts": solve_counts,
        },
    )
