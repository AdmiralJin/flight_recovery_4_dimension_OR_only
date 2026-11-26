from __future__ import annotations

import heapq
import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from time import perf_counter
from types import MappingProxyType

from backend.config import (
    AircraftStringColumnGenerationConfig,
    BranchAndPriceConfig,
    FixedColumnCostConfig,
    FlightStringGenerationConfig,
)
from backend.schemas.columns import AircraftString, FlightOption
from backend.schemas.scenario import Scenario
from backend.solver import SolverAdapter

from .aircraft_string_column_generation import (
    AircraftStringColumnGenerationResult,
    AircraftStringColumnGenerationStatus,
    solve_aircraft_string_column_generation,
)
from .arm import AircraftRecoveryRequest
from .branch_restrictions import (
    AircraftBranchRestrictions,
    AircraftStringKey,
    BranchRestrictionError,
    branch_restriction_fingerprint,
)
from .string_generator import aircraft_string_semantic_key


class BranchAndPriceStatus(str, Enum):
    OPTIMAL = "optimal"
    INFEASIBLE = "infeasible"
    NOT_CONVERGED = "not_converged"
    ABORTED = "aborted"


class AircraftBranchAndPriceError(ValueError):
    """Aircraft Branch-and-Price cannot prove the requested integer recourse."""


@dataclass(frozen=True)
class AircraftBranchAndPriceNode:
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
class AircraftBranchAndPriceResult:
    status: BranchAndPriceStatus
    objective_value: float | None
    lower_bound: float | None
    upper_bound: float | None
    root_lp_objective: float | None
    selected_strings: tuple[AircraftString, ...]
    string_values: Mapping[str, float] = field(repr=False)
    nodes: tuple[AircraftBranchAndPriceNode, ...]
    generated_columns: tuple[AircraftString, ...]
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
            self, "string_values", MappingProxyType(dict(self.string_values))
        )


@dataclass(frozen=True)
class _OpenAircraftNode:
    node_id: str
    parent_id: str | None
    depth: int
    restrictions: AircraftBranchRestrictions
    initial_columns: tuple[AircraftString, ...]
    decision: str
    inherited_bound: float


@dataclass(frozen=True)
class _AircraftIncumbent:
    objective: float
    columns: tuple[AircraftString, ...]
    values: Mapping[str, float]


def _copy_sets(values: Mapping[str, Sequence[str]]) -> dict[str, set[str]]:
    return {owner: set(items) for owner, items in values.items()}


def _assignment_children(
    restrictions: AircraftBranchRestrictions,
    aircraft_id: str,
    option_id: str,
) -> tuple[AircraftBranchRestrictions, AircraftBranchRestrictions]:
    required = _copy_sets(restrictions.required_options_by_aircraft)
    forbidden = _copy_sets(restrictions.forbidden_options_by_aircraft)
    left_forbidden = {key: set(value) for key, value in forbidden.items()}
    left_forbidden.setdefault(aircraft_id, set()).add(option_id)
    right_required = {key: set(value) for key, value in required.items()}
    right_required.setdefault(aircraft_id, set()).add(option_id)
    common = {
        "forced_string_key_by_aircraft": dict(
            restrictions.forced_string_key_by_aircraft
        ),
        "forbidden_string_keys": restrictions.forbidden_string_keys,
    }
    return (
        AircraftBranchRestrictions(
            required_options_by_aircraft=required,
            forbidden_options_by_aircraft=left_forbidden,
            **common,
        ),
        AircraftBranchRestrictions(
            required_options_by_aircraft=right_required,
            forbidden_options_by_aircraft=forbidden,
            **common,
        ),
    )


def _string_children(
    restrictions: AircraftBranchRestrictions,
    key: AircraftStringKey,
) -> tuple[AircraftBranchRestrictions, AircraftBranchRestrictions]:
    forbidden_keys = set(restrictions.forbidden_string_keys)
    forbidden_keys.add(key)
    forced = dict(restrictions.forced_string_key_by_aircraft)
    forced[key[0]] = key
    common = {
        "required_options_by_aircraft": dict(restrictions.required_options_by_aircraft),
        "forbidden_options_by_aircraft": dict(
            restrictions.forbidden_options_by_aircraft
        ),
    }
    return (
        AircraftBranchRestrictions(
            **common,
            forced_string_key_by_aircraft=dict(
                restrictions.forced_string_key_by_aircraft
            ),
            forbidden_string_keys=frozenset(forbidden_keys),
        ),
        AircraftBranchRestrictions(
            **common,
            forced_string_key_by_aircraft=forced,
            forbidden_string_keys=restrictions.forbidden_string_keys,
        ),
    )


def _branch_candidate(
    columns: Sequence[AircraftString],
    values: Mapping[str, float],
    request: AircraftRecoveryRequest,
    tolerance: float,
) -> tuple[str, tuple[object, ...]] | None:
    assignments: dict[tuple[str, str], float] = {}
    required = set(request.required_operated_option_ids)
    for item in columns:
        value = values.get(item.string_id, 0.0)
        for option_id in item.leg_option_ids:
            if option_id in required:
                key = (item.aircraft_id, option_id)
                assignments[key] = assignments.get(key, 0.0) + value
    fractional_assignments = [
        (abs(value - 0.5), key, value)
        for key, value in assignments.items()
        if tolerance < value < 1.0 - tolerance
    ]
    if fractional_assignments:
        _, key, value = min(fractional_assignments)
        return "assignment", (key[0], key[1], value)
    fractional_columns = [
        (
            abs(value - 0.5),
            aircraft_string_semantic_key(item.aircraft_id, item.leg_option_ids),
            value,
        )
        for item in columns
        if tolerance < (value := values.get(item.string_id, 0.0)) < 1.0 - tolerance
    ]
    if fractional_columns:
        _, key, value = min(fractional_columns)
        return "string", (key, value)
    return None


def _is_integral(values: Mapping[str, float], tolerance: float) -> bool:
    return all(
        value <= tolerance or value >= 1.0 - tolerance for value in values.values()
    )


def solve_aircraft_string_branch_and_price(
    scenario: Scenario,
    flight_options: Sequence[FlightOption],
    request: AircraftRecoveryRequest,
    costs: FixedColumnCostConfig,
    string_config: FlightStringGenerationConfig,
    cg_config: AircraftStringColumnGenerationConfig,
    branch_config: BranchAndPriceConfig,
    solver_factory: Callable[[], SolverAdapter],
) -> AircraftBranchAndPriceResult:
    """Solve the fixed-schedule implicit binary ARM by deterministic B&P."""

    started = perf_counter()
    root = _OpenAircraftNode(
        node_id="A000000",
        parent_id=None,
        depth=0,
        restrictions=AircraftBranchRestrictions(),
        initial_columns=(),
        decision="root",
        inherited_bound=-math.inf,
    )
    open_nodes: list[tuple[float, int, str, _OpenAircraftNode]] = [
        (root.inherited_bound, root.depth, root.node_id, root)
    ]
    node_records: list[AircraftBranchAndPriceNode] = []
    generated: dict[AircraftStringKey, AircraftString] = {}
    incumbent: _AircraftIncumbent | None = None
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
            return AircraftBranchAndPriceResult(
                BranchAndPriceStatus.NOT_CONVERGED,
                incumbent.objective if incumbent else None,
                lower if math.isfinite(lower) else None,
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
        _, _, _, node = heapq.heappop(open_nodes)
        max_depth = max(max_depth, node.depth)
        legal_seed = tuple(
            item for item in node.initial_columns if node.restrictions.allows(item)
        )
        total_reused += len(legal_seed)
        cg = solve_aircraft_string_column_generation(
            scenario,
            flight_options,
            request,
            costs,
            string_config,
            cg_config,
            solver_factory,
            branch_restrictions=node.restrictions,
            initial_columns=legal_seed,
        )
        total_phase_one += cg.phase_one_iterations
        total_phase_two += cg.phase_two_iterations
        for item in cg.columns:
            generated[
                aircraft_string_semantic_key(item.aircraft_id, item.leg_option_ids)
            ] = item
        if node.parent_id is None:
            root_fingerprint = cg.input_fingerprint
        if cg.status is AircraftStringColumnGenerationStatus.NOT_CONVERGED:
            termination_reason = f"node_{node.node_id}_cg_not_converged"
            status = BranchAndPriceStatus.NOT_CONVERGED
        elif cg.status is AircraftStringColumnGenerationStatus.ABORTED:
            termination_reason = f"node_{node.node_id}_cg_aborted"
            status = BranchAndPriceStatus.ABORTED
        else:
            status = None
        if status is not None:
            node_records.append(
                AircraftBranchAndPriceNode(
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
            return AircraftBranchAndPriceResult(
                status,
                incumbent.objective if incumbent else None,
                None,
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
        if cg.status is AircraftStringColumnGenerationStatus.INFEASIBLE:
            nodes_infeasible += 1
            node_records.append(
                AircraftBranchAndPriceNode(
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
            raise AircraftBranchAndPriceError(
                f"node {node.node_id} OPTIMAL CG has no objective"
            )
        objective = float(cg.objective_value)
        if node.parent_id is None:
            root_lp = objective
        if incumbent is not None and objective >= (
            incumbent.objective - branch_config.bound_tolerance
        ):
            nodes_pruned_bound += 1
            node_records.append(
                AircraftBranchAndPriceNode(
                    node.node_id,
                    node.parent_id,
                    node.depth,
                    branch_restriction_fingerprint(node.restrictions),
                    node.decision,
                    cg.status.value,
                    objective,
                    len(cg.columns),
                    len(legal_seed),
                    _is_integral(cg.string_values, branch_config.integrality_tolerance),
                    "bound",
                    cg.phase_one_iterations,
                    cg.phase_two_iterations,
                )
            )
            continue
        integral = _is_integral(cg.string_values, branch_config.integrality_tolerance)
        if integral:
            integral_nodes += 1
            selected = tuple(
                item
                for item in cg.columns
                if cg.string_values.get(item.string_id, 0.0) > 0.5
            )
            incumbent = _AircraftIncumbent(
                objective,
                selected,
                MappingProxyType(dict(cg.string_values)),
            )
            node_records.append(
                AircraftBranchAndPriceNode(
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
                AircraftBranchAndPriceNode(
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
            return AircraftBranchAndPriceResult(
                BranchAndPriceStatus.NOT_CONVERGED,
                incumbent.objective if incumbent else None,
                objective,
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
        branch = _branch_candidate(
            cg.columns,
            cg.string_values,
            request,
            branch_config.integrality_tolerance,
        )
        if branch is None:
            raise AircraftBranchAndPriceError(
                f"node {node.node_id} is fractional but has no branch candidate"
            )
        kind, payload = branch
        try:
            if kind == "assignment":
                aircraft_id, option_id, value = payload
                children = _assignment_children(
                    node.restrictions, str(aircraft_id), str(option_id)
                )
                description = (
                    f"assignment[{aircraft_id},{option_id}]={float(value):.12g}"
                )
            else:
                key, value = payload
                assert isinstance(key, tuple)
                children = _string_children(node.restrictions, key)
                description = f"string[{key}]={float(value):.12g}"
        except BranchRestrictionError as exc:
            raise AircraftBranchAndPriceError(
                f"failed to create children at {node.node_id}: {exc}"
            ) from exc
        node_records.append(
            AircraftBranchAndPriceNode(
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
            node_id = f"A{next_node_number:06d}"
            next_node_number += 1
            child = _OpenAircraftNode(
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
        return AircraftBranchAndPriceResult(
            BranchAndPriceStatus.INFEASIBLE,
            None,
            None,
            None,
            root_lp,
            (),
            {},
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
    return AircraftBranchAndPriceResult(
        BranchAndPriceStatus.OPTIMAL,
        incumbent.objective,
        incumbent.objective,
        incumbent.objective,
        root_lp,
        incumbent.columns,
        incumbent.values,
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
