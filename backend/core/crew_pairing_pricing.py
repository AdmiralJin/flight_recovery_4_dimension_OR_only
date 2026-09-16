from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence, Set
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType

from backend.config.costs import FixedColumnCostConfig, crew_pairing_cost
from backend.config.pairing_generation import CrewPairingGenerationConfig
from backend.schemas.columns import (
    CrewPairing,
    CrewSegmentType,
    FlightOperationType,
    FlightOption,
)
from backend.schemas.crew import Crew
from backend.schemas.scenario import Scenario

from .crew_network import CrewLegKey, build_crew_flight_network
from .crew_pairing_master import CrewPairingMasterDuals, CrewPairingMasterPhase
from .crm import CrewRecoveryRequest
from .pairing_generator import (
    make_generated_crew_pairing,
    pairing_semantic_key,
    validate_generated_crew_pairing,
)


class CrewPairingPricingError(ValueError):
    """The crew-local pricing problem cannot be constructed safely."""


@dataclass(frozen=True)
class CrewPairingPricingState:
    """Explicit resource label carried by the typed Crew DAG search."""

    last_leg: CrewLegKey
    typed_path: tuple[CrewLegKey, ...]
    used_option_ids: frozenset[str]
    used_base_flight_ids: frozenset[str]
    deadhead_count: int
    first_departure_time: datetime
    duty_elapsed_minutes: float


@dataclass(frozen=True)
class CrewPairingPricedColumn:
    crew_pairing: CrewPairing
    primal_cost: float
    dual_contribution: float
    reduced_cost: float
    row_coefficients: Mapping[str, float] = field(repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "row_coefficients", MappingProxyType(dict(self.row_coefficients))
        )


@dataclass(frozen=True)
class CrewPairingPricingResult:
    crew_id: str
    columns: tuple[CrewPairingPricedColumn, ...]
    minimum_reduced_cost: float | None
    paths_evaluated: int
    omitted_paths_evaluated: int
    duplicate_paths_skipped: int
    resource_pruning_counts: Mapping[str, int] = field(repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "resource_pruning_counts",
            MappingProxyType(dict(self.resource_pruning_counts)),
        )


def _segments(pairing: CrewPairing):
    return tuple(segment for duty in pairing.duties for segment in duty.segments)


def evaluate_crew_pairing_reduced_cost(
    scenario: Scenario,
    flight_options: Mapping[str, FlightOption],
    pairing: CrewPairing,
    costs: FixedColumnCostConfig,
    duals: CrewPairingMasterDuals,
) -> CrewPairingPricedColumn:
    """Evaluate crew pairing c - pi*a using the actual CRM LP rows."""

    row_coefficients: dict[str, float] = {
        f"selection:{pairing.crew_id}": 1.0,
        f"terminal:{pairing.crew_id}": 1.0,
    }
    contribution = duals.selection_by_crew[pairing.crew_id]
    contribution += duals.terminal_by_crew[pairing.crew_id]
    for segment in _segments(pairing):
        option_id = segment.flight_option_id or ""
        if segment.segment_type is CrewSegmentType.OPERATE:
            if option_id in duals.required_operate_coverage_by_option:
                row_coefficients[f"required_operate:{option_id}"] = 1.0
                contribution += duals.required_operate_coverage_by_option[option_id]
            elif option_id in duals.nonrequired_operate_by_option:
                row_coefficients[f"nonrequired_operate:{option_id}"] = 1.0
                contribution += duals.nonrequired_operate_by_option[option_id]
        elif (
            segment.segment_type is CrewSegmentType.DEADHEAD
            and option_id in duals.nonrequired_deadhead_by_option
        ):
            row_coefficients[f"nonrequired_deadhead:{option_id}"] = 1.0
            contribution += duals.nonrequired_deadhead_by_option[option_id]
    true_cost = crew_pairing_cost(scenario, flight_options, pairing, costs).total
    primal_cost = 0.0 if duals.phase is CrewPairingMasterPhase.PHASE_I else true_cost
    return CrewPairingPricedColumn(
        crew_pairing=pairing,
        primal_cost=primal_cost,
        dual_contribution=contribution,
        reduced_cost=primal_cost - contribution,
        row_coefficients=row_coefficients,
    )


def price_crew_pairings(
    scenario: Scenario,
    flight_options: Sequence[FlightOption],
    crew: Crew,
    request: CrewRecoveryRequest,
    costs: FixedColumnCostConfig,
    pairing_config: CrewPairingGenerationConfig,
    duals: CrewPairingMasterDuals,
    existing_keys: Set[tuple[str, tuple[tuple[str, str], ...]]],
    *,
    pricing_epsilon: float,
    max_columns: int = 1,
) -> CrewPairingPricingResult:
    """Search the fixed-schedule typed Crew DAG without a full pairing pool."""

    if crew.crew_id not in duals.selection_by_crew:
        raise CrewPairingPricingError(
            f"missing selection dual for crew {crew.crew_id!r}"
        )
    required = set(request.required_operated_option_ids)
    allowed = tuple(
        item
        for item in flight_options
        if item.operation_type is FlightOperationType.OPERATE
        and item.option_id in required
    )
    option_by_id = {item.option_id: item for item in allowed}
    all_options = {item.option_id: item for item in flight_options}
    network = build_crew_flight_network(scenario, allowed, crew, pairing_config)
    evaluated: list[CrewPairingPricedColumn] = []
    paths_evaluated = 0
    omitted_paths_evaluated = 0
    duplicates = 0
    pruned: Counter[str] = Counter()

    def emit(path: tuple[CrewLegKey, ...]) -> None:
        nonlocal paths_evaluated, omitted_paths_evaluated, duplicates
        candidate = make_generated_crew_pairing(crew, path)
        audit = validate_generated_crew_pairing(
            scenario, flight_options, crew, candidate, pairing_config
        )
        if not audit.valid:
            raise CrewPairingPricingError(
                f"pricing emitted illegal path {path!r}: {audit.violations}"
            )
        paths_evaluated += 1
        key = pairing_semantic_key(candidate)
        if key in existing_keys:
            duplicates += 1
            return
        omitted_paths_evaluated += 1
        evaluated.append(
            evaluate_crew_pairing_reduced_cost(
                scenario, all_options, candidate, costs, duals
            )
        )

    idle = make_generated_crew_pairing(crew, ())
    if validate_generated_crew_pairing(
        scenario, flight_options, crew, idle, pairing_config
    ).valid:
        emit(())

    def visit(state: CrewPairingPricingState) -> None:
        last_option = option_by_id[state.last_leg.flight_option_id]
        if last_option.destination == crew.required_station_at_T_end:
            emit(state.typed_path)
        for next_key in network.successor_leg_keys[state.last_leg]:
            if next_key.flight_option_id in state.used_option_ids:
                pruned["duplicate_flight_option"] += 1
                continue
            next_option = option_by_id[next_key.flight_option_id]
            base_id = next_option.base_flight_id
            if base_id is not None and base_id in state.used_base_flight_ids:
                pruned["duplicate_base_flight"] += 1
                continue
            next_deadheads = state.deadhead_count + (
                next_key.segment_type is CrewSegmentType.DEADHEAD
            )
            if (
                pairing_config.max_deadhead_legs is not None
                and next_deadheads > pairing_config.max_deadhead_legs
            ):
                pruned["deadhead_limit_violation"] += 1
                continue
            assert next_option.arr_time is not None
            duty_minutes = (
                next_option.arr_time - state.first_departure_time
            ).total_seconds() / 60
            if duty_minutes > pairing_config.max_duty_minutes:
                pruned["duty_time_violation"] += 1
                continue
            visit(
                CrewPairingPricingState(
                    last_leg=next_key,
                    typed_path=(*state.typed_path, next_key),
                    used_option_ids=state.used_option_ids | {next_key.flight_option_id},
                    used_base_flight_ids=state.used_base_flight_ids
                    | (frozenset({base_id}) if base_id is not None else frozenset()),
                    deadhead_count=next_deadheads,
                    first_departure_time=state.first_departure_time,
                    duty_elapsed_minutes=duty_minutes,
                )
            )

    for key in network.start_leg_keys:
        initial_deadheads = int(key.segment_type is CrewSegmentType.DEADHEAD)
        if (
            pairing_config.max_deadhead_legs is not None
            and initial_deadheads > pairing_config.max_deadhead_legs
        ):
            pruned["deadhead_limit_violation"] += 1
            continue
        option = option_by_id[key.flight_option_id]
        assert option.dep_time is not None and option.arr_time is not None
        bases = (
            frozenset({option.base_flight_id})
            if option.base_flight_id is not None
            else frozenset()
        )
        visit(
            CrewPairingPricingState(
                last_leg=key,
                typed_path=(key,),
                used_option_ids=frozenset({key.flight_option_id}),
                used_base_flight_ids=bases,
                deadhead_count=initial_deadheads,
                first_departure_time=option.dep_time,
                duty_elapsed_minutes=(option.arr_time - option.dep_time).total_seconds()
                / 60,
            )
        )

    ordered = tuple(
        sorted(
            evaluated,
            key=lambda item: (
                item.reduced_cost,
                pairing_semantic_key(item.crew_pairing),
            ),
        )
    )
    negative = tuple(item for item in ordered if item.reduced_cost < -pricing_epsilon)[
        :max_columns
    ]
    return CrewPairingPricingResult(
        crew_id=crew.crew_id,
        columns=negative,
        minimum_reduced_cost=ordered[0].reduced_cost if ordered else None,
        paths_evaluated=paths_evaluated,
        omitted_paths_evaluated=omitted_paths_evaluated,
        duplicate_paths_skipped=duplicates,
        resource_pruning_counts=dict(sorted(pruned.items())),
    )
