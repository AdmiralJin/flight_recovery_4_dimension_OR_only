from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import timedelta
from types import MappingProxyType

from backend.config.pairing_generation import CrewPairingGenerationConfig
from backend.schemas.columns import (
    CrewSegmentType,
    FlightOperationType,
    FlightOption,
)
from backend.schemas.crew import Crew
from backend.schemas.scenario import Scenario


@dataclass(frozen=True, order=True)
class CrewLegKey:
    segment_type: CrewSegmentType
    flight_option_id: str


@dataclass(frozen=True)
class CrewLegEligibility:
    key: CrewLegKey
    eligible: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class CrewFlightNetwork:
    """Deterministic crew-local DAG over OPERATE and DEADHEAD legs."""

    crew_id: str
    min_connection_minutes: int
    max_duty_minutes: int
    leg_keys: tuple[CrewLegKey, ...]
    start_leg_keys: tuple[CrewLegKey, ...]
    terminal_leg_keys: tuple[CrewLegKey, ...]
    successor_leg_keys: Mapping[CrewLegKey, tuple[CrewLegKey, ...]]
    rejected_leg_reasons: Mapping[CrewLegKey, tuple[str, ...]]
    rejected_edge_counts: Mapping[str, int]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "successor_leg_keys", MappingProxyType(dict(self.successor_leg_keys))
        )
        object.__setattr__(
            self,
            "rejected_leg_reasons",
            MappingProxyType(dict(self.rejected_leg_reasons)),
        )
        object.__setattr__(
            self,
            "rejected_edge_counts",
            MappingProxyType(dict(self.rejected_edge_counts)),
        )

    @property
    def node_count(self) -> int:
        return len(self.leg_keys) + 2

    @property
    def edge_count(self) -> int:
        return (
            len(self.start_leg_keys)
            + sum(len(items) for items in self.successor_leg_keys.values())
            + len(self.terminal_leg_keys)
        )


def validate_flight_option_for_crew(
    scenario: Scenario,
    option: FlightOption,
    crew: Crew,
    segment_type: CrewSegmentType,
    config: CrewPairingGenerationConfig,
) -> CrewLegEligibility:
    """Check one typed flight leg against the Phase 6 v1 local contract."""

    key = CrewLegKey(segment_type, option.option_id)
    reasons: list[str] = []
    if segment_type not in {CrewSegmentType.OPERATE, CrewSegmentType.DEADHEAD}:
        reasons.append("unsupported_segment_type")
        return CrewLegEligibility(key, False, tuple(reasons))
    if segment_type is CrewSegmentType.DEADHEAD and not config.allow_deadhead:
        reasons.append("deadhead_disabled")
    if option.operation_type is not FlightOperationType.OPERATE:
        reasons.append("not_revenue_operate_option")
        return CrewLegEligibility(key, False, tuple(dict.fromkeys(reasons)))

    flights = {item.flight_id: item for item in scenario.flights}
    airports = {item.airport_id for item in scenario.airports}
    base = flights.get(option.base_flight_id or "")
    if base is None:
        reasons.append("unknown_base_flight")
    elif (
        segment_type is CrewSegmentType.OPERATE
        and base.original_equipment != crew.rating
    ):
        reasons.append("qualification_mismatch")

    if option.origin not in airports:
        reasons.append("unknown_origin")
    if option.destination not in airports:
        reasons.append("unknown_destination")
    if option.dep_time is None or option.arr_time is None:
        reasons.append("missing_time")
    else:
        window = scenario.recovery_window
        if option.dep_time < window.start_time or option.arr_time > window.end_time:
            reasons.append("recovery_horizon_violation")
        if option.dep_time >= option.arr_time:
            reasons.append("invalid_time_order")
    return CrewLegEligibility(key, not reasons, tuple(dict.fromkeys(reasons)))


def _leg_order(
    key: CrewLegKey, options: Mapping[str, FlightOption]
) -> tuple[object, ...]:
    option = options[key.flight_option_id]
    return (
        option.dep_time,
        option.arr_time,
        option.option_id,
        0 if key.segment_type is CrewSegmentType.OPERATE else 1,
    )


def build_crew_flight_network(
    scenario: Scenario,
    flight_options: Sequence[FlightOption],
    crew: Crew,
    config: CrewPairingGenerationConfig,
) -> CrewFlightNetwork:
    """Build a crew-local DAG; path-level duty and duplicate checks stay in DFS."""

    options = {item.option_id: item for item in flight_options}
    if len(options) != len(flight_options):
        raise ValueError("flight option IDs must be unique")

    rejected: dict[CrewLegKey, tuple[str, ...]] = {}
    eligible: list[CrewLegKey] = []
    for option in flight_options:
        for segment_type in (CrewSegmentType.OPERATE, CrewSegmentType.DEADHEAD):
            audit = validate_flight_option_for_crew(
                scenario, option, crew, segment_type, config
            )
            if audit.eligible:
                eligible.append(audit.key)
            else:
                rejected[audit.key] = audit.reasons
    eligible.sort(key=lambda item: _leg_order(item, options))

    starts = tuple(
        key
        for key in eligible
        if options[key.flight_option_id].origin == crew.start_station_at_t
    )
    terminals = tuple(
        key
        for key in eligible
        if options[key.flight_option_id].destination == crew.required_station_at_T_end
    )
    successors: dict[CrewLegKey, tuple[CrewLegKey, ...]] = {}
    rejected_edges: Counter[str] = Counter()
    connection = timedelta(minutes=config.default_min_connection_minutes)
    for left_key in eligible:
        left = options[left_key.flight_option_id]
        accepted: list[CrewLegKey] = []
        for right_key in eligible:
            right = options[right_key.flight_option_id]
            if left_key == right_key:
                continue
            if left.destination != right.origin:
                rejected_edges["station_mismatch"] += 1
                continue
            assert left.arr_time is not None and right.dep_time is not None
            if left.arr_time > right.dep_time:
                rejected_edges["time_overlap"] += 1
                continue
            if left.arr_time + connection > right.dep_time:
                rejected_edges["min_connection_violation"] += 1
                continue
            accepted.append(right_key)
        successors[left_key] = tuple(accepted)

    return CrewFlightNetwork(
        crew_id=crew.crew_id,
        min_connection_minutes=config.default_min_connection_minutes,
        max_duty_minutes=config.max_duty_minutes,
        leg_keys=tuple(eligible),
        start_leg_keys=starts,
        terminal_leg_keys=terminals,
        successor_leg_keys=successors,
        rejected_leg_reasons=rejected,
        rejected_edge_counts=dict(sorted(rejected_edges.items())),
    )
