from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from time import perf_counter
from types import MappingProxyType

from backend.config.aircraft_string_column_generation import (
    AircraftStringColumnGenerationConfig,
)
from backend.config.costs import FixedColumnCostConfig
from backend.config.string_generation import FlightStringGenerationConfig
from backend.schemas.columns import AircraftString, FlightOption
from backend.schemas.scenario import Scenario
from backend.solver.base import SolverAdapter, SolverStatus

from .aircraft_string_master import (
    AircraftStringMasterPhase,
    AircraftStringMasterResult,
    build_aircraft_string_master,
    solve_aircraft_string_master,
    restrict_aircraft_string_pool,
    validate_aircraft_string_master_inputs,
)
from .aircraft_string_pricing import (
    evaluate_aircraft_string_reduced_cost,
    price_aircraft_strings,
)
from .arm import AircraftRecoveryRequest
from .branch_restrictions import (
    AircraftBranchRestrictions,
    branch_restriction_fingerprint,
)
from .scope import RecoveryScope, resolve_original_flight_option_ids
from .string_generator import (
    aircraft_string_semantic_key,
    make_generated_aircraft_string,
    validate_generated_aircraft_string,
)


class AircraftStringColumnGenerationError(ValueError):
    """Phase 9 cannot safely execute the requested column generation."""


class AircraftStringColumnGenerationStatus(str, Enum):
    OPTIMAL = "optimal"
    INFEASIBLE = "infeasible"
    NOT_CONVERGED = "not_converged"
    ABORTED = "aborted"


@dataclass(frozen=True)
class AircraftStringColumnGenerationIteration:
    phase: AircraftStringMasterPhase
    iteration: int
    phase_iteration: int
    restricted_master_objective: float | None
    artificial_objective: float
    real_column_count_before: int
    real_column_count_after: int
    dual_count: int
    priced_aircraft_count: int
    minimum_reduced_cost: float | None
    negative_columns_found: int
    new_columns_added: int
    duplicate_paths_skipped: int
    paths_evaluated: int
    runtime_seconds: float


@dataclass(frozen=True)
class AircraftStringColumnGenerationResult:
    status: AircraftStringColumnGenerationStatus
    objective_value: float | None
    columns: tuple[AircraftString, ...]
    string_values: Mapping[str, float] = field(repr=False)
    iterations: tuple[AircraftStringColumnGenerationIteration, ...]
    phase_one_iterations: int
    phase_two_iterations: int
    input_fingerprint: str
    termination_reason: str
    maximum_reduced_cost_audit_error: float
    runtime_seconds: float

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "string_values", MappingProxyType(dict(self.string_values))
        )


@dataclass(frozen=True)
class AircraftStringColumnGenerationAudit:
    full_column_count: int
    final_column_count: int
    omitted_column_count: int
    minimum_omitted_reduced_cost: float | None
    pricing_epsilon: float
    passed: bool


def aircraft_string_cg_input_fingerprint(
    scenario: Scenario,
    flight_options: Sequence[FlightOption],
    request: AircraftRecoveryRequest,
    costs: FixedColumnCostConfig,
    string_config: FlightStringGenerationConfig,
    cg_config: AircraftStringColumnGenerationConfig,
    scope: RecoveryScope | None,
    branch_restrictions: AircraftBranchRestrictions | None = None,
) -> str:
    payload = {
        "scenario": scenario.model_dump(mode="json"),
        "flight_options": [item.model_dump(mode="json") for item in flight_options],
        "request": {
            "scenario_id": request.scenario_id,
            "required_operated_option_ids": request.required_operated_option_ids,
        },
        "costs": costs.model_dump(mode="json"),
        "string_config": string_config.model_dump(mode="json"),
        "cg_config": cg_config.model_dump(mode="json"),
        "scope_aircraft_ids": None if scope is None else scope.aircraft_ids,
        "branch_restriction_fingerprint": branch_restriction_fingerprint(
            branch_restrictions
        ),
    }
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _initial_pool(
    scenario: Scenario,
    flight_options: Sequence[FlightOption],
    scope: RecoveryScope | None,
) -> tuple[AircraftString, ...]:
    if scope is None:
        return ()
    priced = set(scope.aircraft_ids)
    originals = resolve_original_flight_option_ids(scenario, flight_options)
    return tuple(
        make_generated_aircraft_string(
            aircraft,
            tuple(originals[flight_id] for flight_id in aircraft.original_rotation),
        )
        for aircraft in scenario.aircraft
        if aircraft.tail_id not in priced
    )


def _run_master(
    solver_factory: Callable[[], SolverAdapter],
    scenario: Scenario,
    flight_options: Sequence[FlightOption],
    pool: Sequence[AircraftString],
    request: AircraftRecoveryRequest,
    costs: FixedColumnCostConfig,
    string_config: FlightStringGenerationConfig,
    phase: AircraftStringMasterPhase,
) -> AircraftStringMasterResult:
    solver = solver_factory()
    try:
        model = build_aircraft_string_master(
            scenario,
            flight_options,
            pool,
            request,
            costs,
            string_config,
            solver,
            phase=phase,
        )
        return solve_aircraft_string_master(model, solver)
    finally:
        solver.close()


def solve_aircraft_string_column_generation(
    scenario: Scenario,
    flight_options: Sequence[FlightOption],
    request: AircraftRecoveryRequest,
    costs: FixedColumnCostConfig,
    string_config: FlightStringGenerationConfig,
    cg_config: AircraftStringColumnGenerationConfig,
    solver_factory: Callable[[], SolverAdapter],
    *,
    scope: RecoveryScope | None = None,
    branch_restrictions: AircraftBranchRestrictions | None = None,
    initial_columns: Sequence[AircraftString] = (),
) -> AircraftStringColumnGenerationResult:
    """Solve the fixed-schedule aircraft LP without accepting a full string pool."""

    started = perf_counter()
    validate_aircraft_string_master_inputs(
        scenario, flight_options, (), request, string_config
    )
    aircraft_ids = {item.tail_id for item in scenario.aircraft}
    if branch_restrictions is not None and scope is not None:
        raise AircraftStringColumnGenerationError(
            "branch-restricted Aircraft CG requires scope=None"
        )
    if scope is not None:
        unknown = set(scope.aircraft_ids) - aircraft_ids
        if unknown:
            raise AircraftStringColumnGenerationError(
                f"scope contains unknown aircraft: {sorted(unknown)}"
            )
    priced_ids = aircraft_ids if scope is None else set(scope.aircraft_ids)
    priced_aircraft = tuple(
        item for item in scenario.aircraft if item.tail_id in priced_ids
    )
    option_ids = {item.option_id for item in flight_options}
    if branch_restrictions is not None:
        branch_owners = (
            set(branch_restrictions.required_options_by_aircraft)
            | set(branch_restrictions.forbidden_options_by_aircraft)
            | set(branch_restrictions.forced_string_key_by_aircraft)
            | {key[0] for key in branch_restrictions.forbidden_string_keys}
        )
        unknown_owners = branch_owners - aircraft_ids
        if unknown_owners:
            raise AircraftStringColumnGenerationError(
                f"branch restrictions contain unknown aircraft: {sorted(unknown_owners)}"
            )
        branch_options = set().union(
            *branch_restrictions.required_options_by_aircraft.values(),
            *branch_restrictions.forbidden_options_by_aircraft.values(),
            *(set(key[1]) for key in branch_restrictions.forbidden_string_keys),
            *(
                set(key[1])
                for key in branch_restrictions.forced_string_key_by_aircraft.values()
            ),
        )
        unknown_options = branch_options - option_ids
        if unknown_options:
            raise AircraftStringColumnGenerationError(
                f"branch restrictions contain unknown options: {sorted(unknown_options)}"
            )
    pool = list(_initial_pool(scenario, flight_options, scope))
    if branch_restrictions is not None:
        pool = [item for item in pool if branch_restrictions.allows(item)]
    aircraft_by_id = {item.tail_id: item for item in scenario.aircraft}
    for item in initial_columns:
        aircraft = aircraft_by_id.get(item.aircraft_id)
        if aircraft is None:
            raise AircraftStringColumnGenerationError(
                f"initial column has unknown aircraft {item.aircraft_id!r}"
            )
        audit = validate_generated_aircraft_string(
            scenario, flight_options, aircraft, item, string_config
        )
        if not audit.valid:
            raise AircraftStringColumnGenerationError(
                f"illegal initial Aircraft String {item.string_id!r}: {audit.violations}"
            )
        if branch_restrictions is None or branch_restrictions.allows(item):
            pool.append(item)
    deduplicated: dict[tuple[str, tuple[str, ...]], AircraftString] = {}
    for item in pool:
        deduplicated[
            aircraft_string_semantic_key(item.aircraft_id, item.leg_option_ids)
        ] = item
    pool = list(deduplicated.values())
    existing_keys = {
        aircraft_string_semantic_key(item.aircraft_id, item.leg_option_ids)
        for item in pool
    }
    fingerprint = aircraft_string_cg_input_fingerprint(
        scenario,
        flight_options,
        request,
        costs,
        string_config,
        cg_config,
        scope,
        branch_restrictions,
    )
    records: list[AircraftStringColumnGenerationIteration] = []
    phase_counts = {
        AircraftStringMasterPhase.PHASE_I: 0,
        AircraftStringMasterPhase.PHASE_II: 0,
    }
    maximum_audit_error = 0.0
    last_master: AircraftStringMasterResult | None = None

    def finish(
        status: AircraftStringColumnGenerationStatus,
        reason: str,
        master: AircraftStringMasterResult | None,
    ) -> AircraftStringColumnGenerationResult:
        current_fingerprint = aircraft_string_cg_input_fingerprint(
            scenario,
            flight_options,
            request,
            costs,
            string_config,
            cg_config,
            scope,
            branch_restrictions,
        )
        if current_fingerprint != fingerprint:
            status = AircraftStringColumnGenerationStatus.ABORTED
            reason = "fixed_input_fingerprint_changed_during_solve"
            master = None
        objective = (
            master.objective_value
            if master is not None
            and master.phase is AircraftStringMasterPhase.PHASE_II
            and master.outcome.status is SolverStatus.OPTIMAL
            else None
        )
        values = master.string_values if objective is not None else {}
        return AircraftStringColumnGenerationResult(
            status=status,
            objective_value=objective,
            columns=tuple(pool),
            string_values=values,
            iterations=tuple(records),
            phase_one_iterations=phase_counts[AircraftStringMasterPhase.PHASE_I],
            phase_two_iterations=phase_counts[AircraftStringMasterPhase.PHASE_II],
            input_fingerprint=fingerprint,
            termination_reason=reason,
            maximum_reduced_cost_audit_error=maximum_audit_error,
            runtime_seconds=perf_counter() - started,
        )

    phase = AircraftStringMasterPhase.PHASE_I
    phase_iteration = 0
    for iteration in range(1, cg_config.max_iterations + 1):
        iteration_started = perf_counter()
        phase_iteration += 1
        phase_counts[phase] += 1
        before = len(pool)
        master = _run_master(
            solver_factory,
            scenario,
            flight_options,
            pool,
            request,
            costs,
            string_config,
            phase,
        )
        last_master = master
        if master.outcome.status is not SolverStatus.OPTIMAL or master.duals is None:
            status = (
                AircraftStringColumnGenerationStatus.INFEASIBLE
                if master.outcome.status is SolverStatus.INFEASIBLE
                else AircraftStringColumnGenerationStatus.ABORTED
            )
            return finish(
                status, f"restricted_master_{master.outcome.status.value}", master
            )
        audit_error = master.maximum_reduced_cost_error or 0.0
        maximum_audit_error = max(maximum_audit_error, audit_error)
        if audit_error > cg_config.reduced_cost_audit_tolerance:
            return finish(
                AircraftStringColumnGenerationStatus.ABORTED,
                "existing_column_reduced_cost_audit_failed",
                master,
            )

        if (
            phase is AircraftStringMasterPhase.PHASE_I
            and master.artificial_objective <= cg_config.feasibility_epsilon
        ):
            records.append(
                AircraftStringColumnGenerationIteration(
                    phase=phase,
                    iteration=iteration,
                    phase_iteration=phase_iteration,
                    restricted_master_objective=master.objective_value,
                    artificial_objective=master.artificial_objective,
                    real_column_count_before=before,
                    real_column_count_after=before,
                    dual_count=master.duals.count,
                    priced_aircraft_count=0,
                    minimum_reduced_cost=None,
                    negative_columns_found=0,
                    new_columns_added=0,
                    duplicate_paths_skipped=0,
                    paths_evaluated=0,
                    runtime_seconds=perf_counter() - iteration_started,
                )
            )
            phase = AircraftStringMasterPhase.PHASE_II
            phase_iteration = 0
            continue

        pricing_results = tuple(
            price_aircraft_strings(
                scenario,
                flight_options,
                aircraft,
                request,
                costs,
                string_config,
                master.duals,
                existing_keys,
                pricing_epsilon=cg_config.pricing_epsilon,
                max_columns=cg_config.max_columns_per_aircraft_per_iteration,
                branch_restrictions=branch_restrictions,
            )
            for aircraft in priced_aircraft
        )
        minima = [
            result.minimum_reduced_cost
            for result in pricing_results
            if result.minimum_reduced_cost is not None
        ]
        priced_columns = [item for result in pricing_results for item in result.columns]
        added = 0
        for item in sorted(
            priced_columns,
            key=lambda value: (
                value.aircraft_string.aircraft_id,
                value.reduced_cost,
                tuple(value.aircraft_string.leg_option_ids),
            ),
        ):
            key = aircraft_string_semantic_key(
                item.aircraft_string.aircraft_id,
                item.aircraft_string.leg_option_ids,
            )
            if key in existing_keys:
                continue
            pool.append(item.aircraft_string)
            existing_keys.add(key)
            added += 1
        records.append(
            AircraftStringColumnGenerationIteration(
                phase=phase,
                iteration=iteration,
                phase_iteration=phase_iteration,
                restricted_master_objective=master.objective_value,
                artificial_objective=master.artificial_objective,
                real_column_count_before=before,
                real_column_count_after=len(pool),
                dual_count=master.duals.count,
                priced_aircraft_count=len(priced_aircraft),
                minimum_reduced_cost=min(minima) if minima else None,
                negative_columns_found=len(priced_columns),
                new_columns_added=added,
                duplicate_paths_skipped=sum(
                    result.duplicate_paths_skipped for result in pricing_results
                ),
                paths_evaluated=sum(
                    result.paths_evaluated for result in pricing_results
                ),
                runtime_seconds=perf_counter() - iteration_started,
            )
        )
        if added:
            continue
        if phase is AircraftStringMasterPhase.PHASE_I:
            return finish(
                AircraftStringColumnGenerationStatus.INFEASIBLE,
                "positive_artificial_objective_without_improving_column",
                master,
            )
        return finish(
            AircraftStringColumnGenerationStatus.OPTIMAL,
            "no_negative_reduced_cost_column",
            master,
        )

    return finish(
        AircraftStringColumnGenerationStatus.NOT_CONVERGED,
        "maximum_iterations_reached",
        last_master,
    )


def audit_aircraft_string_column_generation_termination(
    scenario: Scenario,
    flight_options: Sequence[FlightOption],
    full_strings: Sequence[AircraftString],
    request: AircraftRecoveryRequest,
    costs: FixedColumnCostConfig,
    string_config: FlightStringGenerationConfig,
    cg_config: AircraftStringColumnGenerationConfig,
    result: AircraftStringColumnGenerationResult,
    solver_factory: Callable[[], SolverAdapter],
    *,
    scope: RecoveryScope | None = None,
) -> AircraftStringColumnGenerationAudit:
    """Exhaustively audit termination outside the formal CG solver.

    The full Phase 5 pool is deliberately accepted only by this audit boundary.
    """

    if result.status is not AircraftStringColumnGenerationStatus.OPTIMAL:
        raise AircraftStringColumnGenerationError(
            "termination audit requires an OPTIMAL column-generation result"
        )
    full_pool = restrict_aircraft_string_pool(
        scenario, flight_options, full_strings, scope
    )
    master = _run_master(
        solver_factory,
        scenario,
        flight_options,
        result.columns,
        request,
        costs,
        string_config,
        AircraftStringMasterPhase.PHASE_II,
    )
    if master.outcome.status is not SolverStatus.OPTIMAL or master.duals is None:
        raise AircraftStringColumnGenerationError(
            "final restricted master could not be re-solved for termination audit"
        )
    final_keys = {
        aircraft_string_semantic_key(item.aircraft_id, item.leg_option_ids)
        for item in result.columns
    }
    options = {item.option_id: item for item in flight_options}
    omitted_reduced_costs = tuple(
        evaluate_aircraft_string_reduced_cost(
            scenario, options, item, costs, master.duals
        ).reduced_cost
        for item in full_pool
        if aircraft_string_semantic_key(item.aircraft_id, item.leg_option_ids)
        not in final_keys
    )
    minimum = min(omitted_reduced_costs) if omitted_reduced_costs else None
    return AircraftStringColumnGenerationAudit(
        full_column_count=len(full_pool),
        final_column_count=len(result.columns),
        omitted_column_count=len(omitted_reduced_costs),
        minimum_omitted_reduced_cost=minimum,
        pricing_epsilon=cg_config.pricing_epsilon,
        passed=minimum is None or minimum >= -cg_config.pricing_epsilon,
    )
