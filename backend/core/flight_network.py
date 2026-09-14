from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import timedelta
from types import MappingProxyType

from backend.config.string_generation import FlightStringGenerationConfig
from backend.schemas.aircraft import Aircraft
from backend.schemas.columns import FlightOperationType, FlightOption
from backend.schemas.common import minutes_between
from backend.schemas.scenario import Scenario


HARD_DEPARTURE_RESTRICTIONS = frozenset({"closed", "departure_closed"})
HARD_ARRIVAL_RESTRICTIONS = frozenset({"closed", "arrival_closed"})


@dataclass(frozen=True)
class FlightLegEligibility:
    option_id: str
    eligible: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class AircraftFlightNetwork:
    """Deterministic aircraft-local DAG over eligible Flight Options."""

    aircraft_id: str
    min_turn_minutes: int
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


def _interval_restrictions(
    scenario: Scenario, airport: str, timestamp, *, departure: bool
) -> tuple[str, ...]:
    intervals = tuple(
        item
        for item in scenario.airport_intervals
        if item.airport == airport
        and item.start_time <= timestamp < item.end_time
    )
    reasons: list[str] = []
    if len(intervals) > 1:
        reasons.append(
            "ambiguous_departure_interval"
            if departure
            else "ambiguous_arrival_interval"
        )
    hard_restrictions = (
        HARD_DEPARTURE_RESTRICTIONS if departure else HARD_ARRIVAL_RESTRICTIONS
    )
    for interval in intervals:
        if interval.curfew_flag:
            reasons.append("departure_curfew" if departure else "arrival_curfew")
        if hard_restrictions.intersection(interval.weather_restrictions):
            reasons.append(
                "departure_local_closure"
                if departure
                else "arrival_local_closure"
            )
    return tuple(dict.fromkeys(reasons))


def validate_flight_option_for_aircraft(
    scenario: Scenario,
    option: FlightOption,
    aircraft: Aircraft,
) -> FlightLegEligibility:
    """Independently check one option's aircraft-local Phase 5 eligibility."""

    reasons: list[str] = []
    flights = {item.flight_id: item for item in scenario.flights}
    airports = {item.airport_id for item in scenario.airports}
    if option.operation_type is FlightOperationType.CANCEL:
        reasons.append("cancel_excluded")
        return FlightLegEligibility(option.option_id, False, tuple(reasons))
    if option.origin is None or option.destination is None:
        reasons.append("missing_route")
    else:
        if option.origin not in airports:
            reasons.append("unknown_origin")
        if option.destination not in airports:
            reasons.append("unknown_destination")
    if option.dep_time is None or option.arr_time is None:
        reasons.append("missing_times")
    else:
        if (
            option.dep_time < scenario.recovery_window.start_time
            or option.arr_time > scenario.recovery_window.end_time
        ):
            reasons.append("outside_recovery_horizon")
        if option.dep_time >= option.arr_time:
            reasons.append("invalid_time_order")
        if option.block_minutes is not None:
            try:
                if minutes_between(option.dep_time, option.arr_time) != option.block_minutes:
                    reasons.append("block_time_mismatch")
            except ValueError:
                reasons.append("block_time_mismatch")
        if option.origin in airports:
            reasons.extend(
                _interval_restrictions(
                    scenario, option.origin, option.dep_time, departure=True
                )
            )
        if option.destination in airports:
            reasons.extend(
                _interval_restrictions(
                    scenario, option.destination, option.arr_time, departure=False
                )
            )

    if option.operation_type is FlightOperationType.OPERATE:
        base = flights.get(option.base_flight_id or "")
        if base is None:
            reasons.append("unknown_base_flight")
        else:
            if base.original_equipment != aircraft.equipment_type:
                reasons.append("equipment_mismatch")
            if option.departure_delay_minutes is None:
                reasons.append("missing_departure_delay")
            else:
                if option.departure_delay_minutes > base.max_delay:
                    reasons.append("max_delay_exceeded")
                if option.dep_time is not None:
                    try:
                        actual_delay = minutes_between(base.sched_dep, option.dep_time)
                    except ValueError:
                        reasons.append("departure_delay_mismatch")
                    else:
                        if actual_delay != option.departure_delay_minutes:
                            reasons.append("departure_delay_mismatch")

    return FlightLegEligibility(
        option_id=option.option_id,
        eligible=not reasons,
        reasons=tuple(dict.fromkeys(reasons)),
    )


def _option_order(option: FlightOption) -> tuple[object, ...]:
    return (
        option.dep_time.isoformat() if option.dep_time is not None else "9999",
        option.arr_time.isoformat() if option.arr_time is not None else "9999",
        option.option_id,
    )


def build_aircraft_flight_network(
    scenario: Scenario,
    flight_options: Sequence[FlightOption],
    aircraft: Aircraft,
    config: FlightStringGenerationConfig,
) -> AircraftFlightNetwork:
    """Build start/option/terminal arcs for one aircraft without global constraints."""

    ordered_options = tuple(sorted(flight_options, key=_option_order))
    eligible: list[FlightOption] = []
    rejected_options: dict[str, tuple[str, ...]] = {}
    for option in ordered_options:
        result = validate_flight_option_for_aircraft(scenario, option, aircraft)
        if result.eligible:
            eligible.append(option)
        else:
            rejected_options[option.option_id] = result.reasons

    min_turn = config.min_turn_minutes(aircraft.equipment_type)
    start_ids = tuple(
        item.option_id
        for item in eligible
        if item.origin == aircraft.initial_station_at_t
    )
    terminal_ids = tuple(
        item.option_id
        for item in eligible
        if item.destination == aircraft.required_station_at_T_end
    )
    successors: dict[str, tuple[str, ...]] = {}
    rejected_edges: Counter[str] = Counter()
    for left in eligible:
        related: list[str] = []
        assert left.arr_time is not None
        for right in eligible:
            if left.option_id == right.option_id:
                continue
            assert right.dep_time is not None
            if (
                left.base_flight_id is not None
                and left.base_flight_id == right.base_flight_id
            ):
                rejected_edges["same_base_flight"] += 1
                continue
            if left.destination != right.origin:
                rejected_edges["station_mismatch"] += 1
                continue
            if left.arr_time + timedelta(minutes=min_turn) > right.dep_time:
                rejected_edges["turn_time_violation"] += 1
                continue
            related.append(right.option_id)
        successors[left.option_id] = tuple(related)

    return AircraftFlightNetwork(
        aircraft_id=aircraft.tail_id,
        min_turn_minutes=min_turn,
        option_ids=tuple(item.option_id for item in eligible),
        start_option_ids=start_ids,
        terminal_option_ids=terminal_ids,
        successor_option_ids=successors,
        rejected_option_reasons=rejected_options,
        rejected_edge_counts=dict(sorted(rejected_edges.items())),
    )
