from __future__ import annotations

from collections.abc import Hashable, Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Generic, TypeVar

from backend.schemas.columns import (
    CrewSegmentType,
    FlightOperationType,
    PassengerSegmentType,
    RecoveryColumns,
)
from backend.schemas.scenario import Scenario

from .indices import CapacityIntervalKey, RecoveryIndices, build_recovery_indices


RowT = TypeVar("RowT", bound=Hashable)
ColumnT = TypeVar("ColumnT", bound=Hashable)


@dataclass(frozen=True, init=False)
class BinaryIncidence(Generic[RowT, ColumnT]):
    """Immutable binary relation with deterministic row and column traversal."""

    rows: tuple[RowT, ...]
    columns: tuple[ColumnT, ...]
    row_to_columns: Mapping[RowT, frozenset[ColumnT]]
    column_to_rows: Mapping[ColumnT, frozenset[RowT]]

    def __init__(
        self,
        rows: Iterable[RowT],
        columns: Iterable[ColumnT],
        edges: Iterable[tuple[RowT, ColumnT]] = (),
    ) -> None:
        row_ids = tuple(rows)
        column_ids = tuple(columns)
        if len(row_ids) != len(set(row_ids)):
            raise ValueError("binary incidence rows must be unique")
        if len(column_ids) != len(set(column_ids)):
            raise ValueError("binary incidence columns must be unique")

        by_row: dict[RowT, set[ColumnT]] = {row_id: set() for row_id in row_ids}
        by_column: dict[ColumnT, set[RowT]] = {
            column_id: set() for column_id in column_ids
        }
        seen: set[tuple[RowT, ColumnT]] = set()
        for edge in edges:
            row_id, column_id = edge
            if row_id not in by_row:
                raise KeyError(f"unknown incidence row: {row_id!r}")
            if column_id not in by_column:
                raise KeyError(f"unknown incidence column: {column_id!r}")
            if edge in seen:
                raise ValueError(f"duplicate incidence edge: {edge!r}")
            seen.add(edge)
            by_row[row_id].add(column_id)
            by_column[column_id].add(row_id)

        object.__setattr__(self, "rows", row_ids)
        object.__setattr__(self, "columns", column_ids)
        object.__setattr__(
            self,
            "row_to_columns",
            MappingProxyType(
                {row_id: frozenset(values) for row_id, values in by_row.items()}
            ),
        )
        object.__setattr__(
            self,
            "column_to_rows",
            MappingProxyType(
                {
                    column_id: frozenset(values)
                    for column_id, values in by_column.items()
                }
            ),
        )

    def contains(self, row_id: RowT, column_id: ColumnT) -> bool:
        self._require_row(row_id)
        self._require_column(column_id)
        return column_id in self.row_to_columns[row_id]

    def columns_for_row(self, row_id: RowT) -> tuple[ColumnT, ...]:
        """Return related columns in the declared column-index order."""

        self._require_row(row_id)
        related = self.row_to_columns[row_id]
        return tuple(column_id for column_id in self.columns if column_id in related)

    def rows_for_column(self, column_id: ColumnT) -> tuple[RowT, ...]:
        """Return related rows in the declared row-index order."""

        self._require_column(column_id)
        related = self.column_to_rows[column_id]
        return tuple(row_id for row_id in self.rows if row_id in related)

    def _require_row(self, row_id: RowT) -> None:
        if row_id not in self.row_to_columns:
            raise KeyError(f"unknown incidence row: {row_id!r}")

    def _require_column(self, column_id: ColumnT) -> None:
        if column_id not in self.column_to_rows:
            raise KeyError(f"unknown incidence column: {column_id!r}")


@dataclass(frozen=True)
class RecoveryIncidence:
    """Phase 2.0 entity-choice, operational, and movement incidences.

    Gate incidence intentionally deferred.
    """

    base_flight_to_options: BinaryIncidence[str, str]
    aircraft_to_strings: BinaryIncidence[str, str]
    crew_to_pairings: BinaryIncidence[str, str]
    passenger_group_to_itineraries: BinaryIncidence[str, str]

    option_to_aircraft_strings: BinaryIncidence[str, str]
    option_to_operating_pairings: BinaryIncidence[str, str]
    option_to_deadhead_pairings: BinaryIncidence[str, str]
    option_to_passenger_itineraries: BinaryIncidence[str, str]

    maintenance_to_strings: BinaryIncidence[str, str]

    departure_capacity_to_options: BinaryIncidence[CapacityIntervalKey, str]
    arrival_capacity_to_options: BinaryIncidence[CapacityIntervalKey, str]


def _checked_indices(
    scenario: Scenario,
    columns: RecoveryColumns,
    indices: RecoveryIndices | None,
) -> RecoveryIndices:
    expected = build_recovery_indices(scenario, columns)
    if indices is not None and indices != expected:
        raise ValueError("provided recovery indices do not match scenario and columns")
    return indices or expected


def build_recovery_incidence(
    scenario: Scenario,
    columns: RecoveryColumns,
    indices: RecoveryIndices | None = None,
) -> RecoveryIncidence:
    """Transform validated Scenario and RecoveryColumns into binary incidences.

    This is deliberately defensive at relation boundaries, but it does not replace
    the Phase 1 semantic validators.
    """

    indices = _checked_indices(scenario, columns, indices)
    options = {option.option_id: option for option in columns.flight_options}
    aircraft = {item.tail_id: item for item in scenario.aircraft}

    base_flight_edges: list[tuple[str, str]] = []
    for option in columns.flight_options:
        if option.operation_type is FlightOperationType.FERRY:
            if option.base_flight_id is not None:
                raise ValueError(
                    f"ferry option {option.option_id!r} cannot reference a base flight"
                )
            continue
        if option.base_flight_id not in indices.flights:
            raise ValueError(
                f"option {option.option_id!r} references unknown base flight "
                f"{option.base_flight_id!r}"
            )
        base_flight_edges.append((option.base_flight_id, option.option_id))  # type: ignore[arg-type]

    aircraft_choice_edges: list[tuple[str, str]] = []
    option_aircraft_edges: list[tuple[str, str]] = []
    for string in columns.aircraft_strings:
        if string.aircraft_id not in indices.aircraft:
            raise ValueError(
                f"aircraft string {string.string_id!r} references unknown aircraft "
                f"{string.aircraft_id!r}"
            )
        aircraft_choice_edges.append((string.aircraft_id, string.string_id))
        for option_id in string.leg_option_ids:
            option = options.get(option_id)
            if option is None:
                raise ValueError(
                    f"aircraft string {string.string_id!r} references unknown option "
                    f"{option_id!r}"
                )
            if option.operation_type is FlightOperationType.CANCEL:
                raise ValueError(
                    f"aircraft string {string.string_id!r} cannot cover cancel option "
                    f"{option_id!r}"
                )
            option_aircraft_edges.append((option_id, string.string_id))

    crew_choice_edges: list[tuple[str, str]] = []
    operating_pairing_edges: list[tuple[str, str]] = []
    deadhead_pairing_edges: list[tuple[str, str]] = []
    for pairing in columns.crew_pairings:
        if pairing.crew_id not in indices.crew:
            raise ValueError(
                f"crew pairing {pairing.pairing_id!r} references unknown crew "
                f"{pairing.crew_id!r}"
            )
        crew_choice_edges.append((pairing.crew_id, pairing.pairing_id))
        for duty in pairing.duties:
            for segment in duty.segments:
                if segment.segment_type not in {
                    CrewSegmentType.OPERATE,
                    CrewSegmentType.DEADHEAD,
                }:
                    continue
                option_id = segment.flight_option_id
                option = options.get(option_id or "")
                if option is None:
                    raise ValueError(
                        f"crew pairing {pairing.pairing_id!r} references unknown option "
                        f"{option_id!r}"
                    )
                if option.operation_type is FlightOperationType.CANCEL:
                    raise ValueError(
                        f"crew pairing {pairing.pairing_id!r} cannot use cancel option "
                        f"{option_id!r}"
                    )
                edge = (option.option_id, pairing.pairing_id)
                if segment.segment_type is CrewSegmentType.OPERATE:
                    operating_pairing_edges.append(edge)
                else:
                    deadhead_pairing_edges.append(edge)

    passenger_choice_edges: list[tuple[str, str]] = []
    passenger_option_edges: list[tuple[str, str]] = []
    for itinerary in columns.passenger_itineraries:
        if itinerary.pax_group_id not in indices.passenger_groups:
            raise ValueError(
                f"passenger itinerary {itinerary.itinerary_id!r} references unknown group "
                f"{itinerary.pax_group_id!r}"
            )
        passenger_choice_edges.append(
            (itinerary.pax_group_id, itinerary.itinerary_id)
        )
        for segment in itinerary.segments:
            if segment.segment_type is not PassengerSegmentType.FLIGHT:
                continue
            option_id = segment.flight_option_id
            option = options.get(option_id or "")
            if option is None:
                raise ValueError(
                    f"passenger itinerary {itinerary.itinerary_id!r} references unknown "
                    f"option {option_id!r}"
                )
            if option.operation_type is not FlightOperationType.OPERATE:
                raise ValueError(
                    f"passenger itinerary {itinerary.itinerary_id!r} cannot use "
                    f"{option.operation_type.value} option {option.option_id!r}"
                )
            passenger_option_edges.append((option.option_id, itinerary.itinerary_id))

    maintenance_edges: list[tuple[str, str]] = []
    for string in columns.aircraft_strings:
        resource = aircraft.get(string.aircraft_id)
        if resource is None:
            continue
        if (
            resource.maintenance_required
            and string.maintenance_satisfied
            and string.end_station in resource.maintenance_stations
        ):
            maintenance_edges.append((resource.tail_id, string.string_id))

    departure_edges: list[tuple[CapacityIntervalKey, str]] = []
    arrival_edges: list[tuple[CapacityIntervalKey, str]] = []
    for key, interval in zip(
        indices.capacity_intervals.ids, scenario.airport_intervals
    ):
        for option in columns.flight_options:
            if option.operation_type not in {
                FlightOperationType.OPERATE,
                FlightOperationType.FERRY,
            }:
                continue
            if (
                option.origin == interval.airport
                and option.dep_time is not None
                and interval.start_time <= option.dep_time < interval.end_time
            ):
                departure_edges.append((key, option.option_id))
            if (
                option.destination == interval.airport
                and option.arr_time is not None
                and interval.start_time <= option.arr_time < interval.end_time
            ):
                arrival_edges.append((key, option.option_id))

    option_ids = indices.flight_options.ids
    string_ids = indices.aircraft_strings.ids
    pairing_ids = indices.crew_pairings.ids
    itinerary_ids = indices.passenger_itineraries.ids

    return RecoveryIncidence(
        base_flight_to_options=BinaryIncidence(
            indices.flights.ids, option_ids, base_flight_edges
        ),
        aircraft_to_strings=BinaryIncidence(
            indices.aircraft.ids, string_ids, aircraft_choice_edges
        ),
        crew_to_pairings=BinaryIncidence(
            indices.crew.ids, pairing_ids, crew_choice_edges
        ),
        passenger_group_to_itineraries=BinaryIncidence(
            indices.passenger_groups.ids, itinerary_ids, passenger_choice_edges
        ),
        option_to_aircraft_strings=BinaryIncidence(
            option_ids, string_ids, option_aircraft_edges
        ),
        option_to_operating_pairings=BinaryIncidence(
            option_ids, pairing_ids, operating_pairing_edges
        ),
        option_to_deadhead_pairings=BinaryIncidence(
            option_ids, pairing_ids, deadhead_pairing_edges
        ),
        option_to_passenger_itineraries=BinaryIncidence(
            option_ids, itinerary_ids, passenger_option_edges
        ),
        maintenance_to_strings=BinaryIncidence(
            indices.maintenance_aircraft.ids, string_ids, maintenance_edges
        ),
        departure_capacity_to_options=BinaryIncidence(
            indices.capacity_intervals.ids, option_ids, departure_edges
        ),
        arrival_capacity_to_options=BinaryIncidence(
            indices.capacity_intervals.ids, option_ids, arrival_edges
        ),
    )
