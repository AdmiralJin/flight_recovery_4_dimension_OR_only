from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType

from backend.schemas.columns import FlightOperationType, RecoveryColumns
from backend.schemas.scenario import Scenario

from .indices import CapacityIntervalKey


class GateInventoryBuildError(ValueError):
    """The provisional aggregate Gate Inventory coefficients are not auditable."""


@dataclass(frozen=True)
class GateCheckpoint:
    """Cumulative aggregate ground-inventory expression at one checkpoint."""

    checkpoint_id: str
    airport: str
    timestamp: datetime
    capacity_source_key: CapacityIntervalKey
    gate_capacity: int
    initial_ground: int
    cumulative_arrival_option_ids: tuple[str, ...]
    cumulative_departure_option_ids: tuple[str, ...]
    coefficient_by_option: Mapping[str, int]


@dataclass(frozen=True)
class GateInventoryData:
    checkpoints: tuple[GateCheckpoint, ...]
    initial_ground_by_airport: Mapping[str, int]

    def checkpoints_for_airport(self, airport: str) -> tuple[GateCheckpoint, ...]:
        if airport not in self.initial_ground_by_airport:
            raise KeyError(f"unknown gate-inventory airport: {airport!r}")
        return tuple(item for item in self.checkpoints if item.airport == airport)


def _capacity_key(interval) -> CapacityIntervalKey:
    return CapacityIntervalKey(
        airport=interval.airport,
        start_time=interval.start_time,
        end_time=interval.end_time,
    )


def _checkpoint_id(airport: str, timestamp: datetime) -> str:
    return f"{airport}@{timestamp.isoformat()}"


def _resolve_gate_capacity(airport: str, timestamp: datetime, intervals):
    covering = [
        interval
        for interval in intervals
        if interval.start_time <= timestamp < interval.end_time
    ]
    if len(covering) > 1:
        raise GateInventoryBuildError(
            f"overlapping gate-capacity intervals cover {airport!r} at {timestamp.isoformat()}"
        )
    if covering:
        interval = covering[0]
        return _capacity_key(interval), interval.gate_capacity

    capacities = {interval.gate_capacity for interval in intervals}
    if len(capacities) != 1:
        raise GateInventoryBuildError(
            f"uncovered gate checkpoint for {airport!r} at {timestamp.isoformat()} "
            "has no unambiguous provisional gate capacity"
        )
    interval = intervals[0]
    return _capacity_key(interval), interval.gate_capacity


def build_gate_inventory_data(
    scenario: Scenario,
    columns: RecoveryColumns,
) -> GateInventoryData:
    """Build deterministic Phase 2.2 provisional aggregate Gate coefficients.

    Revenue operate options contribute movements. Cancel and ferry options are
    intentionally excluded from this single-model SRM proxy.
    """

    airport_ids = tuple(airport.airport_id for airport in scenario.airports)
    airport_set = set(airport_ids)
    intervals_by_airport = {airport_id: [] for airport_id in airport_ids}
    for interval in scenario.airport_intervals:
        if interval.airport not in airport_set:
            raise GateInventoryBuildError(
                f"gate-capacity interval references unknown airport {interval.airport!r}"
            )
        intervals_by_airport[interval.airport].append(interval)

    initial_ground = {airport_id: 0 for airport_id in airport_ids}
    for aircraft in scenario.aircraft:
        if aircraft.initial_station_at_t not in airport_set:
            raise GateInventoryBuildError(
                f"aircraft {aircraft.tail_id!r} starts at unknown airport "
                f"{aircraft.initial_station_at_t!r}"
            )
        initial_ground[aircraft.initial_station_at_t] += 1

    seen_options: set[str] = set()
    operated_options = []
    active_airports = {
        airport_id for airport_id, count in initial_ground.items() if count > 0
    }
    for option in columns.flight_options:
        if option.option_id in seen_options:
            raise GateInventoryBuildError(
                f"duplicate flight option ID in gate builder: {option.option_id!r}"
            )
        seen_options.add(option.option_id)
        if option.operation_type is not FlightOperationType.OPERATE:
            continue
        if option.origin not in airport_set or option.destination not in airport_set:
            raise GateInventoryBuildError(
                f"option {option.option_id!r} has an unknown movement airport"
            )
        if option.dep_time is None or option.arr_time is None:
            raise GateInventoryBuildError(
                f"operate option {option.option_id!r} is missing movement times"
            )
        active_airports.update((option.origin, option.destination))
        operated_options.append(option)

    for airport_id in active_airports:
        if not intervals_by_airport[airport_id]:
            raise GateInventoryBuildError(
                f"airport {airport_id!r} has gate inventory but no AirportInterval"
            )

    checkpoints: list[GateCheckpoint] = []
    for airport_id in airport_ids:
        intervals = intervals_by_airport[airport_id]
        if not intervals:
            continue
        checkpoint_times = {scenario.recovery_window.start_time}
        for interval in intervals:
            checkpoint_times.add(interval.start_time)
            checkpoint_times.add(interval.end_time)
        for option in operated_options:
            if option.origin == airport_id:
                checkpoint_times.add(option.dep_time)
            if option.destination == airport_id:
                checkpoint_times.add(option.arr_time)

        start_key, start_capacity = _resolve_gate_capacity(
            airport_id, scenario.recovery_window.start_time, intervals
        )
        if initial_ground[airport_id] > start_capacity:
            raise GateInventoryBuildError(
                f"initial ground inventory {initial_ground[airport_id]} at {airport_id!r} "
                f"exceeds provisional gate capacity {start_capacity} from {start_key!r}"
            )

        for timestamp in sorted(checkpoint_times):
            capacity_key, gate_capacity = _resolve_gate_capacity(
                airport_id, timestamp, intervals
            )
            arrivals = tuple(
                option.option_id
                for option in operated_options
                if option.destination == airport_id and option.arr_time <= timestamp
            )
            departures = tuple(
                option.option_id
                for option in operated_options
                if option.origin == airport_id and option.dep_time <= timestamp
            )
            coefficients: dict[str, int] = {}
            for option_id in arrivals:
                coefficients[option_id] = coefficients.get(option_id, 0) + 1
            for option_id in departures:
                coefficients[option_id] = coefficients.get(option_id, 0) - 1
            coefficients = {
                option_id: value
                for option_id, value in coefficients.items()
                if value != 0
            }
            checkpoints.append(
                GateCheckpoint(
                    checkpoint_id=_checkpoint_id(airport_id, timestamp),
                    airport=airport_id,
                    timestamp=timestamp,
                    capacity_source_key=capacity_key,
                    gate_capacity=gate_capacity,
                    initial_ground=initial_ground[airport_id],
                    cumulative_arrival_option_ids=arrivals,
                    cumulative_departure_option_ids=departures,
                    coefficient_by_option=MappingProxyType(coefficients),
                )
            )

    return GateInventoryData(
        checkpoints=tuple(checkpoints),
        initial_ground_by_airport=MappingProxyType(initial_ground),
    )
