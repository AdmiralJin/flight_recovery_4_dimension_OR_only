from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from enum import Enum
from time import perf_counter
from types import MappingProxyType
from typing import Any

from backend.config import (
    AircraftStringColumnGenerationConfig,
    BendersColumnGenerationConfig,
    CrewPairingColumnGenerationConfig,
    CrewPairingGenerationConfig,
    FixedColumnCostConfig,
    FlightStringGenerationConfig,
    PassengerCapacityError,
    PassengerCapacityProfile,
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

from .aircraft_string_column_generation import (
    AircraftStringColumnGenerationResult,
    AircraftStringColumnGenerationStatus,
    solve_aircraft_string_column_generation,
)
from .arm import AircraftRecoveryRequest, solve_fixed_column_arm
from .benders import BendersCutType, BendersSubproblem, schedule_signature
from .crm import CrewRecoveryRequest, solve_fixed_column_crm
from .crew_pairing_column_generation import (
    CrewPairingColumnGenerationResult,
    CrewPairingColumnGenerationStatus,
    solve_crew_pairing_column_generation,
)
from .integrated_oracle import (
    IntegratedRecoveryRequest,
    build_integrated_fixed_column_oracle,
    recompute_integrated_diagnostics,
)
from .prm import PassengerRecoveryRequest, solve_fixed_column_prm
from .scope import RecoveryScope
from .srm import FixedColumnSrmModel, build_fixed_column_srm


BENDERS_CG_MASTER_MODEL_NAME = "benders_column_generation_master"
BENDERS_CG_FEASIBILITY_TOLERANCE = 1e-6


class BendersCgStatus(str, Enum):
    OPTIMAL = "optimal"
    INFEASIBLE = "infeasible"
    NOT_CONVERGED = "not_converged"
    INTEGRALITY_REQUIRED = "integrality_required"
    ABORTED = "aborted"


class BendersCgCutSource(str, Enum):
    AIRCRAFT_FULL_LP = "aircraft_full_lp"
    CREW_FULL_LP = "crew_full_lp"
    PASSENGER_EXACT_MIP = "passenger_exact_mip"
    AIRCRAFT_LP_INFEASIBILITY = "aircraft_lp_infeasibility"
    CREW_LP_INFEASIBILITY = "crew_lp_infeasibility"
    PASSENGER_MIP_INFEASIBILITY = "passenger_mip_infeasibility"


class BendersColumnGenerationError(ValueError):
    """Phase 11 cannot execute without violating its bound contract."""


_OPTIMAL_SOURCE = {
    BendersSubproblem.ARM: BendersCgCutSource.AIRCRAFT_FULL_LP,
    BendersSubproblem.CRM: BendersCgCutSource.CREW_FULL_LP,
    BendersSubproblem.PRM: BendersCgCutSource.PASSENGER_EXACT_MIP,
}
_INFEASIBLE_SOURCES = {
    BendersCgCutSource.AIRCRAFT_LP_INFEASIBILITY,
    BendersCgCutSource.CREW_LP_INFEASIBILITY,
    BendersCgCutSource.PASSENGER_MIP_INFEASIBILITY,
}


@dataclass(frozen=True)
class BendersCgCut:
    cut_type: BendersCutType
    subproblem: BendersSubproblem | None
    schedule_signature: tuple[str, ...]
    recourse_lower_bound: float | None
    conditional_m: float | None
    source: BendersCgCutSource
    implicit_universe_fingerprint: str
    certificate_id: str

    def __post_init__(self) -> None:
        signature = tuple(self.schedule_signature)
        if not signature or any(not item for item in signature):
            raise BendersColumnGenerationError("cut requires a non-empty schedule")
        if len(signature) != len(set(signature)):
            raise BendersColumnGenerationError("cut schedule must contain unique IDs")
        object.__setattr__(self, "schedule_signature", signature)
        if not self.implicit_universe_fingerprint or not self.certificate_id:
            raise BendersColumnGenerationError("cut provenance must not be empty")
        if self.cut_type is BendersCutType.FEASIBILITY:
            if self.subproblem is not None:
                raise BendersColumnGenerationError(
                    "schedule no-good cannot target a theta subproblem"
                )
            if self.source not in _INFEASIBLE_SOURCES:
                raise BendersColumnGenerationError(
                    "feasibility cut requires certified infeasibility provenance"
                )
            if self.recourse_lower_bound is not None or self.conditional_m is not None:
                raise BendersColumnGenerationError(
                    "feasibility cut cannot carry a recourse lower bound"
                )
            return
        if (
            self.subproblem is None
            or _OPTIMAL_SOURCE[self.subproblem] is not self.source
        ):
            raise BendersColumnGenerationError(
                "optimality cut source does not match its subproblem"
            )
        value = self.recourse_lower_bound
        conditional_m = self.conditional_m
        if value is None or conditional_m is None:
            raise BendersColumnGenerationError(
                "optimality cut requires recourse_lower_bound and conditional_m"
            )
        if not math.isfinite(value) or value < 0.0:
            raise BendersColumnGenerationError(
                "recourse_lower_bound must be finite and nonnegative"
            )
        if not math.isfinite(conditional_m) or conditional_m < value:
            raise BendersColumnGenerationError(
                "conditional_m must be finite and at least the lower bound"
            )

    @property
    def key(self) -> tuple[str, str | None, tuple[str, ...], str]:
        return (
            self.cut_type.value,
            self.subproblem.value if self.subproblem is not None else None,
            self.schedule_signature,
            self.implicit_universe_fingerprint,
        )

    @property
    def cut_id(self) -> str:
        digest = hashlib.sha256(
            json.dumps(self.key, separators=(",", ":")).encode("utf-8")
        ).hexdigest()[:16]
        prefix = "F" if self.cut_type is BendersCutType.FEASIBILITY else "O"
        owner = self.subproblem.value.upper() if self.subproblem else "SCHEDULE"
        return f"BCG_{prefix}_{owner}_{digest}"


@dataclass(frozen=True)
class BendersCgRecourseCertificate:
    certificate_id: str
    schedule_signature: tuple[str, ...]
    implicit_universe_fingerprint: str
    aircraft_cg_status: str
    aircraft_lp_objective: float | None
    aircraft_column_count: int
    aircraft_pool_fingerprint: str | None
    aircraft_phase_one_iterations: int
    aircraft_phase_two_iterations: int
    aircraft_binary_status: str
    aircraft_binary_objective: float | None
    aircraft_integrality_certified: bool
    crew_cg_status: str
    crew_lp_objective: float | None
    crew_column_count: int
    crew_pool_fingerprint: str | None
    crew_phase_one_iterations: int
    crew_phase_two_iterations: int
    crew_binary_status: str
    crew_binary_objective: float | None
    crew_integrality_certified: bool
    prm_status: str
    prm_objective: float | None


@dataclass(frozen=True)
class BendersCgIteration:
    iteration: int
    schedule_signature: tuple[str, ...]
    master_objective: float
    lower_bound: float
    candidate_upper_bound: float | None
    incumbent_upper_bound: float | None
    absolute_gap: float | None
    relative_gap: float | None
    aircraft_cg_status: str
    aircraft_lp_objective: float | None
    aircraft_column_count: int
    aircraft_binary_objective: float | None
    crew_cg_status: str
    crew_lp_objective: float | None
    crew_column_count: int
    crew_binary_objective: float | None
    prm_status: str
    prm_objective: float | None
    feasibility_cuts_added: int
    aircraft_cuts_added: int
    crew_cuts_added: int
    passenger_cuts_added: int
    total_unique_cuts: int
    runtime_seconds: float


@dataclass(frozen=True)
class BendersCgResult:
    status: BendersCgStatus
    objective_value: float | None
    lower_bound: float | None
    upper_bound: float | None
    iterations: tuple[BendersCgIteration, ...]
    cuts: tuple[BendersCgCut, ...]
    certificates: tuple[BendersCgRecourseCertificate, ...]
    x_values: Mapping[str, float] = field(repr=False)
    y_values: Mapping[str, float] = field(repr=False)
    z_values: Mapping[str, float] = field(repr=False)
    w_values: Mapping[str, float] = field(repr=False)
    selected_flight_options: tuple[str, ...]
    selected_aircraft_strings: tuple[str, ...]
    selected_crew_pairings: tuple[str, ...]
    selected_passenger_itineraries: tuple[str, ...]
    diagnostics: Mapping[str, Any]
    solution_columns: RecoveryColumns | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        for name in ("x_values", "y_values", "z_values", "w_values", "diagnostics"):
            object.__setattr__(self, name, MappingProxyType(dict(getattr(self, name))))

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "objective_value": self.objective_value,
            "lower_bound": self.lower_bound,
            "upper_bound": self.upper_bound,
            "iterations": [asdict(item) for item in self.iterations],
            "cuts": [
                {
                    **asdict(item),
                    "cut_type": item.cut_type.value,
                    "subproblem": item.subproblem.value if item.subproblem else None,
                    "source": item.source.value,
                    "cut_id": item.cut_id,
                }
                for item in self.cuts
            ],
            "certificates": [asdict(item) for item in self.certificates],
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
class _BendersCgMaster:
    srm_model: FixedColumnSrmModel
    theta_variables: Mapping[BendersSubproblem, VariableHandle]


@dataclass(frozen=True)
class _Incumbent:
    objective: float
    schedule_signature: tuple[str, ...]
    columns: RecoveryColumns
    x_values: Mapping[str, float]
    y_values: Mapping[str, float]
    z_values: Mapping[str, float]
    w_values: Mapping[str, float]


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
        raise BendersColumnGenerationError(
            _validation_message("scenario", scenario_issues)
        )
    columns, column_issues = validate_recovery_columns(scenario, columns_data)
    if columns is None or column_issues:
        raise BendersColumnGenerationError(
            _validation_message("columns", column_issues)
        )
    if columns.aircraft_strings or columns.crew_pairings:
        raise BendersColumnGenerationError(
            "formal Phase 11 input must not contain pre-generated aircraft strings "
            "or crew pairings"
        )
    try:
        validate_passenger_capacity_profile(capacity_profile, scenario, columns)
    except PassengerCapacityError as exc:
        raise BendersColumnGenerationError(
            f"capacity profile validation failed: {exc}"
        ) from exc
    return scenario, columns


def _sorted_models(items: Sequence[Any], id_name: str) -> list[dict[str, Any]]:
    return [
        item.model_dump(mode="json")
        for item in sorted(items, key=lambda value: getattr(value, id_name))
    ]


def benders_cg_implicit_universe_fingerprint(
    scenario: Scenario,
    columns: RecoveryColumns,
    capacity_profile: PassengerCapacityProfile,
    costs: FixedColumnCostConfig,
    string_config: FlightStringGenerationConfig,
    pairing_config: CrewPairingGenerationConfig,
    aircraft_cg_config: AircraftStringColumnGenerationConfig,
    crew_cg_config: CrewPairingColumnGenerationConfig,
    config: BendersColumnGenerationConfig,
    *,
    scope: RecoveryScope | None = None,
) -> str:
    """Fingerprint the implicit universe, excluding materialized dynamic pools."""

    scenario_payload = scenario.model_dump(mode="json")
    for field_name, id_name in (
        ("airports", "airport_id"),
        ("flights", "flight_id"),
        ("aircraft", "tail_id"),
        ("crew", "crew_id"),
        ("passengers", "pax_group_id"),
    ):
        scenario_payload[field_name] = _sorted_models(
            getattr(scenario, field_name), id_name
        )
    scenario_payload["airport_intervals"] = sorted(
        scenario_payload["airport_intervals"],
        key=lambda value: (
            value["airport"],
            value["start_time"],
            value["end_time"],
        ),
    )
    scenario_payload["disruptions"] = sorted(
        scenario_payload["disruptions"],
        key=lambda value: json.dumps(value, sort_keys=True, separators=(",", ":")),
    )
    payload = {
        "scenario": scenario_payload,
        "flight_options": _sorted_models(columns.flight_options, "option_id"),
        "passenger_itineraries": _sorted_models(
            columns.passenger_itineraries, "itinerary_id"
        ),
        "capacity": capacity_profile.model_dump(mode="json"),
        "costs": costs.model_dump(mode="json"),
        "string_config": string_config.model_dump(mode="json"),
        "pairing_config": pairing_config.model_dump(mode="json"),
        "aircraft_cg_config": aircraft_cg_config.model_dump(mode="json"),
        "crew_cg_config": crew_cg_config.model_dump(mode="json"),
        "phase11_config": config.model_dump(mode="json"),
        "scope_mode": "full" if scope is None else "dynamic",
    }
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _pool_fingerprint(items: Sequence[Any]) -> str:
    payload = sorted(
        (item.model_dump(mode="json") for item in items),
        key=lambda value: json.dumps(value, sort_keys=True, separators=(",", ":")),
    )
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _certificate_id(
    fingerprint: str, schedule: Sequence[str], values: Mapping[str, Any]
) -> str:
    payload = {
        "fingerprint": fingerprint,
        "schedule": list(schedule),
        "values": dict(values),
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:20]
    return f"BCG_CERT_{digest}"


def _validate_cut(
    cut: BendersCgCut,
    fingerprint: str,
    scenario: Scenario,
    columns: RecoveryColumns,
) -> None:
    if cut.implicit_universe_fingerprint != fingerprint:
        raise BendersColumnGenerationError(
            f"cut {cut.cut_id} belongs to a different implicit universe"
        )
    schedule_ids = {
        item.option_id
        for item in columns.flight_options
        if item.operation_type
        in {FlightOperationType.OPERATE, FlightOperationType.CANCEL}
    }
    unknown = set(cut.schedule_signature) - schedule_ids
    if unknown or len(cut.schedule_signature) != len(scenario.flights):
        raise BendersColumnGenerationError(
            f"invalid cut schedule: unknown={sorted(unknown)}, "
            f"size={len(cut.schedule_signature)}"
        )
    canonical = schedule_signature(
        scenario,
        columns,
        {item_id: float(item_id in cut.schedule_signature) for item_id in schedule_ids},
    )
    if canonical != cut.schedule_signature:
        raise BendersColumnGenerationError("cut schedule is not canonical")


def _build_master(
    scenario: Scenario,
    columns: RecoveryColumns,
    costs: FixedColumnCostConfig,
    cuts: Sequence[BendersCgCut],
    fingerprint: str,
    solver: SolverAdapter,
) -> _BendersCgMaster:
    srm = build_fixed_column_srm(scenario, columns, costs, solver)
    theta = {
        item: solver.add_variable(
            f"theta[{item.value}]",
            lower_bound=0.0,
            variable_type=VariableType.CONTINUOUS,
        )
        for item in BendersSubproblem
    }
    objective = {
        srm.variables[option_id]: value for option_id, value in srm.option_costs.items()
    }
    objective.update({theta[item]: 1.0 for item in BendersSubproblem})
    solver.set_objective(objective, ObjectiveSense.MINIMIZE)

    seen: set[tuple[str, str | None, tuple[str, ...], str]] = set()
    for cut in cuts:
        _validate_cut(cut, fingerprint, scenario, columns)
        if cut.key in seen:
            raise BendersColumnGenerationError(f"duplicate cut key: {cut.key!r}")
        seen.add(cut.key)
        selected = {
            srm.variables[option_id]: 1.0 for option_id in cut.schedule_signature
        }
        if cut.cut_type is BendersCutType.FEASIBILITY:
            solver.add_linear_constraint(
                selected,
                ConstraintSense.LESS_EQUAL,
                float(len(cut.schedule_signature) - 1),
                name=cut.cut_id,
            )
            continue
        assert cut.subproblem is not None
        assert cut.conditional_m is not None
        assert cut.recourse_lower_bound is not None
        coefficients = {variable: -cut.conditional_m for variable in selected}
        coefficients[theta[cut.subproblem]] = 1.0
        solver.add_linear_constraint(
            coefficients,
            ConstraintSense.GREATER_EQUAL,
            cut.recourse_lower_bound - cut.conditional_m * len(cut.schedule_signature),
            name=cut.cut_id,
        )
    return _BendersCgMaster(srm, MappingProxyType(theta))


def _solve_model(
    solver_factory: Callable[[], SolverAdapter],
    solve: Callable[[SolverAdapter], ModelSolveResult],
) -> ModelSolveResult:
    solver = solver_factory()
    try:
        return solve(solver)
    finally:
        solver.close()


def _selection_values(
    result: ModelSolveResult,
    all_ids: Sequence[str],
    diagnostic_key: str,
) -> Mapping[str, float]:
    selected_by_owner = result.diagnostics.get(diagnostic_key, {})
    if not isinstance(selected_by_owner, Mapping):
        raise BendersColumnGenerationError(
            f"{result.model_name} diagnostics.{diagnostic_key} is not a mapping"
        )
    selected = set(selected_by_owner.values())
    unknown = selected - set(all_ids)
    if unknown:
        raise BendersColumnGenerationError(
            f"{result.model_name} returned unknown candidates: {sorted(unknown)}"
        )
    return MappingProxyType(
        {item_id: float(item_id in selected) for item_id in all_ids}
    )


def _dynamic_columns(
    base: RecoveryColumns,
    aircraft_result: AircraftStringColumnGenerationResult,
    crew_result: CrewPairingColumnGenerationResult,
) -> RecoveryColumns:
    payload = base.model_dump(mode="python")
    payload["aircraft_strings"] = [
        item.model_dump(mode="python") for item in aircraft_result.columns
    ]
    payload["crew_pairings"] = [
        item.model_dump(mode="python") for item in crew_result.columns
    ]
    return RecoveryColumns.model_validate(payload)


def _gaps(
    lower_bound: float, upper_bound: float | None
) -> tuple[float | None, float | None]:
    if upper_bound is None:
        return None, None
    absolute = max(0.0, upper_bound - lower_bound)
    return absolute, absolute / max(1.0, abs(upper_bound))


def _gap_closed(
    absolute: float | None,
    relative: float | None,
    config: BendersColumnGenerationConfig,
) -> bool:
    return (
        absolute is not None
        and relative is not None
        and (
            absolute <= config.absolute_gap_tolerance
            or relative <= config.relative_gap_tolerance
        )
    )


def recompute_benders_cg_audit(
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
    if scope is not None:
        raise BendersColumnGenerationError(
            "UNSUPPORTED_DYNAMIC_SCOPE: Phase 11 v1 requires scope=None"
        )
    solver = solver_factory()
    try:
        request = IntegratedRecoveryRequest(
            scenario.scenario_id,
            costs.cost_profile_id,
            capacity_profile.capacity_profile_id,
        )
        model = build_integrated_fixed_column_oracle(
            scenario, columns, request, capacity_profile, costs, solver
        )
        return recompute_integrated_diagnostics(
            model, x_values, y_values, z_values, w_values
        )
    finally:
        solver.close()


def _result(
    status: BendersCgStatus,
    iterations: Sequence[BendersCgIteration],
    cuts: Sequence[BendersCgCut],
    certificates: Sequence[BendersCgRecourseCertificate],
    lower_bound: float | None,
    incumbent: _Incumbent | None,
    diagnostics: Mapping[str, Any],
) -> BendersCgResult:
    empty: Mapping[str, float] = MappingProxyType({})
    return BendersCgResult(
        status=status,
        objective_value=incumbent.objective if incumbent is not None else None,
        lower_bound=lower_bound,
        upper_bound=incumbent.objective if incumbent is not None else None,
        iterations=tuple(iterations),
        cuts=tuple(cuts),
        certificates=tuple(certificates),
        x_values=incumbent.x_values if incumbent else empty,
        y_values=incumbent.y_values if incumbent else empty,
        z_values=incumbent.z_values if incumbent else empty,
        w_values=incumbent.w_values if incumbent else empty,
        selected_flight_options=(incumbent.schedule_signature if incumbent else ()),
        selected_aircraft_strings=(
            tuple(key for key, value in incumbent.y_values.items() if value > 0.5)
            if incumbent
            else ()
        ),
        selected_crew_pairings=(
            tuple(key for key, value in incumbent.z_values.items() if value > 0.5)
            if incumbent
            else ()
        ),
        selected_passenger_itineraries=(
            tuple(key for key, value in incumbent.w_values.items() if value > 0.5)
            if incumbent
            else ()
        ),
        diagnostics=diagnostics,
        solution_columns=incumbent.columns if incumbent else None,
    )


def solve_benders_with_column_generation(
    scenario_data: Any,
    columns_data: Any,
    capacity_profile: PassengerCapacityProfile,
    costs: FixedColumnCostConfig,
    string_config: FlightStringGenerationConfig,
    pairing_config: CrewPairingGenerationConfig,
    aircraft_cg_config: AircraftStringColumnGenerationConfig,
    crew_cg_config: CrewPairingColumnGenerationConfig,
    config: BendersColumnGenerationConfig,
    *,
    solver_factory: Callable[[], SolverAdapter],
    scope: RecoveryScope | None = None,
    solver_parameters: Mapping[str, bool | int | float | str] | None = None,
    event_sink: Callable[[dict[str, Any]], None] | None = None,
) -> BendersCgResult:
    """Solve Schedule Benders with certified Aircraft/Crew LP pricing."""

    started = perf_counter()
    if scope is not None:
        raise BendersColumnGenerationError(
            "UNSUPPORTED_DYNAMIC_SCOPE: Phase 11 v1 requires scope=None"
        )
    if not config.require_full_scope:
        raise BendersColumnGenerationError("Phase 11 v1 requires full-scope config")
    scenario, columns = _validated_inputs(scenario_data, columns_data, capacity_profile)
    fingerprint = benders_cg_implicit_universe_fingerprint(
        scenario,
        columns,
        capacity_profile,
        costs,
        string_config,
        pairing_config,
        aircraft_cg_config,
        crew_cg_config,
        config,
        scope=scope,
    )
    cuts: list[BendersCgCut] = []
    cut_keys: set[tuple[str, str | None, tuple[str, ...], str]] = set()
    certificates: list[BendersCgRecourseCertificate] = []
    certificate_by_schedule: dict[tuple[str, ...], BendersCgRecourseCertificate] = {}
    iterations: list[BendersCgIteration] = []

    def record_iteration(item: BendersCgIteration) -> None:
        iterations.append(item)
        if event_sink is not None:
            event_sink(
                {
                    "stage": "phase11",
                    "type": "benders_iteration",
                    "iteration": item.iteration,
                    "schedule": list(item.schedule_signature),
                    "lower_bound": item.lower_bound,
                    "upper_bound": item.incumbent_upper_bound,
                    "absolute_gap": item.absolute_gap,
                    "relative_gap": item.relative_gap,
                    "metrics": {
                        "master_objective": item.master_objective,
                        "candidate_upper_bound": item.candidate_upper_bound,
                        "aircraft_columns": item.aircraft_column_count,
                        "aircraft_cg_status": item.aircraft_cg_status,
                        "aircraft_lp_objective": item.aircraft_lp_objective,
                        "aircraft_binary_objective": item.aircraft_binary_objective,
                        "crew_columns": item.crew_column_count,
                        "crew_cg_status": item.crew_cg_status,
                        "crew_lp_objective": item.crew_lp_objective,
                        "crew_binary_objective": item.crew_binary_objective,
                        "passenger_status": item.prm_status,
                        "passenger_objective": item.prm_objective,
                        "cuts": item.total_unique_cuts,
                        "feasibility_cuts_added": item.feasibility_cuts_added,
                        "aircraft_cuts_added": item.aircraft_cuts_added,
                        "crew_cuts_added": item.crew_cuts_added,
                        "passenger_cuts_added": item.passenger_cuts_added,
                        "runtime_seconds": item.runtime_seconds,
                    },
                }
            )
    incumbent: _Incumbent | None = None
    lower_bound = -math.inf
    visited: set[tuple[str, ...]] = set()
    metrics = {
        "aircraft_cg_calls": 0,
        "crew_cg_calls": 0,
        "aircraft_phase_one_iterations": 0,
        "aircraft_phase_two_iterations": 0,
        "crew_phase_one_iterations": 0,
        "crew_phase_two_iterations": 0,
        "aircraft_generated_columns": 0,
        "crew_generated_columns": 0,
    }
    terminal_reason = "maximum_iterations_reached"

    def finish(status: BendersCgStatus) -> BendersCgResult:
        nonlocal terminal_reason
        current = benders_cg_implicit_universe_fingerprint(
            scenario,
            columns,
            capacity_profile,
            costs,
            string_config,
            pairing_config,
            aircraft_cg_config,
            crew_cg_config,
            config,
            scope=scope,
        )
        if current != fingerprint:
            raise BendersColumnGenerationError(
                "implicit universe fingerprint changed during solve"
            )
        diagnostics: dict[str, Any] = {
            "algorithm": "schedule_benders_with_aircraft_and_crew_column_generation",
            "terminal_reason": terminal_reason,
            "implicit_universe_fingerprint": fingerprint,
            "visited_schedule_count": len(visited),
            "cut_counts": {
                "feasibility": sum(
                    item.cut_type is BendersCutType.FEASIBILITY for item in cuts
                ),
                "aircraft_full_lp": sum(
                    item.source is BendersCgCutSource.AIRCRAFT_FULL_LP for item in cuts
                ),
                "crew_full_lp": sum(
                    item.source is BendersCgCutSource.CREW_FULL_LP for item in cuts
                ),
                "passenger_exact_mip": sum(
                    item.source is BendersCgCutSource.PASSENGER_EXACT_MIP
                    for item in cuts
                ),
            },
            "metrics": dict(metrics),
            "runtime_seconds": perf_counter() - started,
            "scope_mode": "full",
            "formal_full_enumerators_used": False,
        }
        if status is BendersCgStatus.OPTIMAL:
            if incumbent is None:
                raise BendersColumnGenerationError(
                    "OPTIMAL result requires an integer incumbent"
                )
            audit = recompute_benders_cg_audit(
                scenario,
                incumbent.columns,
                capacity_profile,
                costs,
                incumbent.x_values,
                incumbent.y_values,
                incumbent.z_values,
                incumbent.w_values,
                solver_factory=solver_factory,
            )
            if not audit.get("all_constraints_satisfied"):
                raise BendersColumnGenerationError(
                    "final Integrated audit found a constraint violation"
                )
            audited = float(audit["objective_breakdown"]["grand_total"])
            if not math.isclose(
                audited,
                incumbent.objective,
                rel_tol=BENDERS_CG_FEASIBILITY_TOLERANCE,
                abs_tol=BENDERS_CG_FEASIBILITY_TOLERANCE,
            ):
                raise BendersColumnGenerationError(
                    "final Integrated audit objective differs from incumbent"
                )
            diagnostics["integrated_audit"] = audit
        return _result(
            status,
            iterations,
            cuts,
            certificates,
            lower_bound if math.isfinite(lower_bound) else None,
            incumbent,
            diagnostics,
        )

    for iteration in range(1, config.max_benders_iterations + 1):
        iteration_started = perf_counter()
        solver = solver_factory()
        try:
            master = _build_master(scenario, columns, costs, cuts, fingerprint, solver)
            outcome = solver.solve(solver_parameters)
            if outcome.status is SolverStatus.INFEASIBLE:
                terminal_reason = "master_infeasible"
                return finish(
                    BendersCgStatus.OPTIMAL
                    if incumbent is not None
                    else BendersCgStatus.INFEASIBLE
                )
            if outcome.status is not SolverStatus.OPTIMAL:
                terminal_reason = f"master_nonoptimal:{outcome.status.value}"
                return finish(BendersCgStatus.ABORTED)
            if outcome.objective_value is None:
                raise BendersColumnGenerationError(
                    "optimal master returned no objective"
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

        absolute_gap, relative_gap = _gaps(
            lower_bound, incumbent.objective if incumbent else None
        )
        if _gap_closed(absolute_gap, relative_gap, config):
            previous = certificate_by_schedule.get(signature)
            record_iteration(
                BendersCgIteration(
                    iteration=iteration,
                    schedule_signature=signature,
                    master_objective=master_objective,
                    lower_bound=lower_bound,
                    candidate_upper_bound=None,
                    incumbent_upper_bound=incumbent.objective if incumbent else None,
                    absolute_gap=absolute_gap,
                    relative_gap=relative_gap,
                    aircraft_cg_status=(
                        previous.aircraft_cg_status
                        if previous
                        else "not_run_bound_closed"
                    ),
                    aircraft_lp_objective=(
                        previous.aircraft_lp_objective if previous else None
                    ),
                    aircraft_column_count=(
                        previous.aircraft_column_count if previous else 0
                    ),
                    aircraft_binary_objective=(
                        previous.aircraft_binary_objective if previous else None
                    ),
                    crew_cg_status=(
                        previous.crew_cg_status if previous else "not_run_bound_closed"
                    ),
                    crew_lp_objective=(
                        previous.crew_lp_objective if previous else None
                    ),
                    crew_column_count=previous.crew_column_count if previous else 0,
                    crew_binary_objective=(
                        previous.crew_binary_objective if previous else None
                    ),
                    prm_status=(
                        previous.prm_status if previous else "not_run_bound_closed"
                    ),
                    prm_objective=previous.prm_objective if previous else None,
                    feasibility_cuts_added=0,
                    aircraft_cuts_added=0,
                    crew_cuts_added=0,
                    passenger_cuts_added=0,
                    total_unique_cuts=len(cuts),
                    runtime_seconds=perf_counter() - iteration_started,
                )
            )
            terminal_reason = "bound_gap_closed_before_recourse"
            return finish(BendersCgStatus.OPTIMAL)
        if signature in certificate_by_schedule:
            previous = certificate_by_schedule[signature]
            record_iteration(
                BendersCgIteration(
                    iteration=iteration,
                    schedule_signature=signature,
                    master_objective=master_objective,
                    lower_bound=lower_bound,
                    candidate_upper_bound=None,
                    incumbent_upper_bound=(incumbent.objective if incumbent else None),
                    absolute_gap=absolute_gap,
                    relative_gap=relative_gap,
                    aircraft_cg_status=previous.aircraft_cg_status,
                    aircraft_lp_objective=previous.aircraft_lp_objective,
                    aircraft_column_count=previous.aircraft_column_count,
                    aircraft_binary_objective=previous.aircraft_binary_objective,
                    crew_cg_status=previous.crew_cg_status,
                    crew_lp_objective=previous.crew_lp_objective,
                    crew_column_count=previous.crew_column_count,
                    crew_binary_objective=previous.crew_binary_objective,
                    prm_status=previous.prm_status,
                    prm_objective=previous.prm_objective,
                    feasibility_cuts_added=0,
                    aircraft_cuts_added=0,
                    crew_cuts_added=0,
                    passenger_cuts_added=0,
                    total_unique_cuts=len(cuts),
                    runtime_seconds=perf_counter() - iteration_started,
                )
            )
            if (
                previous.aircraft_integrality_certified
                and previous.crew_integrality_certified
            ):
                terminal_reason = "revisited_exact_schedule_without_bound_closure"
                return finish(BendersCgStatus.ABORTED)
            terminal_reason = "lp_integer_gap_requires_branching"
            return finish(BendersCgStatus.INTEGRALITY_REQUIRED)

        visited.add(signature)
        option_by_id = {item.option_id: item for item in columns.flight_options}
        required_operated = tuple(
            option_id
            for option_id in signature
            if option_by_id[option_id].operation_type is FlightOperationType.OPERATE
        )
        aircraft_request = AircraftRecoveryRequest(
            scenario.scenario_id, required_operated
        )
        crew_request = CrewRecoveryRequest(scenario.scenario_id, required_operated)
        try:
            aircraft = solve_aircraft_string_column_generation(
                scenario,
                columns.flight_options,
                aircraft_request,
                costs,
                string_config,
                aircraft_cg_config,
                solver_factory,
            )
        except Exception as exc:
            raise BendersColumnGenerationError(
                f"iteration {iteration}, aircraft CG failed: {exc}"
            ) from exc
        metrics["aircraft_cg_calls"] += 1
        metrics["aircraft_phase_one_iterations"] += aircraft.phase_one_iterations
        metrics["aircraft_phase_two_iterations"] += aircraft.phase_two_iterations
        metrics["aircraft_generated_columns"] += len(aircraft.columns)
        if aircraft.status is AircraftStringColumnGenerationStatus.NOT_CONVERGED:
            terminal_reason = "aircraft_cg_not_converged"
            return finish(BendersCgStatus.NOT_CONVERGED)
        if aircraft.status is AircraftStringColumnGenerationStatus.ABORTED:
            terminal_reason = f"aircraft_cg_aborted:{aircraft.termination_reason}"
            return finish(BendersCgStatus.ABORTED)

        try:
            crew = solve_crew_pairing_column_generation(
                scenario,
                columns.flight_options,
                crew_request,
                costs,
                pairing_config,
                crew_cg_config,
                solver_factory,
            )
        except Exception as exc:
            raise BendersColumnGenerationError(
                f"iteration {iteration}, crew CG failed: {exc}"
            ) from exc
        metrics["crew_cg_calls"] += 1
        metrics["crew_phase_one_iterations"] += crew.phase_one_iterations
        metrics["crew_phase_two_iterations"] += crew.phase_two_iterations
        metrics["crew_generated_columns"] += len(crew.columns)
        if crew.status is CrewPairingColumnGenerationStatus.NOT_CONVERGED:
            terminal_reason = "crew_cg_not_converged"
            return finish(BendersCgStatus.NOT_CONVERGED)
        if crew.status is CrewPairingColumnGenerationStatus.ABORTED:
            terminal_reason = f"crew_cg_aborted:{crew.termination_reason}"
            return finish(BendersCgStatus.ABORTED)

        prm_request = PassengerRecoveryRequest(
            scenario.scenario_id,
            required_operated,
            capacity_profile.capacity_profile_id,
        )
        try:
            prm = _solve_model(
                solver_factory,
                lambda prm_solver: solve_fixed_column_prm(
                    scenario,
                    columns,
                    prm_request,
                    capacity_profile,
                    costs,
                    prm_solver,
                    solver_parameters=solver_parameters,
                ),
            )
        except Exception as exc:
            raise BendersColumnGenerationError(
                f"iteration {iteration}, PRM failed: {exc}"
            ) from exc
        if prm.status not in {SolverStatus.OPTIMAL, SolverStatus.INFEASIBLE}:
            terminal_reason = f"prm_unexpected_status:{prm.status.value}"
            return finish(BendersCgStatus.ABORTED)

        infeasible_source: BendersCgCutSource | None = None
        if aircraft.status is AircraftStringColumnGenerationStatus.INFEASIBLE:
            infeasible_source = BendersCgCutSource.AIRCRAFT_LP_INFEASIBILITY
        elif crew.status is CrewPairingColumnGenerationStatus.INFEASIBLE:
            infeasible_source = BendersCgCutSource.CREW_LP_INFEASIBILITY
        elif prm.status is SolverStatus.INFEASIBLE:
            infeasible_source = BendersCgCutSource.PASSENGER_MIP_INFEASIBILITY

        aircraft_binary: ModelSolveResult | None = None
        crew_binary: ModelSolveResult | None = None
        dynamic_columns: RecoveryColumns | None = None
        y_values: Mapping[str, float] = MappingProxyType({})
        z_values: Mapping[str, float] = MappingProxyType({})
        w_values: Mapping[str, float] = MappingProxyType({})
        candidate_upper_bound: float | None = None
        aircraft_integral = False
        crew_integral = False

        if infeasible_source is None:
            if aircraft.objective_value is None or crew.objective_value is None:
                raise BendersColumnGenerationError(
                    "pricing-certified OPTIMAL CG result has no objective"
                )
            if aircraft.objective_value < -BENDERS_CG_FEASIBILITY_TOLERANCE:
                raise BendersColumnGenerationError("aircraft LP objective is negative")
            if crew.objective_value < -BENDERS_CG_FEASIBILITY_TOLERANCE:
                raise BendersColumnGenerationError("crew LP objective is negative")
            if prm.objective_value is None or prm.objective_value < 0.0:
                raise BendersColumnGenerationError("optimal PRM objective is invalid")
            try:
                dynamic_columns = _dynamic_columns(columns, aircraft, crew)
                _, dynamic_issues = validate_recovery_columns(scenario, dynamic_columns)
                if dynamic_issues:
                    raise BendersColumnGenerationError(
                        _validation_message("generated columns", dynamic_issues)
                    )
            except Exception as exc:
                if isinstance(exc, BendersColumnGenerationError):
                    raise
                raise BendersColumnGenerationError(
                    f"illegal generated column: {exc}"
                ) from exc
            aircraft_binary = _solve_model(
                solver_factory,
                lambda arm_solver: solve_fixed_column_arm(
                    scenario,
                    dynamic_columns,
                    aircraft_request,
                    costs,
                    arm_solver,
                    solver_parameters=solver_parameters,
                ),
            )
            crew_binary = _solve_model(
                solver_factory,
                lambda crm_solver: solve_fixed_column_crm(
                    scenario,
                    dynamic_columns,
                    crew_request,
                    costs,
                    crm_solver,
                    solver_parameters=solver_parameters,
                ),
            )
            if aircraft_binary.status is SolverStatus.OPTIMAL:
                assert aircraft_binary.objective_value is not None
                y_values = _selection_values(
                    aircraft_binary,
                    [item.string_id for item in aircraft.columns],
                    "selected_string_by_aircraft",
                )
                aircraft_integral = math.isclose(
                    aircraft.objective_value,
                    aircraft_binary.objective_value,
                    rel_tol=config.integrality_tolerance,
                    abs_tol=config.integrality_tolerance,
                )
            if crew_binary.status is SolverStatus.OPTIMAL:
                assert crew_binary.objective_value is not None
                z_values = _selection_values(
                    crew_binary,
                    [item.pairing_id for item in crew.columns],
                    "selected_pairing_by_crew",
                )
                crew_integral = math.isclose(
                    crew.objective_value,
                    crew_binary.objective_value,
                    rel_tol=config.integrality_tolerance,
                    abs_tol=config.integrality_tolerance,
                )
            w_values = _selection_values(
                prm,
                [item.itinerary_id for item in columns.passenger_itineraries],
                "selected_itinerary_by_group",
            )
            if (
                aircraft_binary.status is SolverStatus.OPTIMAL
                and crew_binary.status is SolverStatus.OPTIMAL
            ):
                assert aircraft_binary.objective_value is not None
                assert crew_binary.objective_value is not None
                assert prm.objective_value is not None
                candidate_upper_bound = (
                    schedule_cost
                    + aircraft_binary.objective_value
                    + crew_binary.objective_value
                    + prm.objective_value
                )
                candidate = _Incumbent(
                    candidate_upper_bound,
                    signature,
                    dynamic_columns,
                    x_values,
                    y_values,
                    z_values,
                    w_values,
                )
                if incumbent is None or candidate.objective < incumbent.objective:
                    incumbent = candidate

        cert_values = {
            "aircraft_status": aircraft.status.value,
            "aircraft_lp": aircraft.objective_value,
            "crew_status": crew.status.value,
            "crew_lp": crew.objective_value,
            "prm_status": prm.status.value,
            "prm": prm.objective_value,
        }
        certificate_id = _certificate_id(fingerprint, signature, cert_values)
        certificate = BendersCgRecourseCertificate(
            certificate_id=certificate_id,
            schedule_signature=signature,
            implicit_universe_fingerprint=fingerprint,
            aircraft_cg_status=aircraft.status.value,
            aircraft_lp_objective=aircraft.objective_value,
            aircraft_column_count=len(aircraft.columns),
            aircraft_pool_fingerprint=_pool_fingerprint(aircraft.columns),
            aircraft_phase_one_iterations=aircraft.phase_one_iterations,
            aircraft_phase_two_iterations=aircraft.phase_two_iterations,
            aircraft_binary_status=(
                aircraft_binary.status.value if aircraft_binary else "not_run"
            ),
            aircraft_binary_objective=(
                aircraft_binary.objective_value if aircraft_binary else None
            ),
            aircraft_integrality_certified=aircraft_integral,
            crew_cg_status=crew.status.value,
            crew_lp_objective=crew.objective_value,
            crew_column_count=len(crew.columns),
            crew_pool_fingerprint=_pool_fingerprint(crew.columns),
            crew_phase_one_iterations=crew.phase_one_iterations,
            crew_phase_two_iterations=crew.phase_two_iterations,
            crew_binary_status=(crew_binary.status.value if crew_binary else "not_run"),
            crew_binary_objective=(
                crew_binary.objective_value if crew_binary else None
            ),
            crew_integrality_certified=crew_integral,
            prm_status=prm.status.value,
            prm_objective=prm.objective_value,
        )
        certificate_by_schedule[signature] = certificate
        certificates.append(certificate)

        added = {
            "feasibility": 0,
            "aircraft": 0,
            "crew": 0,
            "passenger": 0,
        }
        new_cuts: list[BendersCgCut] = []
        if infeasible_source is not None:
            new_cuts.append(
                BendersCgCut(
                    BendersCutType.FEASIBILITY,
                    None,
                    signature,
                    None,
                    None,
                    infeasible_source,
                    fingerprint,
                    certificate_id,
                )
            )
            added["feasibility"] = 1
        else:
            assert aircraft.objective_value is not None
            assert crew.objective_value is not None
            assert prm.objective_value is not None
            for owner, value, source, key in (
                (
                    BendersSubproblem.ARM,
                    float(aircraft.objective_value),
                    BendersCgCutSource.AIRCRAFT_FULL_LP,
                    "aircraft",
                ),
                (
                    BendersSubproblem.CRM,
                    float(crew.objective_value),
                    BendersCgCutSource.CREW_FULL_LP,
                    "crew",
                ),
                (
                    BendersSubproblem.PRM,
                    float(prm.objective_value),
                    BendersCgCutSource.PASSENGER_EXACT_MIP,
                    "passenger",
                ),
            ):
                new_cuts.append(
                    BendersCgCut(
                        BendersCutType.OPTIMALITY,
                        owner,
                        signature,
                        value,
                        value,
                        source,
                        fingerprint,
                        certificate_id,
                    )
                )
                added[key] = 1
        for cut in new_cuts:
            if cut.key in cut_keys:
                continue
            cuts.append(cut)
            cut_keys.add(cut.key)

        absolute_gap, relative_gap = _gaps(
            lower_bound, incumbent.objective if incumbent else None
        )
        record_iteration(
            BendersCgIteration(
                iteration=iteration,
                schedule_signature=signature,
                master_objective=master_objective,
                lower_bound=lower_bound,
                candidate_upper_bound=candidate_upper_bound,
                incumbent_upper_bound=incumbent.objective if incumbent else None,
                absolute_gap=absolute_gap,
                relative_gap=relative_gap,
                aircraft_cg_status=aircraft.status.value,
                aircraft_lp_objective=aircraft.objective_value,
                aircraft_column_count=len(aircraft.columns),
                aircraft_binary_objective=(
                    aircraft_binary.objective_value if aircraft_binary else None
                ),
                crew_cg_status=crew.status.value,
                crew_lp_objective=crew.objective_value,
                crew_column_count=len(crew.columns),
                crew_binary_objective=(
                    crew_binary.objective_value if crew_binary else None
                ),
                prm_status=prm.status.value,
                prm_objective=prm.objective_value,
                feasibility_cuts_added=added["feasibility"],
                aircraft_cuts_added=added["aircraft"],
                crew_cuts_added=added["crew"],
                passenger_cuts_added=added["passenger"],
                total_unique_cuts=len(cuts),
                runtime_seconds=perf_counter() - iteration_started,
            )
        )

    return finish(BendersCgStatus.NOT_CONVERGED)
