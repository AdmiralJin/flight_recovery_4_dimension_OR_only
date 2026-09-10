from __future__ import annotations

from collections.abc import Hashable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Generic, TypeVar

from backend.schemas.columns import FlightOperationType, RecoveryColumns
from backend.schemas.scenario import Scenario


IdT = TypeVar("IdT", bound=Hashable)


@dataclass(frozen=True)
class OrderedIndex(Generic[IdT]):
    """An immutable, order-preserving bidirectional ID index."""

    ids: tuple[IdT, ...]
    position: Mapping[IdT, int] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        positions: dict[IdT, int] = {}
        for index, item_id in enumerate(self.ids):
            if item_id in positions:
                raise ValueError(f"duplicate index ID: {item_id!r}")
            positions[item_id] = index
        object.__setattr__(self, "position", MappingProxyType(positions))

    @classmethod
    def from_ids(cls, ids: Iterable[IdT]) -> OrderedIndex[IdT]:
        return cls(tuple(ids))

    def position_of(self, item_id: IdT) -> int:
        """Return the zero-based position, raising KeyError for an unknown ID."""

        return self.position[item_id]

    def id_at(self, position: int) -> IdT:
        """Return the business ID at a zero-based position."""

        return self.ids[position]

    def __contains__(self, item_id: object) -> bool:
        return item_id in self.position

    def __len__(self) -> int:
        return len(self.ids)


@dataclass(frozen=True)
class CapacityIntervalKey:
    """Structured identity for one airport-capacity interval."""

    airport: str
    start_time: datetime
    end_time: datetime


@dataclass(frozen=True)
class RecoveryIndices:
    """All deterministic indices required by the Phase 2 fixed-column models."""

    flights: OrderedIndex[str]
    flight_options: OrderedIndex[str]
    operate_options: OrderedIndex[str]
    cancel_options: OrderedIndex[str]
    ferry_options: OrderedIndex[str]
    revenue_operate_options: OrderedIndex[str]
    aircraft: OrderedIndex[str]
    aircraft_strings: OrderedIndex[str]
    crew: OrderedIndex[str]
    crew_pairings: OrderedIndex[str]
    passenger_groups: OrderedIndex[str]
    passenger_itineraries: OrderedIndex[str]
    maintenance_aircraft: OrderedIndex[str]
    capacity_intervals: OrderedIndex[CapacityIntervalKey]


def build_recovery_indices(
    scenario: Scenario,
    columns: RecoveryColumns,
) -> RecoveryIndices:
    """Build indices in the explicit order of the validated input documents."""

    return RecoveryIndices(
        flights=OrderedIndex.from_ids(flight.flight_id for flight in scenario.flights),
        flight_options=OrderedIndex.from_ids(
            option.option_id for option in columns.flight_options
        ),
        operate_options=OrderedIndex.from_ids(
            option.option_id
            for option in columns.flight_options
            if option.operation_type is FlightOperationType.OPERATE
        ),
        cancel_options=OrderedIndex.from_ids(
            option.option_id
            for option in columns.flight_options
            if option.operation_type is FlightOperationType.CANCEL
        ),
        ferry_options=OrderedIndex.from_ids(
            option.option_id
            for option in columns.flight_options
            if option.operation_type is FlightOperationType.FERRY
        ),
        revenue_operate_options=OrderedIndex.from_ids(
            option.option_id
            for option in columns.flight_options
            if option.operation_type is FlightOperationType.OPERATE
            and option.base_flight_id is not None
        ),
        aircraft=OrderedIndex.from_ids(item.tail_id for item in scenario.aircraft),
        aircraft_strings=OrderedIndex.from_ids(
            item.string_id for item in columns.aircraft_strings
        ),
        crew=OrderedIndex.from_ids(item.crew_id for item in scenario.crew),
        crew_pairings=OrderedIndex.from_ids(
            item.pairing_id for item in columns.crew_pairings
        ),
        passenger_groups=OrderedIndex.from_ids(
            item.pax_group_id for item in scenario.passengers
        ),
        passenger_itineraries=OrderedIndex.from_ids(
            item.itinerary_id for item in columns.passenger_itineraries
        ),
        maintenance_aircraft=OrderedIndex.from_ids(
            item.tail_id for item in scenario.aircraft if item.maintenance_required
        ),
        capacity_intervals=OrderedIndex.from_ids(
            CapacityIntervalKey(
                airport=interval.airport,
                start_time=interval.start_time,
                end_time=interval.end_time,
            )
            for interval in scenario.airport_intervals
        ),
    )
