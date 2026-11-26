from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from time import perf_counter
from types import MappingProxyType

from backend.config.costs import FixedColumnCostConfig
from backend.config.crew_pairing_column_generation import (
    CrewPairingColumnGenerationConfig,
)
from backend.config.pairing_generation import CrewPairingGenerationConfig
from backend.schemas.columns import CrewPairing, FlightOption
from backend.schemas.scenario import Scenario
from backend.solver.base import SolverAdapter, SolverStatus

from .crm import CrewRecoveryRequest
from .branch_restrictions import (
    CrewBranchRestrictions,
    branch_restriction_fingerprint,
)
from .crew_pairing_master import (
    CrewPairingMasterPhase,
    CrewPairingMasterResult,
    build_crew_pairing_master,
    original_pairing_by_crew,
    restrict_crew_pairing_pool,
    solve_crew_pairing_master,
    validate_crew_pairing_master_inputs,
)
from .crew_pairing_pricing import (
    evaluate_crew_pairing_reduced_cost,
    price_crew_pairings,
)
from .pairing_generator import pairing_semantic_key, validate_generated_crew_pairing
from .scope import RecoveryScope


class CrewPairingColumnGenerationError(ValueError):
    """Phase 10 cannot safely execute the requested column generation."""


class CrewPairingColumnGenerationStatus(str, Enum):
    OPTIMAL = "optimal"
    INFEASIBLE = "infeasible"
    NOT_CONVERGED = "not_converged"
    ABORTED = "aborted"


@dataclass(frozen=True)
class CrewPairingColumnGenerationIteration:
    phase: CrewPairingMasterPhase
    iteration: int
    phase_iteration: int
    restricted_master_objective: float | None
    artificial_objective: float
    real_column_count_before: int
    real_column_count_after: int
    dual_count: int
    priced_crew_count: int
    minimum_reduced_cost: float | None
    negative_columns_found: int
    new_columns_added: int
    duplicate_paths_skipped: int
    paths_evaluated: int
    resource_pruning_count: int
    runtime_seconds: float


@dataclass(frozen=True)
class CrewPairingColumnGenerationResult:
    status: CrewPairingColumnGenerationStatus
    objective_value: float | None
    columns: tuple[CrewPairing, ...]
    pairing_values: Mapping[str, float] = field(repr=False)
    iterations: tuple[CrewPairingColumnGenerationIteration, ...]
    phase_one_iterations: int
    phase_two_iterations: int
    input_fingerprint: str
    termination_reason: str
    maximum_reduced_cost_audit_error: float
    runtime_seconds: float

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "pairing_values", MappingProxyType(dict(self.pairing_values))
        )


@dataclass(frozen=True)
class CrewPairingColumnGenerationAudit:
    full_column_count: int
    final_column_count: int
    omitted_column_count: int
    minimum_omitted_reduced_cost: float | None
    pricing_epsilon: float
    passed: bool


def crew_pairing_cg_input_fingerprint(
    scenario: Scenario,
    flight_options: Sequence[FlightOption],
    request: CrewRecoveryRequest,
    costs: FixedColumnCostConfig,
    pairing_config: CrewPairingGenerationConfig,
    cg_config: CrewPairingColumnGenerationConfig,
    scope: RecoveryScope | None,
    branch_restrictions: CrewBranchRestrictions | None = None,
) -> str:
    payload = {
        "scenario": scenario.model_dump(mode="json"),
        "flight_options": [item.model_dump(mode="json") for item in flight_options],
        "request": {
            "scenario_id": request.scenario_id,
            "required_operated_option_ids": request.required_operated_option_ids,
        },
        "costs": costs.model_dump(mode="json"),
        "pairing_config": pairing_config.model_dump(mode="json"),
        "cg_config": cg_config.model_dump(mode="json"),
        "scope_crew_ids": None if scope is None else scope.crew_ids,
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
) -> tuple[CrewPairing, ...]:
    if scope is None:
        return ()
    priced = set(scope.crew_ids)
    originals = original_pairing_by_crew(scenario, flight_options)
    return tuple(
        originals[crew.crew_id] for crew in scenario.crew if crew.crew_id not in priced
    )


def _run_master(
    solver_factory: Callable[[], SolverAdapter],
    scenario: Scenario,
    flight_options: Sequence[FlightOption],
    pool: Sequence[CrewPairing],
    request: CrewRecoveryRequest,
    costs: FixedColumnCostConfig,
    pairing_config: CrewPairingGenerationConfig,
    phase: CrewPairingMasterPhase,
) -> CrewPairingMasterResult:
    solver = solver_factory()
    try:
        model = build_crew_pairing_master(
            scenario,
            flight_options,
            pool,
            request,
            costs,
            pairing_config,
            solver,
            phase=phase,
        )
        return solve_crew_pairing_master(model, solver)
    finally:
        solver.close()


def solve_crew_pairing_column_generation(
    scenario: Scenario,
    flight_options: Sequence[FlightOption],
    request: CrewRecoveryRequest,
    costs: FixedColumnCostConfig,
    pairing_config: CrewPairingGenerationConfig,
    cg_config: CrewPairingColumnGenerationConfig,
    solver_factory: Callable[[], SolverAdapter],
    *,
    scope: RecoveryScope | None = None,
    branch_restrictions: CrewBranchRestrictions | None = None,
    initial_columns: Sequence[CrewPairing] = (),
) -> CrewPairingColumnGenerationResult:
    """Solve fixed-schedule Crew LP without accepting a full pairing pool."""

    started = perf_counter()
    validate_crew_pairing_master_inputs(
        scenario, flight_options, (), request, pairing_config
    )
    crew_ids = {item.crew_id for item in scenario.crew}
    if branch_restrictions is not None and scope is not None:
        raise CrewPairingColumnGenerationError(
            "branch-restricted Crew CG requires scope=None"
        )
    if scope is not None:
        unknown = set(scope.crew_ids) - crew_ids
        if unknown:
            raise CrewPairingColumnGenerationError(
                f"scope contains unknown crew: {sorted(unknown)}"
            )
    priced_ids = crew_ids if scope is None else set(scope.crew_ids)
    priced_crew = tuple(item for item in scenario.crew if item.crew_id in priced_ids)
    option_ids = {item.option_id for item in flight_options}
    if branch_restrictions is not None:
        branch_owners = (
            set(branch_restrictions.required_follow_ons_by_crew)
            | set(branch_restrictions.forbidden_follow_ons_by_crew)
            | set(branch_restrictions.required_typed_legs_by_crew)
            | set(branch_restrictions.forbidden_typed_legs_by_crew)
            | set(branch_restrictions.forced_pairing_key_by_crew)
            | {key[0] for key in branch_restrictions.forbidden_pairing_keys}
        )
        unknown_owners = branch_owners - crew_ids
        if unknown_owners:
            raise CrewPairingColumnGenerationError(
                f"branch restrictions contain unknown crew: {sorted(unknown_owners)}"
            )
        typed_legs = set().union(
            *branch_restrictions.required_typed_legs_by_crew.values(),
            *branch_restrictions.forbidden_typed_legs_by_crew.values(),
            *(set(key[1]) for key in branch_restrictions.forbidden_pairing_keys),
            *(
                set(key[1])
                for key in branch_restrictions.forced_pairing_key_by_crew.values()
            ),
            *(
                {leg for follow_on in values for leg in follow_on}
                for values in branch_restrictions.required_follow_ons_by_crew.values()
            ),
            *(
                {leg for follow_on in values for leg in follow_on}
                for values in branch_restrictions.forbidden_follow_ons_by_crew.values()
            ),
        )
        unknown_options = {item[1] for item in typed_legs} - option_ids
        if unknown_options:
            raise CrewPairingColumnGenerationError(
                f"branch restrictions contain unknown options: {sorted(unknown_options)}"
            )
    pool = list(_initial_pool(scenario, flight_options, scope))
    if branch_restrictions is not None:
        pool = [item for item in pool if branch_restrictions.allows(item)]
    crew_by_id = {item.crew_id: item for item in scenario.crew}
    for item in initial_columns:
        crew = crew_by_id.get(item.crew_id)
        if crew is None:
            raise CrewPairingColumnGenerationError(
                f"initial column has unknown crew {item.crew_id!r}"
            )
        audit = validate_generated_crew_pairing(
            scenario, flight_options, crew, item, pairing_config
        )
        if not audit.valid:
            raise CrewPairingColumnGenerationError(
                f"illegal initial Crew Pairing {item.pairing_id!r}: {audit.violations}"
            )
        if branch_restrictions is None or branch_restrictions.allows(item):
            pool.append(item)
    deduplicated = {pairing_semantic_key(item): item for item in pool}
    pool = list(deduplicated.values())
    existing_keys = {pairing_semantic_key(item) for item in pool}
    fingerprint = crew_pairing_cg_input_fingerprint(
        scenario,
        flight_options,
        request,
        costs,
        pairing_config,
        cg_config,
        scope,
        branch_restrictions,
    )
    records: list[CrewPairingColumnGenerationIteration] = []
    phase_counts = {
        CrewPairingMasterPhase.PHASE_I: 0,
        CrewPairingMasterPhase.PHASE_II: 0,
    }
    maximum_audit_error = 0.0
    last_master: CrewPairingMasterResult | None = None

    def finish(
        status: CrewPairingColumnGenerationStatus,
        reason: str,
        master: CrewPairingMasterResult | None,
    ) -> CrewPairingColumnGenerationResult:
        current_fingerprint = crew_pairing_cg_input_fingerprint(
            scenario,
            flight_options,
            request,
            costs,
            pairing_config,
            cg_config,
            scope,
            branch_restrictions,
        )
        if current_fingerprint != fingerprint:
            status = CrewPairingColumnGenerationStatus.ABORTED
            reason = "fixed_input_fingerprint_changed_during_solve"
            master = None
        objective = (
            master.objective_value
            if master is not None
            and master.phase is CrewPairingMasterPhase.PHASE_II
            and master.outcome.status is SolverStatus.OPTIMAL
            else None
        )
        values = master.pairing_values if objective is not None else {}
        return CrewPairingColumnGenerationResult(
            status=status,
            objective_value=objective,
            columns=tuple(pool),
            pairing_values=values,
            iterations=tuple(records),
            phase_one_iterations=phase_counts[CrewPairingMasterPhase.PHASE_I],
            phase_two_iterations=phase_counts[CrewPairingMasterPhase.PHASE_II],
            input_fingerprint=fingerprint,
            termination_reason=reason,
            maximum_reduced_cost_audit_error=maximum_audit_error,
            runtime_seconds=perf_counter() - started,
        )

    phase = CrewPairingMasterPhase.PHASE_I
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
            pairing_config,
            phase,
        )
        last_master = master
        if master.outcome.status is not SolverStatus.OPTIMAL or master.duals is None:
            status = (
                CrewPairingColumnGenerationStatus.INFEASIBLE
                if master.outcome.status is SolverStatus.INFEASIBLE
                else CrewPairingColumnGenerationStatus.ABORTED
            )
            return finish(
                status, f"restricted_master_{master.outcome.status.value}", master
            )
        audit_error = master.maximum_reduced_cost_error or 0.0
        maximum_audit_error = max(maximum_audit_error, audit_error)
        if audit_error > cg_config.reduced_cost_audit_tolerance:
            return finish(
                CrewPairingColumnGenerationStatus.ABORTED,
                "existing_column_reduced_cost_audit_failed",
                master,
            )
        if (
            phase is CrewPairingMasterPhase.PHASE_I
            and master.artificial_objective <= cg_config.feasibility_epsilon
        ):
            records.append(
                CrewPairingColumnGenerationIteration(
                    phase=phase,
                    iteration=iteration,
                    phase_iteration=phase_iteration,
                    restricted_master_objective=master.objective_value,
                    artificial_objective=master.artificial_objective,
                    real_column_count_before=before,
                    real_column_count_after=before,
                    dual_count=master.duals.count,
                    priced_crew_count=0,
                    minimum_reduced_cost=None,
                    negative_columns_found=0,
                    new_columns_added=0,
                    duplicate_paths_skipped=0,
                    paths_evaluated=0,
                    resource_pruning_count=0,
                    runtime_seconds=perf_counter() - iteration_started,
                )
            )
            phase = CrewPairingMasterPhase.PHASE_II
            phase_iteration = 0
            continue

        pricing_results = tuple(
            price_crew_pairings(
                scenario,
                flight_options,
                crew,
                request,
                costs,
                pairing_config,
                master.duals,
                existing_keys,
                pricing_epsilon=cg_config.pricing_epsilon,
                max_columns=cg_config.max_columns_per_crew_per_iteration,
                branch_restrictions=branch_restrictions,
            )
            for crew in priced_crew
        )
        minima = [
            item.minimum_reduced_cost
            for item in pricing_results
            if item.minimum_reduced_cost is not None
        ]
        priced_columns = [item for result in pricing_results for item in result.columns]
        added = 0
        for item in sorted(
            priced_columns,
            key=lambda value: (
                value.crew_pairing.crew_id,
                value.reduced_cost,
                pairing_semantic_key(value.crew_pairing),
            ),
        ):
            key = pairing_semantic_key(item.crew_pairing)
            if key in existing_keys:
                continue
            pool.append(item.crew_pairing)
            existing_keys.add(key)
            added += 1
        records.append(
            CrewPairingColumnGenerationIteration(
                phase=phase,
                iteration=iteration,
                phase_iteration=phase_iteration,
                restricted_master_objective=master.objective_value,
                artificial_objective=master.artificial_objective,
                real_column_count_before=before,
                real_column_count_after=len(pool),
                dual_count=master.duals.count,
                priced_crew_count=len(priced_crew),
                minimum_reduced_cost=min(minima) if minima else None,
                negative_columns_found=len(priced_columns),
                new_columns_added=added,
                duplicate_paths_skipped=sum(
                    item.duplicate_paths_skipped for item in pricing_results
                ),
                paths_evaluated=sum(item.paths_evaluated for item in pricing_results),
                resource_pruning_count=sum(
                    sum(item.resource_pruning_counts.values())
                    for item in pricing_results
                ),
                runtime_seconds=perf_counter() - iteration_started,
            )
        )
        if added:
            continue
        if phase is CrewPairingMasterPhase.PHASE_I:
            return finish(
                CrewPairingColumnGenerationStatus.INFEASIBLE,
                "positive_artificial_objective_without_improving_column",
                master,
            )
        return finish(
            CrewPairingColumnGenerationStatus.OPTIMAL,
            "no_negative_reduced_cost_column",
            master,
        )
    return finish(
        CrewPairingColumnGenerationStatus.NOT_CONVERGED,
        "maximum_iterations_reached",
        last_master,
    )


def audit_crew_pairing_column_generation_termination(
    scenario: Scenario,
    flight_options: Sequence[FlightOption],
    full_pairings: Sequence[CrewPairing],
    request: CrewRecoveryRequest,
    costs: FixedColumnCostConfig,
    pairing_config: CrewPairingGenerationConfig,
    cg_config: CrewPairingColumnGenerationConfig,
    result: CrewPairingColumnGenerationResult,
    solver_factory: Callable[[], SolverAdapter],
    *,
    scope: RecoveryScope | None = None,
) -> CrewPairingColumnGenerationAudit:
    """Exhaustively audit termination outside the formal Crew CG solver."""

    if result.status is not CrewPairingColumnGenerationStatus.OPTIMAL:
        raise CrewPairingColumnGenerationError(
            "termination audit requires an OPTIMAL column-generation result"
        )
    full_pool = restrict_crew_pairing_pool(
        scenario, flight_options, full_pairings, scope
    )
    master = _run_master(
        solver_factory,
        scenario,
        flight_options,
        result.columns,
        request,
        costs,
        pairing_config,
        CrewPairingMasterPhase.PHASE_II,
    )
    if master.outcome.status is not SolverStatus.OPTIMAL or master.duals is None:
        raise CrewPairingColumnGenerationError(
            "final restricted master could not be re-solved for termination audit"
        )
    final_keys = {pairing_semantic_key(item) for item in result.columns}
    options = {item.option_id: item for item in flight_options}
    omitted_reduced_costs = tuple(
        evaluate_crew_pairing_reduced_cost(
            scenario, options, item, costs, master.duals
        ).reduced_cost
        for item in full_pool
        if pairing_semantic_key(item) not in final_keys
    )
    minimum = min(omitted_reduced_costs) if omitted_reduced_costs else None
    return CrewPairingColumnGenerationAudit(
        full_column_count=len(full_pool),
        final_column_count=len(result.columns),
        omitted_column_count=len(omitted_reduced_costs),
        minimum_omitted_reduced_cost=minimum,
        pricing_epsilon=cg_config.pricing_epsilon,
        passed=minimum is None or minimum >= -cg_config.pricing_epsilon,
    )
