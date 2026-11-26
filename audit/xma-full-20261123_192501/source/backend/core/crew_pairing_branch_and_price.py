from __future__ import annotations

import heapq
import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from time import perf_counter
from types import MappingProxyType

from backend.config import (
    BranchAndPriceConfig,
    CrewPairingColumnGenerationConfig,
    CrewPairingGenerationConfig,
    FixedColumnCostConfig,
)
from backend.schemas.columns import CrewPairing, FlightOption
from backend.schemas.scenario import Scenario
from backend.solver import SolverAdapter

from .aircraft_string_branch_and_price import BranchAndPriceStatus
from .branch_restrictions import (
    BranchRestrictionError,
    CrewBranchRestrictions,
    CrewFollowOn,
    CrewPairingKey,
    CrewTypedLeg,
    branch_restriction_fingerprint,
)
from .crm import CrewRecoveryRequest
from .crew_pairing_column_generation import (
    CrewPairingColumnGenerationStatus,
    solve_crew_pairing_column_generation,
)
from .pairing_generator import pairing_semantic_key


class CrewBranchAndPriceError(ValueError):
    """Crew Branch-and-Price cannot prove the requested integer recourse."""


@dataclass(frozen=True)
class CrewBranchAndPriceNode:
    node_id: str
    parent_id: str | None
    depth: int
    branch_restriction_fingerprint: str
    branch_decision: str
    cg_status: str
    lp_lower_bound: float | None
    column_count: int
    reused_parent_columns: int
    integral: bool
    pruned_reason: str | None
    phase_one_iterations: int
    phase_two_iterations: int


@dataclass(frozen=True)
class CrewBranchAndPriceResult:
    status: BranchAndPriceStatus
    objective_value: float | None
    lower_bound: float | None
    upper_bound: float | None
    root_lp_objective: float | None
    selected_pairings: tuple[CrewPairing, ...]
    pairing_values: Mapping[str, float] = field(repr=False)
    nodes: tuple[CrewBranchAndPriceNode, ...]
    generated_columns: tuple[CrewPairing, ...]
    nodes_created: int
    nodes_solved: int
    nodes_infeasible: int
    nodes_pruned_bound: int
    integral_nodes: int
    max_depth: int
    total_phase_one_iterations: int
    total_phase_two_iterations: int
    reused_parent_columns: int
    input_fingerprint: str | None
    termination_reason: str
    runtime_seconds: float

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "pairing_values", MappingProxyType(dict(self.pairing_values))
        )


@dataclass(frozen=True)
class _OpenCrewNode:
    node_id: str
    parent_id: str | None
    depth: int
    restrictions: CrewBranchRestrictions
    initial_columns: tuple[CrewPairing, ...]
    decision: str
    inherited_bound: float


@dataclass(frozen=True)
class _CrewIncumbent:
    objective: float
    columns: tuple[CrewPairing, ...]
    values: Mapping[str, float]


def _copy_follow_ons(
    values: Mapping[str, Sequence[CrewFollowOn]],
) -> dict[str, set[CrewFollowOn]]:
    return {owner: set(items) for owner, items in values.items()}


def _copy_legs(
    values: Mapping[str, Sequence[CrewTypedLeg]],
) -> dict[str, set[CrewTypedLeg]]:
    return {owner: set(items) for owner, items in values.items()}


def _restriction_kwargs(restrictions: CrewBranchRestrictions) -> dict[str, object]:
    return {
        "required_follow_ons_by_crew": dict(restrictions.required_follow_ons_by_crew),
        "forbidden_follow_ons_by_crew": dict(restrictions.forbidden_follow_ons_by_crew),
        "required_typed_legs_by_crew": dict(restrictions.required_typed_legs_by_crew),
        "forbidden_typed_legs_by_crew": dict(restrictions.forbidden_typed_legs_by_crew),
        "forced_pairing_key_by_crew": dict(restrictions.forced_pairing_key_by_crew),
        "forbidden_pairing_keys": restrictions.forbidden_pairing_keys,
    }


def _follow_on_children(
    restrictions: CrewBranchRestrictions,
    crew_id: str,
    follow_on: CrewFollowOn,
) -> tuple[CrewBranchRestrictions, CrewBranchRestrictions]:
    left = _restriction_kwargs(restrictions)
    right = _restriction_kwargs(restrictions)
    forbidden = _copy_follow_ons(restrictions.forbidden_follow_ons_by_crew)
    forbidden.setdefault(crew_id, set()).add(follow_on)
    required = _copy_follow_ons(restrictions.required_follow_ons_by_crew)
    required.setdefault(crew_id, set()).add(follow_on)
    left["forbidden_follow_ons_by_crew"] = forbidden
    right["required_follow_ons_by_crew"] = required
    return CrewBranchRestrictions(**left), CrewBranchRestrictions(**right)


def _typed_leg_children(
    restrictions: CrewBranchRestrictions,
    crew_id: str,
    leg: CrewTypedLeg,
) -> tuple[CrewBranchRestrictions, CrewBranchRestrictions]:
    left = _restriction_kwargs(restrictions)
    right = _restriction_kwargs(restrictions)
    forbidden = _copy_legs(restrictions.forbidden_typed_legs_by_crew)
    forbidden.setdefault(crew_id, set()).add(leg)
    required = _copy_legs(restrictions.required_typed_legs_by_crew)
    required.setdefault(crew_id, set()).add(leg)
    left["forbidden_typed_legs_by_crew"] = forbidden
    right["required_typed_legs_by_crew"] = required
    return CrewBranchRestrictions(**left), CrewBranchRestrictions(**right)


def _pairing_children(
    restrictions: CrewBranchRestrictions,
    key: CrewPairingKey,
) -> tuple[CrewBranchRestrictions, CrewBranchRestrictions]:
    left = _restriction_kwargs(restrictions)
    right = _restriction_kwargs(restrictions)
    forbidden = set(restrictions.forbidden_pairing_keys)
    forbidden.add(key)
    forced = dict(restrictions.forced_pairing_key_by_crew)
    forced[key[0]] = key
    left["forbidden_pairing_keys"] = frozenset(forbidden)
    right["forced_pairing_key_by_crew"] = forced
    return CrewBranchRestrictions(**left), CrewBranchRestrictions(**right)


def _path(item: CrewPairing) -> tuple[CrewTypedLeg, ...]:
    return pairing_semantic_key(item)[1]


def _branch_candidate(
    columns: Sequence[CrewPairing],
    values: Mapping[str, float],
    tolerance: float,
) -> tuple[str, tuple[object, ...]] | None:
    follow_ons: dict[tuple[str, CrewFollowOn], float] = {}
    typed_legs: dict[tuple[str, CrewTypedLeg], float] = {}
    for item in columns:
        value = values.get(item.pairing_id, 0.0)
        path = _path(item)
        for follow_on in zip(path, path[1:]):
            key = (item.crew_id, follow_on)
            follow_ons[key] = follow_ons.get(key, 0.0) + value
        for leg in set(path):
            key = (item.crew_id, leg)
            typed_legs[key] = typed_legs.get(key, 0.0) + value
    fractional_follow_ons = [
        (abs(value - 0.5), key, value)
        for key, value in follow_ons.items()
        if tolerance < value < 1.0 - tolerance
    ]
    if fractional_follow_ons:
        _, key, value = min(fractional_follow_ons)
        return "follow_on", (key[0], key[1], value)
    fractional_legs = [
        (abs(value - 0.5), key, value)
        for key, value in typed_legs.items()
        if tolerance < value < 1.0 - tolerance
    ]
    if fractional_legs:
        _, key, value = min(fractional_legs)
        return "typed_leg", (key[0], key[1], value)
    fractional_columns = [
        (abs(value - 0.5), pairing_semantic_key(item), value)
        for item in columns
        if tolerance < (value := values.get(item.pairing_id, 0.0)) < 1.0 - tolerance
    ]
    if fractional_columns:
        _, key, value = min(fractional_columns)
        return "pairing", (key, value)
    return None


def _is_integral(values: Mapping[str, float], tolerance: float) -> bool:
    return all(
        value <= tolerance or value >= 1.0 - tolerance for value in values.values()
    )


def _finish(
    status: BranchAndPriceStatus,
    incumbent: _CrewIncumbent | None,
    lower_bound: float | None,
    root_lp: float | None,
    node_records: Sequence[CrewBranchAndPriceNode],
    generated: Mapping[CrewPairingKey, CrewPairing],
    next_node_number: int,
    nodes_infeasible: int,
    nodes_pruned_bound: int,
    integral_nodes: int,
    max_depth: int,
    total_phase_one: int,
    total_phase_two: int,
    total_reused: int,
    root_fingerprint: str | None,
    termination_reason: str,
    started: float,
) -> CrewBranchAndPriceResult:
    return CrewBranchAndPriceResult(
        status,
        incumbent.objective if incumbent else None,
        lower_bound,
        incumbent.objective if incumbent else None,
        root_lp,
        incumbent.columns if incumbent else (),
        incumbent.values if incumbent else {},
        tuple(node_records),
        tuple(generated.values()),
        next_node_number,
        len(node_records),
        nodes_infeasible,
        nodes_pruned_bound,
        integral_nodes,
        max_depth,
        total_phase_one,
        total_phase_two,
        total_reused,
        root_fingerprint,
        termination_reason,
        perf_counter() - started,
    )


def solve_crew_pairing_branch_and_price(
    scenario: Scenario,
    flight_options: Sequence[FlightOption],
    request: CrewRecoveryRequest,
    costs: FixedColumnCostConfig,
    pairing_config: CrewPairingGenerationConfig,
    cg_config: CrewPairingColumnGenerationConfig,
    branch_config: BranchAndPriceConfig,
    solver_factory: Callable[[], SolverAdapter],
) -> CrewBranchAndPriceResult:
    """Solve the fixed-schedule implicit binary CRM by deterministic B&P."""

    started = perf_counter()
    root = _OpenCrewNode(
        "C000000", None, 0, CrewBranchRestrictions(), (), "root", -math.inf
    )
    open_nodes: list[tuple[float, int, str, _OpenCrewNode]] = [
        (root.inherited_bound, root.depth, root.node_id, root)
    ]
    node_records: list[CrewBranchAndPriceNode] = []
    generated: dict[CrewPairingKey, CrewPairing] = {}
    incumbent: _CrewIncumbent | None = None
    next_node_number = 1
    nodes_infeasible = 0
    nodes_pruned_bound = 0
    integral_nodes = 0
    max_depth = 0
    total_phase_one = 0
    total_phase_two = 0
    total_reused = 0
    root_lp: float | None = None
    root_fingerprint: str | None = None
    termination_reason = "tree_exhausted"

    while open_nodes:
        if len(node_records) >= branch_config.max_nodes:
            termination_reason = "maximum_nodes_reached"
            lower = min(item[0] for item in open_nodes)
            return _finish(
                BranchAndPriceStatus.NOT_CONVERGED,
                incumbent,
                lower if math.isfinite(lower) else None,
                root_lp,
                node_records,
                generated,
                next_node_number,
                nodes_infeasible,
                nodes_pruned_bound,
                integral_nodes,
                max_depth,
                total_phase_one,
                total_phase_two,
                total_reused,
                root_fingerprint,
                termination_reason,
                started,
            )
        _, _, _, node = heapq.heappop(open_nodes)
        max_depth = max(max_depth, node.depth)
        legal_seed = tuple(
            item for item in node.initial_columns if node.restrictions.allows(item)
        )
        total_reused += len(legal_seed)
        cg = solve_crew_pairing_column_generation(
            scenario,
            flight_options,
            request,
            costs,
            pairing_config,
            cg_config,
            solver_factory,
            branch_restrictions=node.restrictions,
            initial_columns=legal_seed,
        )
        total_phase_one += cg.phase_one_iterations
        total_phase_two += cg.phase_two_iterations
        for item in cg.columns:
            generated[pairing_semantic_key(item)] = item
        if node.parent_id is None:
            root_fingerprint = cg.input_fingerprint
        if cg.status in {
            CrewPairingColumnGenerationStatus.NOT_CONVERGED,
            CrewPairingColumnGenerationStatus.ABORTED,
        }:
            termination_reason = f"node_{node.node_id}_cg_{cg.status.value}"
            node_records.append(
                CrewBranchAndPriceNode(
                    node.node_id,
                    node.parent_id,
                    node.depth,
                    branch_restriction_fingerprint(node.restrictions),
                    node.decision,
                    cg.status.value,
                    None,
                    len(cg.columns),
                    len(legal_seed),
                    False,
                    termination_reason,
                    cg.phase_one_iterations,
                    cg.phase_two_iterations,
                )
            )
            status = (
                BranchAndPriceStatus.NOT_CONVERGED
                if cg.status is CrewPairingColumnGenerationStatus.NOT_CONVERGED
                else BranchAndPriceStatus.ABORTED
            )
            return _finish(
                status,
                incumbent,
                None,
                root_lp,
                node_records,
                generated,
                next_node_number,
                nodes_infeasible,
                nodes_pruned_bound,
                integral_nodes,
                max_depth,
                total_phase_one,
                total_phase_two,
                total_reused,
                root_fingerprint,
                termination_reason,
                started,
            )
        if cg.status is CrewPairingColumnGenerationStatus.INFEASIBLE:
            nodes_infeasible += 1
            node_records.append(
                CrewBranchAndPriceNode(
                    node.node_id,
                    node.parent_id,
                    node.depth,
                    branch_restriction_fingerprint(node.restrictions),
                    node.decision,
                    cg.status.value,
                    None,
                    len(cg.columns),
                    len(legal_seed),
                    False,
                    "infeasible",
                    cg.phase_one_iterations,
                    cg.phase_two_iterations,
                )
            )
            continue
        if cg.objective_value is None:
            raise CrewBranchAndPriceError(
                f"node {node.node_id} OPTIMAL CG has no objective"
            )
        objective = float(cg.objective_value)
        if node.parent_id is None:
            root_lp = objective
        integral = _is_integral(cg.pairing_values, branch_config.integrality_tolerance)
        if incumbent is not None and objective >= (
            incumbent.objective - branch_config.bound_tolerance
        ):
            nodes_pruned_bound += 1
            node_records.append(
                CrewBranchAndPriceNode(
                    node.node_id,
                    node.parent_id,
                    node.depth,
                    branch_restriction_fingerprint(node.restrictions),
                    node.decision,
                    cg.status.value,
                    objective,
                    len(cg.columns),
                    len(legal_seed),
                    integral,
                    "bound",
                    cg.phase_one_iterations,
                    cg.phase_two_iterations,
                )
            )
            continue
        if integral:
            integral_nodes += 1
            selected = tuple(
                item
                for item in cg.columns
                if cg.pairing_values.get(item.pairing_id, 0.0) > 0.5
            )
            incumbent = _CrewIncumbent(
                objective,
                selected,
                MappingProxyType(dict(cg.pairing_values)),
            )
            node_records.append(
                CrewBranchAndPriceNode(
                    node.node_id,
                    node.parent_id,
                    node.depth,
                    branch_restriction_fingerprint(node.restrictions),
                    node.decision,
                    cg.status.value,
                    objective,
                    len(cg.columns),
                    len(legal_seed),
                    True,
                    "integral",
                    cg.phase_one_iterations,
                    cg.phase_two_iterations,
                )
            )
            continue
        if node.depth >= branch_config.max_depth:
            termination_reason = "maximum_depth_reached"
            node_records.append(
                CrewBranchAndPriceNode(
                    node.node_id,
                    node.parent_id,
                    node.depth,
                    branch_restriction_fingerprint(node.restrictions),
                    node.decision,
                    cg.status.value,
                    objective,
                    len(cg.columns),
                    len(legal_seed),
                    False,
                    termination_reason,
                    cg.phase_one_iterations,
                    cg.phase_two_iterations,
                )
            )
            return _finish(
                BranchAndPriceStatus.NOT_CONVERGED,
                incumbent,
                objective,
                root_lp,
                node_records,
                generated,
                next_node_number,
                nodes_infeasible,
                nodes_pruned_bound,
                integral_nodes,
                max_depth,
                total_phase_one,
                total_phase_two,
                total_reused,
                root_fingerprint,
                termination_reason,
                started,
            )
        branch = _branch_candidate(
            cg.columns, cg.pairing_values, branch_config.integrality_tolerance
        )
        if branch is None:
            raise CrewBranchAndPriceError(
                f"node {node.node_id} is fractional but has no branch candidate"
            )
        kind, payload = branch
        try:
            if kind == "follow_on":
                crew_id, follow_on, value = payload
                assert isinstance(follow_on, tuple)
                children = _follow_on_children(
                    node.restrictions, str(crew_id), follow_on
                )
                description = f"follow_on[{crew_id},{follow_on}]={float(value):.12g}"
            elif kind == "typed_leg":
                crew_id, leg, value = payload
                assert isinstance(leg, tuple)
                children = _typed_leg_children(node.restrictions, str(crew_id), leg)
                description = f"typed_leg[{crew_id},{leg}]={float(value):.12g}"
            else:
                key, value = payload
                assert isinstance(key, tuple)
                children = _pairing_children(node.restrictions, key)
                description = f"pairing[{key}]={float(value):.12g}"
        except BranchRestrictionError as exc:
            raise CrewBranchAndPriceError(
                f"failed to create children at {node.node_id}: {exc}"
            ) from exc
        node_records.append(
            CrewBranchAndPriceNode(
                node.node_id,
                node.parent_id,
                node.depth,
                branch_restriction_fingerprint(node.restrictions),
                f"{node.decision};branch:{description}",
                cg.status.value,
                objective,
                len(cg.columns),
                len(legal_seed),
                False,
                None,
                cg.phase_one_iterations,
                cg.phase_two_iterations,
            )
        )
        for side, child_restrictions in zip(("left", "right"), children):
            node_id = f"C{next_node_number:06d}"
            next_node_number += 1
            child = _OpenCrewNode(
                node_id,
                node.node_id,
                node.depth + 1,
                child_restrictions,
                tuple(cg.columns),
                f"{description}:{side}",
                objective,
            )
            heapq.heappush(
                open_nodes,
                (child.inherited_bound, child.depth, child.node_id, child),
            )

    if incumbent is None:
        return _finish(
            BranchAndPriceStatus.INFEASIBLE,
            None,
            None,
            root_lp,
            node_records,
            generated,
            next_node_number,
            nodes_infeasible,
            nodes_pruned_bound,
            integral_nodes,
            max_depth,
            total_phase_one,
            total_phase_two,
            total_reused,
            root_fingerprint,
            termination_reason,
            started,
        )
    return _finish(
        BranchAndPriceStatus.OPTIMAL,
        incumbent,
        incumbent.objective,
        root_lp,
        node_records,
        generated,
        next_node_number,
        nodes_infeasible,
        nodes_pruned_bound,
        integral_nodes,
        max_depth,
        total_phase_one,
        total_phase_two,
        total_reused,
        root_fingerprint,
        termination_reason,
        started,
    )
