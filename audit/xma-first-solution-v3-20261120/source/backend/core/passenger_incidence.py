from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from backend.schemas.columns import (
    FlightOperationType,
    PassengerItineraryStatus,
    PassengerSegmentType,
    RecoveryColumns,
)
from backend.schemas.scenario import Scenario

from .incidence import BinaryIncidence
from .indices import RecoveryIndices, build_recovery_indices


@dataclass(frozen=True)
class PassengerRecoveryIncidence:
    group_to_itineraries: BinaryIncidence[str, str]
    option_to_itineraries: BinaryIncidence[str, str]
    itinerary_to_flight_options: Mapping[str, tuple[str, ...]]
    transported_itineraries: tuple[str, ...]
    unserved_itineraries: tuple[str, ...]


def build_passenger_recovery_incidence(
    scenario: Scenario,
    columns: RecoveryColumns,
    indices: RecoveryIndices | None = None,
) -> PassengerRecoveryIncidence:
    expected = build_recovery_indices(scenario, columns)
    if indices is not None and indices != expected:
        raise ValueError("provided recovery indices do not match scenario and columns")
    indices = indices or expected

    options = {option.option_id: option for option in columns.flight_options}
    group_edges: list[tuple[str, str]] = []
    option_edges: list[tuple[str, str]] = []
    itinerary_to_options: dict[str, tuple[str, ...]] = {}
    transported: list[str] = []
    unserved: list[str] = []

    for itinerary in columns.passenger_itineraries:
        if itinerary.pax_group_id not in indices.passenger_groups:
            raise ValueError(
                f"passenger itinerary {itinerary.itinerary_id!r} references unknown "
                f"group {itinerary.pax_group_id!r}"
            )
        group_edges.append((itinerary.pax_group_id, itinerary.itinerary_id))

        flight_option_ids: list[str] = []
        for segment in itinerary.segments:
            if segment.segment_type is not PassengerSegmentType.FLIGHT:
                continue
            option_id = segment.flight_option_id or ""
            option = options.get(option_id)
            if option is None:
                raise ValueError(
                    f"passenger itinerary {itinerary.itinerary_id!r} references "
                    f"unknown option {option_id!r}"
                )
            if (
                option.operation_type is not FlightOperationType.OPERATE
                or option.base_flight_id is None
            ):
                raise ValueError(
                    f"passenger itinerary {itinerary.itinerary_id!r} cannot use "
                    f"{option.operation_type.value} option {option_id!r}"
                )
            if option_id in flight_option_ids:
                raise ValueError(
                    f"passenger itinerary {itinerary.itinerary_id!r} repeats "
                    f"flight option {option_id!r}"
                )
            flight_option_ids.append(option_id)
            option_edges.append((option_id, itinerary.itinerary_id))

        itinerary_to_options[itinerary.itinerary_id] = tuple(flight_option_ids)
        if itinerary.status is PassengerItineraryStatus.TRANSPORTED:
            transported.append(itinerary.itinerary_id)
        else:
            unserved.append(itinerary.itinerary_id)

    return PassengerRecoveryIncidence(
        group_to_itineraries=BinaryIncidence(
            indices.passenger_groups.ids,
            indices.passenger_itineraries.ids,
            group_edges,
        ),
        option_to_itineraries=BinaryIncidence(
            indices.revenue_operate_options.ids,
            indices.passenger_itineraries.ids,
            option_edges,
        ),
        itinerary_to_flight_options=MappingProxyType(itinerary_to_options),
        transported_itineraries=tuple(transported),
        unserved_itineraries=tuple(unserved),
    )
