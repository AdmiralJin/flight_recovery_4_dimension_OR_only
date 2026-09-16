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
    BranchAndPriceConfig,
    CrewPairingColumnGenerationConfig,
    CrewPairingGenerationConfig,
    FixedColumnCostConfig,
    FlightStringGenerationConfig,
    PassengerCapacityProfile,
    schedule_flight_option_cost,
)
from backend.schemas.columns import FlightOperationType, RecoveryColumns
from backend.schemas.scenario import Scenario
from backend.solver import ConstraintSense, SolverAdapter, SolverStatus

from .aircraft_string_branch_and_price import (
    BranchAndPriceStatus,
    solve_aircraft_string_branch_and_price,
)
from .aircraft_string_column_generation import (
    AircraftStringColumnGenerationStatus,
    solve_aircraft_string_column_generation,
)
from .arm import AircraftRecoveryRequest, solve_fixed_column_arm
from .benders import BendersCutType, BendersSubproblem, schedule_signature
from .benders_column_generation import (
    BENDERS_CG_FEASIBILITY_TOLERANCE,
    BendersCgCut,
    BendersCgCutSource,
    BendersCgStatus,
    _build_master,
    _selection_values,
    _solve_model,
    _validated_inputs,
    benders_cg_implicit_universe_fingerprint,
    recompute_benders_cg_audit,
    solve_benders_with_column_generation,
)
from .crm import CrewRecoveryRequest, solve_fixed_column_crm
from .crew_pairing_branch_and_price import solve_crew_pairing_branch_and_price
from .crew_pairing_column_generation import (
    CrewPairingColumnGenerationStatus,
    solve_crew_pairing_column_generation,
)
from .integrated_oracle import IntegratedRecoveryRequest
from .prm import PassengerRecoveryRequest, solve_fixed_column_prm
from .scope import RecoveryScope


class BendersBranchAndPriceStatus(str, Enum):
    OPTIMAL = "optimal"
    INFEASIBLE = "infeasible"
    NOT_CONVERGED = "not_converged"
    ABORTED = "aborted"


class BendersBranchAndPriceError(ValueError):
    """Phase 12 cannot preserve its exact integer-recourse contract."""


@dataclass(frozen=True)
class IntegerRecourseCut:
    schedule_signature: tuple[str, ...]
    owner: BendersSubproblem
    integer_objective: float
    implicit_universe_fingerprint: str
    certificate_id: str

    def __post_init__(self) -> None:
        if not self.schedule_signature or len(self.schedule_signature) != len(
            set(self.schedule_signature)
        ):
            raise BendersBranchAndPriceError(
                "exact recourse cut requires a unique non-empty schedule"
            )
        if not math.isfinite(self.integer_objective) or self.integer_objective < 0.0:
            raise BendersBranchAndPriceError(
                "exact recourse objective must be finite and nonnegative"
            )
        if not self.implicit_universe_fingerprint or not self.certificate_id:
            raise BendersBranchAndPriceError("exact cut provenance must not be empty")

    @property
    def key(self) -> tuple[str, tuple[str, ...], str]:
        return (
            self.owner.value,
            self.schedule_signature,
            self.implicit_universe_fingerprint,
        )

    @property
    def cut_id(self) -> str:
        digest = hashlib.sha256(
            json.dumps(self.key, separators=(",", ":")).encode("utf-8")
        ).hexdigest()[:16]
        return f"BBP_X_{self.owner.value.upper()}_{digest}"


@dataclass(frozen=True)
class IntegerRecourseCertificate:
    certificate_id: str
    schedule_signature: tuple[str, ...]
    owner: BendersSubproblem
    lp_objective: float
    integer_objective: float
    branch_and_price_status: str
    nodes_processed: int
    nodes_pruned_infeasible: int
    nodes_pruned_bound: int
    generated_columns: int
    selected_columns: tuple[str, ...]
    implicit_universe_fingerprint: str
    branching_fingerprint: str
    exact: bool


@dataclass(frozen=True)
class BendersBranchAndPriceIteration:
    iteration: int
    schedule_signature: tuple[str, ...]
    master_objective: float | None
    lower_bound: float | None
    candidate_upper_bound: float | None
    incumbent_upper_bound: float | None
    aircraft_lp_objective: float | None
    aircraft_integer_objective: float | None
    aircraft_branch_nodes: int
    crew_lp_objective: float | None
    crew_integer_objective: float | None
    crew_branch_nodes: int
    passenger_objective: float | None
    lp_cuts_added: int
    exact_cuts_added: int
    feasibility_cuts_added: int
    runtime_seconds: float


@dataclass(frozen=True)
class BendersBranchAndPriceResult:
    status: BendersBranchAndPriceStatus
    objective_value: float | None
    lower_bound: float | None
    upper_bound: float | None
    iterations: tuple[BendersBranchAndPriceIteration, ...]
    exact_cuts: tuple[IntegerRecourseCut, ...]
    certificates: tuple[IntegerRecourseCertificate, ...]
    x_values: Mapping[str, float] = field(repr=False)
    y_values: Mapping[str, float] = field(repr=False)
    z_values: Mapping[str, float] = field(repr=False)
    w_values: Mapping[str, float] = field(repr=False)
    selected_flight_options: tuple[str, ...]
    selected_aircraft_strings: tuple[str, ...]
    selected_crew_pairings: tuple[str, ...]
    selected_passenger_itineraries: tuple[str, ...]
    diagnostics: Mapping[str, Any]

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
            "exact_cuts": [
                {
                    **asdict(item),
                    "owner": item.owner.value,
                    "cut_id": item.cut_id,
                }
                for item in self.exact_cuts
            ],
            "certificates": [
                {**asdict(item), "owner": item.owner.value}
                for item in self.certificates
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
class _ExactIncumbent:
    objective: float
    schedule: tuple[str, ...]
    columns: RecoveryColumns
    x_values: Mapping[str, float]
    y_values: Mapping[str, float]
    z_values: Mapping[str, float]
    w_values: Mapping[str, float]


def _phase12_fingerprint(phase11_fingerprint: str, config: BranchAndPriceConfig) -> str:
    payload = {
        "phase11": phase11_fingerprint,
        "branch_and_price": config.model_dump(mode="json"),
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _certificate_id(
    fingerprint: str,
    schedule: Sequence[str],
    owner: BendersSubproblem,
    lp_value: float,
    integer_value: float,
) -> str:
    payload = [fingerprint, list(schedule), owner.value, lp_value, integer_value]
    digest = hashlib.sha256(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:20]
    return f"BBP_CERT_{digest}"


def _dynamic_columns(
    base: RecoveryColumns, aircraft_columns: Sequence[Any], crew_columns: Sequence[Any]
) -> RecoveryColumns:
    return base.model_copy(
        update={
            "aircraft_strings": list(aircraft_columns),
            "crew_pairings": list(crew_columns),
        }
    )


def _add_exact_constraints(
    solver: SolverAdapter, master: Any, cuts: Sequence[IntegerRecourseCut]
) -> None:
    for cut in cuts:
        value = cut.integer_objective
        coefficients = {
            master.srm_model.variables[option_id]: -value
            for option_id in cut.schedule_signature
        }
        coefficients[master.theta_variables[cut.owner]] = 1.0
        solver.add_linear_constraint(
            coefficients,
            ConstraintSense.GREATER_EQUAL,
            value - value * len(cut.schedule_signature),
            name=cut.cut_id,
        )


def _lp_cut(
    owner: BendersSubproblem,
    schedule: tuple[str, ...],
    value: float,
    phase11_fingerprint: str,
    certificate_id: str,
) -> BendersCgCut:
    source = {
        BendersSubproblem.ARM: BendersCgCutSource.AIRCRAFT_FULL_LP,
        BendersSubproblem.CRM: BendersCgCutSource.CREW_FULL_LP,
        BendersSubproblem.PRM: BendersCgCutSource.PASSENGER_EXACT_MIP,
    }[owner]
    return BendersCgCut(
        BendersCutType.OPTIMALITY,
        owner,
        schedule,
        value,
        value,
        source,
        phase11_fingerprint,
        certificate_id,
    )


def _feasibility_cut(
    schedule: tuple[str, ...],
    source: BendersCgCutSource,
    phase11_fingerprint: str,
    certificate_id: str,
) -> BendersCgCut:
    return BendersCgCut(
        BendersCutType.FEASIBILITY,
        None,
        schedule,
        None,
        None,
        source,
        phase11_fingerprint,
        certificate_id,
    )


def solve_benders_with_branch_and_price(
    scenario_data: Any,
    columns_data: Any,
    capacity_profile: PassengerCapacityProfile,
    costs: FixedColumnCostConfig,
    string_config: FlightStringGenerationConfig,
    pairing_config: CrewPairingGenerationConfig,
    aircraft_cg_config: AircraftStringColumnGenerationConfig,
    crew_cg_config: CrewPairingColumnGenerationConfig,
    benders_config: BendersColumnGenerationConfig,
    branch_config: BranchAndPriceConfig,
    *,
    solver_factory: Callable[[], SolverAdapter],
    scope: RecoveryScope | None = None,
    solver_parameters: Mapping[str, bool | int | float | str] | None = None,
) -> BendersBranchAndPriceResult:
    """Close Phase 11 integer gaps with exact implicit-column B&P recourse."""

    started = perf_counter()
    if scope is not None:
        raise BendersBranchAndPriceError(
            "UNSUPPORTED_DYNAMIC_SCOPE: Phase 12 v1 requires scope=None"
        )
    scenario, columns = _validated_inputs(scenario_data, columns_data, capacity_profile)
    phase11_fingerprint = benders_cg_implicit_universe_fingerprint(
        scenario,
        columns,
        capacity_profile,
        costs,
        string_config,
        pairing_config,
        aircraft_cg_config,
        crew_cg_config,
        benders_config,
    )
    fingerprint = _phase12_fingerprint(phase11_fingerprint, branch_config)
    phase11 = solve_benders_with_column_generation(
        scenario,
        columns,
        capacity_profile,
        costs,
        string_config,
        pairing_config,
        aircraft_cg_config,
        crew_cg_config,
        benders_config,
        solver_factory=solver_factory,
        solver_parameters=solver_parameters,
    )
    empty: Mapping[str, float] = MappingProxyType({})
    phase11_metrics = phase11.diagnostics.get("metrics", {})

    if phase11.status is BendersCgStatus.OPTIMAL:
        diagnostics = {
            "algorithm": "phase11_lp_exactness_then_branch_and_price",
            "terminal_reason": "phase11_lp_integer_bound_closed",
            "implicit_universe_fingerprint": fingerprint,
            "phase11_status": phase11.status.value,
            "phase11_iterations": len(phase11.iterations),
            "phase11_diagnostics": dict(phase11.diagnostics),
            "metrics": {
                "benders_master_iterations": len(phase11.iterations),
                "visited_schedules": phase11.diagnostics.get(
                    "visited_schedule_count", 0
                ),
                "schedules_closed_by_lp_exactness": 1,
                "schedules_requiring_aircraft_branch_and_price": 0,
                "schedules_requiring_crew_branch_and_price": 0,
                "aircraft_branch_and_price_nodes": 0,
                "crew_branch_and_price_nodes": 0,
                "lp_lower_bound_cuts": sum(
                    item.cut_type is BendersCutType.OPTIMALITY for item in phase11.cuts
                ),
                "exact_integer_cuts": 0,
                "feasibility_cuts": sum(
                    item.cut_type is BendersCutType.FEASIBILITY for item in phase11.cuts
                ),
                "initial_lower_bound": (
                    phase11.iterations[0].lower_bound
                    if phase11.iterations
                    else phase11.lower_bound
                ),
                "final_lower_bound": phase11.lower_bound,
                "first_upper_bound": next(
                    (
                        item.incumbent_upper_bound
                        for item in phase11.iterations
                        if item.incumbent_upper_bound is not None
                    ),
                    phase11.upper_bound,
                ),
                "final_upper_bound": phase11.upper_bound,
                "final_gap": (
                    max(0.0, phase11.upper_bound - phase11.lower_bound)
                    if phase11.upper_bound is not None
                    and phase11.lower_bound is not None
                    else None
                ),
            },
            "formal_full_enumerators_used": False,
            "runtime_seconds": perf_counter() - started,
        }
        return BendersBranchAndPriceResult(
            BendersBranchAndPriceStatus.OPTIMAL,
            phase11.objective_value,
            phase11.lower_bound,
            phase11.upper_bound,
            (),
            (),
            (),
            phase11.x_values,
            phase11.y_values,
            phase11.z_values,
            phase11.w_values,
            phase11.selected_flight_options,
            phase11.selected_aircraft_strings,
            phase11.selected_crew_pairings,
            phase11.selected_passenger_itineraries,
            diagnostics,
        )

    terminal_map = {
        BendersCgStatus.INFEASIBLE: BendersBranchAndPriceStatus.INFEASIBLE,
        BendersCgStatus.NOT_CONVERGED: BendersBranchAndPriceStatus.NOT_CONVERGED,
        BendersCgStatus.ABORTED: BendersBranchAndPriceStatus.ABORTED,
    }
    if phase11.status is not BendersCgStatus.INTEGRALITY_REQUIRED:
        status = terminal_map[phase11.status]
        return BendersBranchAndPriceResult(
            status,
            None,
            phase11.lower_bound,
            phase11.upper_bound,
            (),
            (),
            (),
            empty,
            empty,
            empty,
            empty,
            (),
            (),
            (),
            (),
            {
                "algorithm": "phase11_lp_exactness_then_branch_and_price",
                "terminal_reason": f"phase11_{phase11.status.value}",
                "phase11_diagnostics": dict(phase11.diagnostics),
                "formal_full_enumerators_used": False,
                "runtime_seconds": perf_counter() - started,
            },
        )

    lp_cuts = list(phase11.cuts)
    lp_cut_keys = {item.key for item in lp_cuts}
    exact_cuts: list[IntegerRecourseCut] = []
    exact_cut_keys: set[tuple[str, tuple[str, ...], str]] = set()
    certificates: list[IntegerRecourseCertificate] = []
    iterations: list[BendersBranchAndPriceIteration] = []
    visited_exact: set[tuple[str, ...]] = set()
    incumbent: _ExactIncumbent | None = None
    current_schedule = phase11.selected_flight_options
    lower_bound = phase11.lower_bound if phase11.lower_bound is not None else -math.inf
    first_upper_bound = phase11.upper_bound
    metrics = {
        "benders_master_iterations": len(phase11.iterations),
        "visited_schedules": int(phase11.diagnostics.get("visited_schedule_count", 0)),
        "schedules_closed_by_lp_exactness": 0,
        "schedules_requiring_aircraft_branch_and_price": 0,
        "schedules_requiring_crew_branch_and_price": 0,
        "aircraft_branch_and_price_nodes": 0,
        "crew_branch_and_price_nodes": 0,
        "lp_lower_bound_cuts": sum(
            item.cut_type is BendersCutType.OPTIMALITY for item in lp_cuts
        ),
        "exact_integer_cuts": 0,
        "feasibility_cuts": sum(
            item.cut_type is BendersCutType.FEASIBILITY for item in lp_cuts
        ),
        "initial_lower_bound": lower_bound,
        "first_upper_bound": first_upper_bound,
    }

    def finish(
        status: BendersBranchAndPriceStatus, reason: str
    ) -> BendersBranchAndPriceResult:
        x_values = incumbent.x_values if incumbent else empty
        y_values = incumbent.y_values if incumbent else empty
        z_values = incumbent.z_values if incumbent else empty
        w_values = incumbent.w_values if incumbent else empty
        upper = incumbent.objective if incumbent else None
        metrics["final_lower_bound"] = (
            lower_bound if math.isfinite(lower_bound) else None
        )
        metrics["final_upper_bound"] = upper
        metrics["final_gap"] = (
            max(0.0, upper - lower_bound)
            if upper is not None and math.isfinite(lower_bound)
            else None
        )
        diagnostics: dict[str, Any] = {
            "algorithm": "phase11_lp_exactness_then_branch_and_price",
            "terminal_reason": reason,
            "implicit_universe_fingerprint": fingerprint,
            "phase11_implicit_universe_fingerprint": phase11_fingerprint,
            "phase11_status": phase11.status.value,
            "phase11_iterations": len(phase11.iterations),
            "phase11_metrics": (
                dict(phase11_metrics) if isinstance(phase11_metrics, Mapping) else {}
            ),
            "metrics": dict(metrics),
            "formal_full_enumerators_used": False,
            "runtime_seconds": perf_counter() - started,
        }
        if status is BendersBranchAndPriceStatus.OPTIMAL:
            if incumbent is None:
                raise BendersBranchAndPriceError("OPTIMAL requires an incumbent")
            audit = recompute_benders_cg_audit(
                scenario,
                incumbent.columns,
                capacity_profile,
                costs,
                x_values,
                y_values,
                z_values,
                w_values,
                solver_factory=solver_factory,
            )
            if not audit.get("all_constraints_satisfied"):
                raise BendersBranchAndPriceError(
                    "final integrated audit found a constraint violation"
                )
            audited = float(audit["objective_breakdown"]["grand_total"])
            if not math.isclose(
                audited,
                incumbent.objective,
                abs_tol=BENDERS_CG_FEASIBILITY_TOLERANCE,
                rel_tol=BENDERS_CG_FEASIBILITY_TOLERANCE,
            ):
                raise BendersBranchAndPriceError(
                    "final integrated audit objective differs from incumbent"
                )
            diagnostics["integrated_audit"] = audit
        return BendersBranchAndPriceResult(
            status,
            upper,
            lower_bound if math.isfinite(lower_bound) else None,
            upper,
            tuple(iterations),
            tuple(exact_cuts),
            tuple(certificates),
            x_values,
            y_values,
            z_values,
            w_values,
            incumbent.schedule if incumbent else (),
            tuple(key for key, value in y_values.items() if value > 0.5),
            tuple(key for key, value in z_values.items() if value > 0.5),
            tuple(key for key, value in w_values.items() if value > 0.5),
            diagnostics,
        )

    for exact_iteration in range(1, benders_config.max_benders_iterations + 1):
        iteration_started = perf_counter()
        if current_schedule in visited_exact:
            return finish(
                BendersBranchAndPriceStatus.ABORTED,
                "revisited_exact_schedule_without_bound_closure",
            )
        visited_exact.add(current_schedule)
        metrics["visited_schedules"] = max(
            metrics["visited_schedules"], len(visited_exact)
        )
        option_by_id = {item.option_id: item for item in columns.flight_options}
        required = tuple(
            item_id
            for item_id in current_schedule
            if option_by_id[item_id].operation_type is FlightOperationType.OPERATE
        )
        aircraft_request = AircraftRecoveryRequest(scenario.scenario_id, required)
        crew_request = CrewRecoveryRequest(scenario.scenario_id, required)
        aircraft_cg = solve_aircraft_string_column_generation(
            scenario,
            columns.flight_options,
            aircraft_request,
            costs,
            string_config,
            aircraft_cg_config,
            solver_factory,
        )
        crew_cg = solve_crew_pairing_column_generation(
            scenario,
            columns.flight_options,
            crew_request,
            costs,
            pairing_config,
            crew_cg_config,
            solver_factory,
        )
        if aircraft_cg.status in {
            AircraftStringColumnGenerationStatus.NOT_CONVERGED,
            AircraftStringColumnGenerationStatus.ABORTED,
        } or crew_cg.status in {
            CrewPairingColumnGenerationStatus.NOT_CONVERGED,
            CrewPairingColumnGenerationStatus.ABORTED,
        }:
            not_converged = (
                aircraft_cg.status is AircraftStringColumnGenerationStatus.NOT_CONVERGED
                or crew_cg.status is CrewPairingColumnGenerationStatus.NOT_CONVERGED
            )
            status = (
                BendersBranchAndPriceStatus.NOT_CONVERGED
                if not_converged
                else BendersBranchAndPriceStatus.ABORTED
            )
            return finish(status, "root_column_generation_not_optimal")

        prm_request = PassengerRecoveryRequest(
            scenario.scenario_id,
            required,
            capacity_profile.capacity_profile_id,
        )
        prm = _solve_model(
            solver_factory,
            lambda solver: solve_fixed_column_prm(
                scenario,
                columns,
                prm_request,
                capacity_profile,
                costs,
                solver,
                solver_parameters=solver_parameters,
            ),
        )
        infeasible_source: BendersCgCutSource | None = None
        if aircraft_cg.status is AircraftStringColumnGenerationStatus.INFEASIBLE:
            infeasible_source = BendersCgCutSource.AIRCRAFT_LP_INFEASIBILITY
        elif crew_cg.status is CrewPairingColumnGenerationStatus.INFEASIBLE:
            infeasible_source = BendersCgCutSource.CREW_LP_INFEASIBILITY
        elif prm.status is SolverStatus.INFEASIBLE:
            infeasible_source = BendersCgCutSource.PASSENGER_MIP_INFEASIBILITY
        if infeasible_source is not None:
            cert_id = _certificate_id(
                fingerprint,
                current_schedule,
                BendersSubproblem.ARM,
                0.0,
                0.0,
            )
            cut = _feasibility_cut(
                current_schedule,
                infeasible_source,
                phase11_fingerprint,
                cert_id,
            )
            if cut.key not in lp_cut_keys:
                lp_cuts.append(cut)
                lp_cut_keys.add(cut.key)
                metrics["feasibility_cuts"] += 1
            iterations.append(
                BendersBranchAndPriceIteration(
                    exact_iteration,
                    current_schedule,
                    None,
                    lower_bound if math.isfinite(lower_bound) else None,
                    None,
                    incumbent.objective if incumbent else None,
                    aircraft_cg.objective_value,
                    None,
                    0,
                    crew_cg.objective_value,
                    None,
                    0,
                    prm.objective_value,
                    0,
                    0,
                    1,
                    perf_counter() - iteration_started,
                )
            )
        else:
            if (
                aircraft_cg.objective_value is None
                or crew_cg.objective_value is None
                or prm.objective_value is None
                or prm.status is not SolverStatus.OPTIMAL
            ):
                return finish(
                    BendersBranchAndPriceStatus.ABORTED,
                    "optimal_recourse_has_no_objective",
                )
            cg_columns = _dynamic_columns(columns, aircraft_cg.columns, crew_cg.columns)
            arm_binary = _solve_model(
                solver_factory,
                lambda solver: solve_fixed_column_arm(
                    scenario,
                    cg_columns,
                    aircraft_request,
                    costs,
                    solver,
                    solver_parameters=solver_parameters,
                ),
            )
            crm_binary = _solve_model(
                solver_factory,
                lambda solver: solve_fixed_column_crm(
                    scenario,
                    cg_columns,
                    crew_request,
                    costs,
                    solver,
                    solver_parameters=solver_parameters,
                ),
            )
            aircraft_exact_at_root = (
                arm_binary.status is SolverStatus.OPTIMAL
                and arm_binary.objective_value is not None
                and math.isclose(
                    aircraft_cg.objective_value,
                    arm_binary.objective_value,
                    abs_tol=benders_config.integrality_tolerance,
                    rel_tol=benders_config.integrality_tolerance,
                )
            )
            crew_exact_at_root = (
                crm_binary.status is SolverStatus.OPTIMAL
                and crm_binary.objective_value is not None
                and math.isclose(
                    crew_cg.objective_value,
                    crm_binary.objective_value,
                    abs_tol=benders_config.integrality_tolerance,
                    rel_tol=benders_config.integrality_tolerance,
                )
            )
            aircraft_bp = None
            crew_bp = None
            if not aircraft_exact_at_root:
                metrics["schedules_requiring_aircraft_branch_and_price"] += 1
                aircraft_bp = solve_aircraft_string_branch_and_price(
                    scenario,
                    columns.flight_options,
                    aircraft_request,
                    costs,
                    string_config,
                    aircraft_cg_config,
                    branch_config,
                    solver_factory,
                )
                metrics["aircraft_branch_and_price_nodes"] += aircraft_bp.nodes_solved
            if not crew_exact_at_root:
                metrics["schedules_requiring_crew_branch_and_price"] += 1
                crew_bp = solve_crew_pairing_branch_and_price(
                    scenario,
                    columns.flight_options,
                    crew_request,
                    costs,
                    pairing_config,
                    crew_cg_config,
                    branch_config,
                    solver_factory,
                )
                metrics["crew_branch_and_price_nodes"] += crew_bp.nodes_solved
            for result in (aircraft_bp, crew_bp):
                if result is None:
                    continue
                if result.status is BranchAndPriceStatus.NOT_CONVERGED:
                    return finish(
                        BendersBranchAndPriceStatus.NOT_CONVERGED,
                        "branch_and_price_not_converged",
                    )
                if result.status is BranchAndPriceStatus.ABORTED:
                    return finish(
                        BendersBranchAndPriceStatus.ABORTED,
                        "branch_and_price_aborted",
                    )
                if result.status is BranchAndPriceStatus.INFEASIBLE:
                    return finish(
                        BendersBranchAndPriceStatus.ABORTED,
                        "root_lp_feasible_but_integer_tree_infeasible",
                    )
            aircraft_integer = float(
                arm_binary.objective_value
                if aircraft_bp is None
                else aircraft_bp.objective_value
            )
            crew_integer = float(
                crm_binary.objective_value
                if crew_bp is None
                else crew_bp.objective_value
            )
            aircraft_pool = (
                aircraft_cg.columns
                if aircraft_bp is None
                else aircraft_bp.generated_columns
            )
            crew_pool = (
                crew_cg.columns if crew_bp is None else crew_bp.generated_columns
            )
            final_columns = _dynamic_columns(columns, aircraft_pool, crew_pool)
            y_values = (
                _selection_values(
                    arm_binary,
                    [item.string_id for item in aircraft_pool],
                    "selected_string_by_aircraft",
                )
                if aircraft_bp is None
                else MappingProxyType(
                    {
                        item.string_id: float(
                            item.string_id
                            in {
                                value.string_id
                                for value in aircraft_bp.selected_strings
                            }
                        )
                        for item in aircraft_pool
                    }
                )
            )
            z_values = (
                _selection_values(
                    crm_binary,
                    [item.pairing_id for item in crew_pool],
                    "selected_pairing_by_crew",
                )
                if crew_bp is None
                else MappingProxyType(
                    {
                        item.pairing_id: float(
                            item.pairing_id
                            in {value.pairing_id for value in crew_bp.selected_pairings}
                        )
                        for item in crew_pool
                    }
                )
            )
            w_values = _selection_values(
                prm,
                [item.itinerary_id for item in columns.passenger_itineraries],
                "selected_itinerary_by_group",
            )
            x_values = MappingProxyType(
                {
                    item.option_id: float(item.option_id in current_schedule)
                    for item in columns.flight_options
                }
            )
            schedule_cost = sum(
                schedule_flight_option_cost(scenario, option_by_id[item_id], costs)
                for item_id in current_schedule
            )
            candidate_value = (
                schedule_cost
                + aircraft_integer
                + crew_integer
                + float(prm.objective_value)
            )
            candidate = _ExactIncumbent(
                candidate_value,
                current_schedule,
                final_columns,
                x_values,
                y_values,
                z_values,
                w_values,
            )
            if incumbent is None or candidate.objective < incumbent.objective:
                incumbent = candidate

            owner_data = (
                (
                    BendersSubproblem.ARM,
                    float(aircraft_cg.objective_value),
                    aircraft_integer,
                    aircraft_bp,
                    tuple(key for key, value in y_values.items() if value > 0.5),
                    len(aircraft_pool),
                    aircraft_cg.input_fingerprint,
                ),
                (
                    BendersSubproblem.CRM,
                    float(crew_cg.objective_value),
                    crew_integer,
                    crew_bp,
                    tuple(key for key, value in z_values.items() if value > 0.5),
                    len(crew_pool),
                    crew_cg.input_fingerprint,
                ),
            )
            lp_added = 0
            exact_added = 0
            for (
                owner,
                lp_value,
                integer_value,
                bp_result,
                selected,
                pool_size,
                root_fp,
            ) in owner_data:
                cert_id = _certificate_id(
                    fingerprint,
                    current_schedule,
                    owner,
                    lp_value,
                    integer_value,
                )
                branching_fingerprint = (
                    hashlib.sha256(
                        "|".join(
                            item.branch_restriction_fingerprint
                            for item in (bp_result.nodes if bp_result else ())
                        ).encode("utf-8")
                    ).hexdigest()
                    if bp_result
                    else str(root_fp)
                )
                certificates.append(
                    IntegerRecourseCertificate(
                        cert_id,
                        current_schedule,
                        owner,
                        lp_value,
                        integer_value,
                        (bp_result.status.value if bp_result else "root_lp_integral"),
                        bp_result.nodes_solved if bp_result else 0,
                        bp_result.nodes_infeasible if bp_result else 0,
                        bp_result.nodes_pruned_bound if bp_result else 0,
                        pool_size,
                        selected,
                        fingerprint,
                        branching_fingerprint,
                        True,
                    )
                )
                lp_cut = _lp_cut(
                    owner,
                    current_schedule,
                    lp_value,
                    phase11_fingerprint,
                    cert_id,
                )
                if lp_cut.key not in lp_cut_keys:
                    lp_cuts.append(lp_cut)
                    lp_cut_keys.add(lp_cut.key)
                    lp_added += 1
                exact_cut = IntegerRecourseCut(
                    current_schedule,
                    owner,
                    integer_value,
                    fingerprint,
                    cert_id,
                )
                if exact_cut.key not in exact_cut_keys:
                    exact_cuts.append(exact_cut)
                    exact_cut_keys.add(exact_cut.key)
                    exact_added += 1
            prm_cert_id = _certificate_id(
                fingerprint,
                current_schedule,
                BendersSubproblem.PRM,
                float(prm.objective_value),
                float(prm.objective_value),
            )
            passenger_cut = _lp_cut(
                BendersSubproblem.PRM,
                current_schedule,
                float(prm.objective_value),
                phase11_fingerprint,
                prm_cert_id,
            )
            if passenger_cut.key not in lp_cut_keys:
                lp_cuts.append(passenger_cut)
                lp_cut_keys.add(passenger_cut.key)
                lp_added += 1
            metrics["lp_lower_bound_cuts"] += lp_added
            metrics["exact_integer_cuts"] += exact_added
            if aircraft_exact_at_root and crew_exact_at_root:
                metrics["schedules_closed_by_lp_exactness"] += 1

            iterations.append(
                BendersBranchAndPriceIteration(
                    exact_iteration,
                    current_schedule,
                    None,
                    lower_bound if math.isfinite(lower_bound) else None,
                    candidate_value,
                    incumbent.objective,
                    float(aircraft_cg.objective_value),
                    aircraft_integer,
                    aircraft_bp.nodes_solved if aircraft_bp else 0,
                    float(crew_cg.objective_value),
                    crew_integer,
                    crew_bp.nodes_solved if crew_bp else 0,
                    float(prm.objective_value),
                    lp_added,
                    exact_added,
                    0,
                    perf_counter() - iteration_started,
                )
            )

        solver = solver_factory()
        try:
            master = _build_master(
                scenario, columns, costs, lp_cuts, phase11_fingerprint, solver
            )
            _add_exact_constraints(solver, master, exact_cuts)
            outcome = solver.solve(solver_parameters)
            metrics["benders_master_iterations"] += 1
            if outcome.status is SolverStatus.INFEASIBLE:
                return finish(
                    (
                        BendersBranchAndPriceStatus.OPTIMAL
                        if incumbent
                        else BendersBranchAndPriceStatus.INFEASIBLE
                    ),
                    "master_exhausted",
                )
            if (
                outcome.status is not SolverStatus.OPTIMAL
                or outcome.objective_value is None
            ):
                return finish(
                    BendersBranchAndPriceStatus.ABORTED,
                    f"master_nonoptimal:{outcome.status.value}",
                )
            master_objective = float(outcome.objective_value)
            lower_bound = max(lower_bound, master_objective)
            master_x = {
                option_id: solver.get_variable_value(variable)
                for option_id, variable in master.srm_model.variables.items()
            }
            next_schedule = schedule_signature(scenario, columns, master_x)
        finally:
            solver.close()
        last = iterations[-1]
        iterations[-1] = BendersBranchAndPriceIteration(
            last.iteration,
            last.schedule_signature,
            master_objective,
            lower_bound,
            last.candidate_upper_bound,
            last.incumbent_upper_bound,
            last.aircraft_lp_objective,
            last.aircraft_integer_objective,
            last.aircraft_branch_nodes,
            last.crew_lp_objective,
            last.crew_integer_objective,
            last.crew_branch_nodes,
            last.passenger_objective,
            last.lp_cuts_added,
            last.exact_cuts_added,
            last.feasibility_cuts_added,
            last.runtime_seconds,
        )
        if incumbent is not None:
            gap = max(0.0, incumbent.objective - lower_bound)
            relative = gap / max(1.0, abs(incumbent.objective))
            if (
                gap <= benders_config.absolute_gap_tolerance
                or relative <= benders_config.relative_gap_tolerance
            ):
                return finish(
                    BendersBranchAndPriceStatus.OPTIMAL,
                    "exact_integer_bound_closed",
                )
        current_schedule = next_schedule

    return finish(
        BendersBranchAndPriceStatus.NOT_CONVERGED,
        "maximum_benders_iterations_reached",
    )
