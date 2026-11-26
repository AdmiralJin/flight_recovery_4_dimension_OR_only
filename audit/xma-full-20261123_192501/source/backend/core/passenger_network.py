from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import timedelta
from types import MappingProxyType

from backend.config.itinerary_generation import PassengerItineraryGenerationConfig
from backend.schemas.columns import FlightOperationType, FlightOption
from backend.schemas.passenger import PassengerCommodity
from backend.schemas.scenario import Scenario


@dataclass(frozen=True)
class PassengerLegEligibility:
    option_id: str
    eligible: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class PassengerFlightNetwork:
    """Deterministic passenger-local DAG over existing revenue options."""

    pax_group_id: str
    min_connection_minutes: int
    option_ids: tuple[str, ...]
    start_option_ids: tuple[str, ...]
    terminal_option_ids: tuple[str, ...]
    successor_option_ids: Mapping[str, tuple[str, ...]]
    rejected_option_reasons: Mapping[str, tuple[str, ...]]
    rejected_edge_counts: Mapping[str, int]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "successor_option_ids",
            MappingProxyType(dict(self.successor_option_ids)),
        )
        object.__setattr__(
            self,
            "rejected_option_reasons",
            MappingProxyType(dict(self.rejected_option_reasons)),
        )
        object.__setattr__(
            self,
            "rejected_edge_counts",
            MappingProxyType(dict(self.rejected_edge_counts)),
        )

    @property
    def node_count(self) -> int:
        return len(self.option_ids) + 2

    @property
    def edge_count(self) -> int:
        return (
            len(self.start_option_ids)
            + sum(len(items) for items in self.successor_option_ids.values())
            + len(self.terminal_option_ids)
        )


def validate_flight_option_for_passenger(
    scenario: Scenario,
    option: FlightOption,
    passenger: PassengerCommodity,
    config: PassengerItineraryGenerationConfig,
) -> PassengerLegEligibility:
    """Check one option against the Phase 7 passenger-local contract."""

    del passenger, config  # Reserved for future versioned passenger eligibility.
    reasons: list[str] = []
    if option.operation_type is not FlightOperationType.OPERATE:
        reasons.append("not_revenue_operate_option")
        return PassengerLegEligibility(option.option_id, False, tuple(reasons))

    flights = {item.flight_id: item for item in scenario.flights}
    airports = {item.airport_id for item in scenario.airports}
    if option.base_flight_id not in flights:
        reasons.append("unknown_base_flight")
    if option.origin not in airports:
        reasons.append("unknown_origin")
    if option.destination not in airports:
        reasons.append("unknown_destination")
    if option.dep_time is None or option.arr_time is None:
        reasons.append("missing_time")
    else:
        if option.dep_time >= option.arr_time:
            reasons.append("invalid_time_order")
        window = scenario.recovery_window
        if option.dep_time < window.start_time or option.arr_time > window.end_time:
            reasons.append("outside_recovery_horizon")
    return PassengerLegEligibility(
        option.option_id,
        not reasons,
        tuple(dict.fromkeys(reasons)),
    )


def _option_order(option: FlightOption) -> tuple[object, ...]:
    return (
        option.dep_time is None,
        option.dep_time,
        option.arr_time is None,
        option.arr_time,
        option.option_id,
    )


def build_passenger_flight_network(
    scenario: Scenario,
    flight_options: Sequence[FlightOption],
    passenger: PassengerCommodity,
    config: PassengerItineraryGenerationConfig,
) -> PassengerFlightNetwork:
    options = {item.option_id: item for item in flight_options}
    if len(options) != len(flight_options):
        raise ValueError("flight option IDs must be unique")

    ordered_options = tuple(sorted(flight_options, key=_option_order))
    rejected: dict[str, tuple[str, ...]] = {}
    eligible: list[FlightOption] = []
    for option in ordered_options:
        audit = validate_flight_option_for_passenger(
            scenario, option, passenger, config
        )
        if audit.eligible:
            eligible.append(option)
        else:
            rejected[option.option_id] = audit.reasons

    starts = tuple(
        item.option_id
        for item in eligible
        if item.origin == passenger.origin
        and item.dep_time is not None
        and item.dep_time >= passenger.original_departure
    )
    terminals = tuple(
        item.option_id for item in eligible if item.destination == passenger.destination
    )
    successors: dict[str, tuple[str, ...]] = {}
    rejected_edges: Counter[str] = Counter()
    mct = timedelta(minutes=config.default_mct_minutes)
    for left in eligible:
        accepted: list[str] = []
        for right in eligible:
            if left.option_id == right.option_id:
                continue
            if left.base_flight_id == right.base_flight_id:
                rejected_edges["same_base_flight"] += 1
                continue
            if left.destination != right.origin:
                rejected_edges["station_mismatch"] += 1
                continue
            assert left.arr_time is not None and right.dep_time is not None
            if left.arr_time > right.dep_time:
                rejected_edges["time_overlap"] += 1
                continue
            if left.arr_time + mct > right.dep_time:
                rejected_edges["mct_violation"] += 1
                continue
            accepted.append(right.option_id)
        successors[left.option_id] = tuple(accepted)

    return PassengerFlightNetwork(
        pax_group_id=passenger.pax_group_id,
        min_connection_minutes=config.default_mct_minutes,
        option_ids=tuple(item.option_id for item in eligible),
        start_option_ids=starts,
        terminal_option_ids=terminals,
        successor_option_ids=successors,
        rejected_option_reasons=rejected,
        rejected_edge_counts=dict(sorted(rejected_edges.items())),
    )
