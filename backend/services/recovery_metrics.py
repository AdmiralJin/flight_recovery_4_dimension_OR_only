from __future__ import annotations

from backend.schemas.columns import (
    FlightOperationType,
    PassengerItineraryStatus,
    PassengerSegmentType,
    RecoveryColumns,
)
from backend.schemas.expected import RecoveryExpected, RecoveryMetrics, ResolvedFlightStatus
from backend.schemas.scenario import Scenario


def recompute_recovery_metrics(
    scenario: Scenario,
    columns: RecoveryColumns,
    expected: RecoveryExpected,
) -> RecoveryMetrics:
    reference = expected.reference_solution
    flights = {flight.flight_id: flight for flight in scenario.flights}
    passengers = {passenger.pax_group_id: passenger for passenger in scenario.passengers}
    options = {option.option_id: option for option in columns.flight_options}
    itineraries = {item.itinerary_id: item for item in columns.passenger_itineraries}

    operated = [item for item in reference.resolved_flights if item.status is ResolvedFlightStatus.OPERATED]
    cancelled = [item for item in reference.resolved_flights if item.status is ResolvedFlightStatus.CANCELLED]
    delayed = [
        item
        for item in operated
        if (item.departure_delay_minutes or 0) > 0 or (item.arrival_delay_minutes or 0) > 0
    ]
    origin_changed = [item for item in operated if item.flight_id in flights and item.recovered_origin != flights[item.flight_id].origin]
    destination_changed = [item for item in operated if item.flight_id in flights and item.recovered_destination != flights[item.flight_id].destination]
    aircraft_reassignments = sum(
        item.flight_id in flights and item.aircraft_id != flights[item.flight_id].original_aircraft
        for item in operated
    )
    crew_reassignments = sum(
        item.flight_id in flights and item.crew_id != flights[item.flight_id].original_crew
        for item in operated
    )

    reaccommodated_groups = 0
    reaccommodated_count = 0
    for group_id, itinerary_id in reference.selected_passenger_itinerary_by_group.items():
        passenger = passengers.get(group_id)
        itinerary = itineraries.get(itinerary_id)
        if passenger is None or itinerary is None or itinerary.status is PassengerItineraryStatus.UNSERVED:
            continue
        recovered_sequence: list[str] = []
        has_surface = False
        for segment in itinerary.segments:
            if segment.segment_type is PassengerSegmentType.SURFACE:
                has_surface = True
                continue
            option = options.get(segment.flight_option_id or "")
            if option is not None and option.operation_type is FlightOperationType.OPERATE and option.base_flight_id:
                recovered_sequence.append(option.base_flight_id)
        if has_surface or recovered_sequence != passenger.original_itinerary:
            reaccommodated_groups += 1
            reaccommodated_count += passenger.count

    outcomes = {outcome.pax_group_id: outcome for outcome in reference.passenger_outcomes}
    weighted_delay = sum(
        passengers[group_id].count * (outcome.arrival_delay_minutes or 0)
        for group_id, outcome in outcomes.items()
        if group_id in passengers and outcome.status is PassengerItineraryStatus.TRANSPORTED
    )
    unserved = sum(
        outcome.unserved_count
        for outcome in outcomes.values()
        if outcome.status is PassengerItineraryStatus.UNSERVED
    )

    return RecoveryMetrics(
        operated_flights=len(operated),
        cancelled_flights=len(cancelled),
        delayed_flights=len(delayed),
        origin_changed_flights=len(origin_changed),
        destination_changed_flights=len(destination_changed),
        aircraft_reassignments=aircraft_reassignments,
        crew_reassignments=crew_reassignments,
        passenger_reaccommodated_groups=reaccommodated_groups,
        passenger_reaccommodated_count=reaccommodated_count,
        total_flight_departure_delay_minutes=sum(item.departure_delay_minutes or 0 for item in operated),
        passenger_delay_minutes_weighted=weighted_delay,
        unserved_passengers=unserved,
    )
