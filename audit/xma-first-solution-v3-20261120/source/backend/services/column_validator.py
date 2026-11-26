from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from pydantic import ValidationError

from backend.schemas.columns import (
    CrewSegment,
    CrewSegmentType,
    FlightChangeType,
    FlightOperationType,
    FlightOption,
    PassengerItineraryStatus,
    PassengerSegment,
    PassengerSegmentType,
    RecoveryColumns,
)
from backend.schemas.common import minutes_between
from backend.schemas.scenario import Scenario

from .validation_common import ValidationIssue, issue, pydantic_issues


def _duplicate_issues(items: Iterable[Any], attr: str, location: str) -> list[ValidationIssue]:
    first: dict[str, int] = {}
    result: list[ValidationIssue] = []
    for index, item in enumerate(items):
        value = getattr(item, attr)
        if value in first:
            result.append(
                issue(
                    f"{location}[{index}].{attr}",
                    "duplicate_id",
                    f"{value!r} duplicates {location}[{first[value]}].{attr}",
                )
            )
        else:
            first[value] = index
    return result


def _resolved_crew_segment(
    segment: CrewSegment,
    options: dict[str, FlightOption],
) -> tuple[str, str, Any, Any] | None:
    if segment.segment_type in {CrewSegmentType.OPERATE, CrewSegmentType.DEADHEAD}:
        option = options.get(segment.flight_option_id or "")
        if option is None or option.operation_type is FlightOperationType.CANCEL:
            return None
        assert option.origin is not None and option.destination is not None
        assert option.dep_time is not None and option.arr_time is not None
        return option.origin, option.destination, option.dep_time, option.arr_time
    assert segment.origin is not None and segment.destination is not None
    assert segment.start_time is not None and segment.end_time is not None
    return segment.origin, segment.destination, segment.start_time, segment.end_time


def _resolved_passenger_segment(
    segment: PassengerSegment,
    options: dict[str, FlightOption],
) -> tuple[str, str, Any, Any] | None:
    if segment.segment_type is PassengerSegmentType.FLIGHT:
        option = options.get(segment.flight_option_id or "")
        if option is None or option.operation_type is not FlightOperationType.OPERATE:
            return None
        assert option.origin is not None and option.destination is not None
        assert option.dep_time is not None and option.arr_time is not None
        return option.origin, option.destination, option.dep_time, option.arr_time
    assert segment.origin is not None and segment.destination is not None
    assert segment.dep_time is not None and segment.arr_time is not None
    return segment.origin, segment.destination, segment.dep_time, segment.arr_time


def validate_recovery_columns(
    scenario: Scenario,
    data: Any,
) -> tuple[RecoveryColumns | None, list[ValidationIssue]]:
    try:
        columns = RecoveryColumns.model_validate(data)
    except ValidationError as exc:
        return None, pydantic_issues(exc)

    issues: list[ValidationIssue] = []
    if columns.scenario_id != scenario.scenario_id:
        issues.append(issue("scenario_id", "scenario_id_mismatch", "columns scenario_id differs from scenario"))

    issues.extend(_duplicate_issues(columns.flight_options, "option_id", "flight_options"))
    issues.extend(_duplicate_issues(columns.aircraft_strings, "string_id", "aircraft_strings"))
    issues.extend(_duplicate_issues(columns.crew_pairings, "pairing_id", "crew_pairings"))
    issues.extend(_duplicate_issues(columns.passenger_itineraries, "itinerary_id", "passenger_itineraries"))
    first_duty: dict[str, str] = {}
    for pairing_index, pairing in enumerate(columns.crew_pairings):
        for duty_index, duty in enumerate(pairing.duties):
            location = f"crew_pairings[{pairing_index}].duties[{duty_index}].duty_id"
            if duty.duty_id in first_duty:
                issues.append(issue(location, "duplicate_id", f"{duty.duty_id!r} duplicates {first_duty[duty.duty_id]}"))
            else:
                first_duty[duty.duty_id] = location

    airports = {airport.airport_id for airport in scenario.airports}
    flights = {flight.flight_id: flight for flight in scenario.flights}
    aircraft = {item.tail_id: item for item in scenario.aircraft}
    crew = {item.crew_id: item for item in scenario.crew}
    passengers = {item.pax_group_id: item for item in scenario.passengers}
    options = {option.option_id: option for option in columns.flight_options}

    for index, option in enumerate(columns.flight_options):
        prefix = f"flight_options[{index}]"
        if option.operation_type is FlightOperationType.CANCEL:
            if option.base_flight_id not in flights:
                issues.append(issue(f"{prefix}.base_flight_id", "unknown_flight", f"flight {option.base_flight_id!r} does not exist"))
            continue

        assert option.origin is not None and option.destination is not None
        assert option.dep_time is not None and option.arr_time is not None
        assert option.block_minutes is not None
        for field in ("origin", "destination"):
            value = getattr(option, field)
            if value not in airports:
                issues.append(issue(f"{prefix}.{field}", "unknown_airport", f"airport {value!r} does not exist"))
        if option.dep_time < scenario.recovery_window.start_time or option.arr_time > scenario.recovery_window.end_time:
            issues.append(issue(prefix, "outside_recovery_window", "option must be fully inside the recovery window"))
        try:
            actual_block = minutes_between(option.dep_time, option.arr_time)
        except ValueError as exc:
            issues.append(issue(f"{prefix}.block_minutes", "block_time_mismatch", str(exc)))
        else:
            if actual_block != option.block_minutes:
                issues.append(issue(f"{prefix}.block_minutes", "block_time_mismatch", f"declared {option.block_minutes}, computed {actual_block}"))

        if option.operation_type is FlightOperationType.FERRY:
            continue
        original = flights.get(option.base_flight_id or "")
        if original is None:
            issues.append(issue(f"{prefix}.base_flight_id", "unknown_flight", f"flight {option.base_flight_id!r} does not exist"))
            continue
        if option.dep_time < original.sched_dep:
            issues.append(issue(f"{prefix}.dep_time", "negative_departure_delay", "departure precedes original schedule"))
        if option.arr_time < original.sched_arr:
            issues.append(issue(f"{prefix}.arr_time", "negative_arrival_delay", "arrival precedes original schedule"))
        try:
            dep_delay = minutes_between(original.sched_dep, option.dep_time)
            arr_delay = minutes_between(original.sched_arr, option.arr_time)
        except ValueError as exc:
            issues.append(issue(prefix, "delay_mismatch", str(exc)))
            continue
        if dep_delay != option.departure_delay_minutes:
            issues.append(issue(f"{prefix}.departure_delay_minutes", "departure_delay_mismatch", f"declared {option.departure_delay_minutes}, computed {dep_delay}"))
        if arr_delay != option.arrival_delay_minutes:
            issues.append(issue(f"{prefix}.arrival_delay_minutes", "arrival_delay_mismatch", f"declared {option.arrival_delay_minutes}, computed {arr_delay}"))
        if dep_delay > original.max_delay:
            issues.append(issue(f"{prefix}.departure_delay_minutes", "max_delay_exceeded", f"delay {dep_delay} exceeds maximum {original.max_delay}"))

        expected_changes: set[FlightChangeType] = set()
        if option.origin != original.origin:
            expected_changes.add(FlightChangeType.ORIGIN_CHANGE)
        if option.destination != original.destination:
            expected_changes.add(FlightChangeType.DESTINATION_CHANGE)
        if dep_delay > 0 or arr_delay > 0:
            expected_changes.add(FlightChangeType.DELAY)
        if option.block_minutes != original.duration:
            expected_changes.add(FlightChangeType.BLOCK_TIME_CHANGE)
        if not expected_changes:
            expected_changes.add(FlightChangeType.UNCHANGED)
        if set(option.change_types) != expected_changes:
            issues.append(issue(f"{prefix}.change_types", "change_type_mismatch", f"expected {sorted(item.value for item in expected_changes)!r}"))

    for index, string in enumerate(columns.aircraft_strings):
        prefix = f"aircraft_strings[{index}]"
        resource = aircraft.get(string.aircraft_id)
        if resource is None:
            issues.append(issue(f"{prefix}.aircraft_id", "unknown_aircraft", f"aircraft {string.aircraft_id!r} does not exist"))
        resolved: list[tuple[int, FlightOption]] = []
        for leg_index, option_id in enumerate(string.leg_option_ids):
            option = options.get(option_id)
            location = f"{prefix}.leg_option_ids[{leg_index}]"
            if option is None:
                issues.append(issue(location, "unknown_flight_option", f"flight option {option_id!r} does not exist"))
            elif option.operation_type is FlightOperationType.CANCEL:
                issues.append(issue(location, "cancel_option_in_aircraft_string", "cancel option is not an operated leg"))
            else:
                resolved.append((leg_index, option))
        if resource is None:
            continue
        if string.start_station != resource.initial_station_at_t:
            issues.append(issue(f"{prefix}.start_station", "initial_station_mismatch", "string start differs from aircraft initial station"))
        if string.end_station != resource.required_station_at_T_end:
            issues.append(issue(f"{prefix}.end_station", "end_station_mismatch", "string end differs from aircraft required station"))
        if resolved:
            first = resolved[0][1]
            last = resolved[-1][1]
            if first.origin != string.start_station:
                issues.append(issue(f"{prefix}.leg_option_ids[{resolved[0][0]}]", "initial_station_mismatch", "first leg origin differs from string start"))
            if last.destination != string.end_station:
                issues.append(issue(f"{prefix}.leg_option_ids[{resolved[-1][0]}]", "end_station_mismatch", "last leg destination differs from string end"))
        for (left_index, left), (right_index, right) in zip(resolved, resolved[1:]):
            if right_index != left_index + 1:
                continue
            if left.destination != right.origin:
                issues.append(issue(f"{prefix}.leg_option_ids[{right_index}]", "station_discontinuity", "consecutive aircraft legs are not station-continuous"))
            if left.arr_time is not None and right.dep_time is not None and left.arr_time > right.dep_time:
                issues.append(issue(f"{prefix}.leg_option_ids[{right_index}]", "time_overlap", "consecutive aircraft legs overlap"))
        for leg_index, option in resolved:
            if option.base_flight_id:
                base = flights.get(option.base_flight_id)
                if base is not None and base.original_equipment != resource.equipment_type:
                    issues.append(issue(f"{prefix}.leg_option_ids[{leg_index}]", "equipment_mismatch", "aircraft equipment is incompatible with flight"))
        if resource.maintenance_required:
            if not string.maintenance_satisfied:
                issues.append(issue(f"{prefix}.maintenance_satisfied", "maintenance_not_satisfied", "maintenance-required aircraft string is not satisfied"))
            if string.end_station not in resource.maintenance_stations:
                issues.append(issue(f"{prefix}.end_station", "maintenance_station_mismatch", "string does not end at a maintenance station"))

    for index, pairing in enumerate(columns.crew_pairings):
        prefix = f"crew_pairings[{index}]"
        resource = crew.get(pairing.crew_id)
        if resource is None:
            issues.append(issue(f"{prefix}.crew_id", "unknown_crew", f"crew {pairing.crew_id!r} does not exist"))
        indexed_segments = [
            (duty_index, segment_index, segment)
            for duty_index, duty in enumerate(pairing.duties)
            for segment_index, segment in enumerate(duty.segments)
        ]
        resolved_segments: list[tuple[int, int, tuple[str, str, Any, Any]]] = []
        for duty_index, segment_index, segment in indexed_segments:
            location = f"{prefix}.duties[{duty_index}].segments[{segment_index}]"
            if segment.segment_type in {CrewSegmentType.OPERATE, CrewSegmentType.DEADHEAD}:
                option = options.get(segment.flight_option_id or "")
                if option is None:
                    issues.append(issue(f"{location}.flight_option_id", "unknown_flight_option", f"flight option {segment.flight_option_id!r} does not exist"))
                    continue
                if option.operation_type is FlightOperationType.CANCEL:
                    issues.append(issue(f"{location}.flight_option_id", "cancel_option_in_crew_pairing", "crew segment cannot use a cancel option"))
                    continue
                if resource is not None and segment.segment_type is CrewSegmentType.OPERATE and option.base_flight_id:
                    base = flights.get(option.base_flight_id)
                    if base is not None and base.original_equipment != resource.rating:
                        issues.append(issue(f"{location}.flight_option_id", "rating_mismatch", "crew rating is incompatible with flight"))
            else:
                for field in ("origin", "destination"):
                    value = getattr(segment, field)
                    if value not in airports:
                        issues.append(issue(f"{location}.{field}", "unknown_airport", f"airport {value!r} does not exist"))
            resolved = _resolved_crew_segment(segment, options)
            if resolved is not None:
                resolved_segments.append((duty_index, segment_index, resolved))
        if resource is None:
            continue
        if pairing.start_station != resource.start_station_at_t:
            issues.append(issue(f"{prefix}.start_station", "initial_station_mismatch", "pairing start differs from crew start"))
        if pairing.end_station != resource.required_station_at_T_end:
            issues.append(issue(f"{prefix}.end_station", "end_station_mismatch", "pairing end differs from crew required station"))
        if resolved_segments:
            if resolved_segments[0][2][0] != pairing.start_station:
                issues.append(issue(f"{prefix}.start_station", "initial_station_mismatch", "first segment origin differs from pairing start"))
            if resolved_segments[-1][2][1] != pairing.end_station:
                issues.append(issue(f"{prefix}.end_station", "end_station_mismatch", "last segment destination differs from pairing end"))
        for left, right in zip(resolved_segments, resolved_segments[1:]):
            location = f"{prefix}.duties[{right[0]}].segments[{right[1]}]"
            if left[2][1] != right[2][0]:
                issues.append(issue(location, "station_discontinuity", "consecutive crew segments are not station-continuous"))
            if left[2][3] > right[2][2]:
                issues.append(issue(location, "time_overlap", "consecutive crew segments overlap"))

    for index, itinerary in enumerate(columns.passenger_itineraries):
        prefix = f"passenger_itineraries[{index}]"
        passenger = passengers.get(itinerary.pax_group_id)
        if passenger is None:
            issues.append(issue(f"{prefix}.pax_group_id", "unknown_passenger_group", f"passenger group {itinerary.pax_group_id!r} does not exist"))
        if itinerary.status is PassengerItineraryStatus.UNSERVED or passenger is None:
            continue
        resolved_segments: list[tuple[int, tuple[str, str, Any, Any]]] = []
        for segment_index, segment in enumerate(itinerary.segments):
            location = f"{prefix}.segments[{segment_index}]"
            if segment.segment_type is PassengerSegmentType.FLIGHT:
                option = options.get(segment.flight_option_id or "")
                if option is None:
                    issues.append(issue(f"{location}.flight_option_id", "unknown_flight_option", f"flight option {segment.flight_option_id!r} does not exist"))
                    continue
                if option.operation_type is not FlightOperationType.OPERATE:
                    issues.append(issue(f"{location}.flight_option_id", "invalid_passenger_flight_option", "passenger flight segment must use an operated revenue option"))
                    continue
            else:
                for field in ("origin", "destination"):
                    value = getattr(segment, field)
                    if value not in airports:
                        issues.append(issue(f"{location}.{field}", "unknown_airport", f"airport {value!r} does not exist"))
            resolved = _resolved_passenger_segment(segment, options)
            if resolved is not None:
                resolved_segments.append((segment_index, resolved))
        if not resolved_segments:
            continue
        first, last = resolved_segments[0], resolved_segments[-1]
        if first[1][0] != passenger.origin:
            issues.append(issue(f"{prefix}.segments[{first[0]}]", "origin_mismatch", "itinerary origin differs from passenger origin"))
        for left, right in zip(resolved_segments, resolved_segments[1:]):
            location = f"{prefix}.segments[{right[0]}]"
            if left[1][1] != right[1][0]:
                issues.append(issue(location, "station_discontinuity", "consecutive passenger segments are not station-continuous"))
            if left[1][3] > right[1][2]:
                issues.append(issue(location, "time_overlap", "consecutive passenger segments overlap"))
        if last[1][1] != passenger.destination or itinerary.final_destination != passenger.destination:
            issues.append(issue(f"{prefix}.final_destination", "destination_mismatch", "itinerary does not end at passenger destination"))
        if itinerary.arrival_time != last[1][3]:
            issues.append(issue(f"{prefix}.arrival_time", "arrival_mismatch", "itinerary arrival differs from last segment"))
        try:
            delay = minutes_between(passenger.scheduled_arrival, itinerary.arrival_time)  # type: ignore[arg-type]
        except ValueError as exc:
            issues.append(issue(f"{prefix}.arrival_delay_minutes", "arrival_delay_mismatch", str(exc)))
        else:
            # Passenger delay is a non-negative lateness metric; an earlier arrival contributes zero.
            delay = max(0, delay)
            if delay != itinerary.arrival_delay_minutes:
                issues.append(issue(f"{prefix}.arrival_delay_minutes", "arrival_delay_mismatch", f"declared {itinerary.arrival_delay_minutes}, computed {delay}"))

    # Phase 1 intentionally validates passenger OD/time only; remaining-seat inventory is not defined yet.
    return columns, issues
