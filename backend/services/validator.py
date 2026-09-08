from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass
from typing import Any

from pydantic import ValidationError

from backend.schemas import Scenario


@dataclass(frozen=True)
class ValidationIssue:
    location: str
    code: str
    message: str


def _format_location(parts: Iterable[Any]) -> str:
    result = ""
    for part in parts:
        if isinstance(part, int):
            result += f"[{part}]"
        else:
            result += ("." if result else "") + str(part)
    return result or "$"


def _issue(location: str, code: str, message: str) -> ValidationIssue:
    return ValidationIssue(location=location, code=code, message=message)


def _duplicates(items: list[Any], attr: str, collection: str) -> list[ValidationIssue]:
    first_index: dict[str, int] = {}
    issues: list[ValidationIssue] = []
    for index, item in enumerate(items):
        value = getattr(item, attr)
        if value in first_index:
            issues.append(
                _issue(
                    f"{collection}[{index}].{attr}",
                    "duplicate_id",
                    f"{value!r} duplicates {collection}[{first_index[value]}].{attr}",
                )
            )
        else:
            first_index[value] = index
    return issues


def _sequence_issues(
    flight_ids: list[str],
    flights_by_id: dict[str, Any],
    location: str,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    resolved: list[tuple[int, Any]] = []
    for index, flight_id in enumerate(flight_ids):
        flight = flights_by_id.get(flight_id)
        if flight is None:
            issues.append(
                _issue(f"{location}[{index}]", "unknown_flight", f"flight {flight_id!r} does not exist")
            )
        else:
            resolved.append((index, flight))
    for (left_index, left), (right_index, right) in zip(resolved, resolved[1:]):
        if right_index != left_index + 1:
            continue
        if left.destination != right.origin:
            issues.append(
                _issue(
                    f"{location}[{right_index}]",
                    "station_discontinuity",
                    f"{left.flight_id} arrives at {left.destination}, but {right.flight_id} departs {right.origin}",
                )
            )
        if left.sched_arr > right.sched_dep:
            issues.append(
                _issue(
                    f"{location}[{right_index}]",
                    "time_overlap",
                    f"{right.flight_id} departs before {left.flight_id} arrives",
                )
            )
    return issues


def validate_scenario(data: Any) -> tuple[Scenario | None, list[ValidationIssue]]:
    try:
        scenario = Scenario.model_validate(data)
    except ValidationError as exc:
        issues = [
            _issue(_format_location(error["loc"]), error["type"], error["msg"])
            for error in exc.errors(include_url=False, include_input=False)
        ]
        return None, issues

    issues: list[ValidationIssue] = []
    issues.extend(_duplicates(scenario.airports, "airport_id", "airports"))
    issues.extend(_duplicates(scenario.flights, "flight_id", "flights"))
    issues.extend(_duplicates(scenario.aircraft, "tail_id", "aircraft"))
    issues.extend(_duplicates(scenario.crew, "crew_id", "crew"))
    issues.extend(_duplicates(scenario.passengers, "pax_group_id", "passengers"))

    airports = {airport.airport_id for airport in scenario.airports}
    aircraft_by_id = {aircraft.tail_id: aircraft for aircraft in scenario.aircraft}
    crew_by_id = {crew.crew_id: crew for crew in scenario.crew}
    flights_by_id = {flight.flight_id: flight for flight in scenario.flights}
    start = scenario.recovery_window.start_time
    end = scenario.recovery_window.end_time

    for index, flight in enumerate(scenario.flights):
        prefix = f"flights[{index}]"
        for field in ("origin", "destination"):
            value = getattr(flight, field)
            if value not in airports:
                issues.append(_issue(f"{prefix}.{field}", "unknown_airport", f"airport {value!r} does not exist"))
        aircraft = aircraft_by_id.get(flight.original_aircraft)
        if aircraft is None:
            issues.append(_issue(f"{prefix}.original_aircraft", "unknown_aircraft", "aircraft does not exist"))
        elif aircraft.equipment_type != flight.original_equipment:
            issues.append(_issue(f"{prefix}.original_equipment", "equipment_mismatch", "flight equipment differs from original aircraft"))
        elif flight.flight_id not in aircraft.original_rotation:
            issues.append(_issue(f"{prefix}.original_aircraft", "missing_from_rotation", "flight is absent from the original aircraft rotation"))
        assigned_crew = crew_by_id.get(flight.original_crew)
        if assigned_crew is None:
            issues.append(_issue(f"{prefix}.original_crew", "unknown_crew", "crew does not exist"))
        elif assigned_crew.rating != flight.original_equipment:
            issues.append(_issue(f"{prefix}.original_crew", "rating_mismatch", "crew rating is incompatible with flight equipment"))
        elif flight.flight_id not in assigned_crew.original_pairing:
            issues.append(_issue(f"{prefix}.original_crew", "missing_from_pairing", "flight is absent from the original crew pairing"))
        if flight.sched_dep < start or flight.sched_arr > end:
            issues.append(_issue(prefix, "outside_recovery_window", "scheduled flight must be fully inside the recovery window"))

    for index, aircraft in enumerate(scenario.aircraft):
        prefix = f"aircraft[{index}]"
        for field in ("initial_station_at_t", "required_station_at_T_end"):
            station = getattr(aircraft, field)
            if station not in airports:
                issues.append(_issue(f"{prefix}.{field}", "unknown_airport", f"airport {station!r} does not exist"))
        for station_index, station in enumerate(aircraft.maintenance_stations):
            if station not in airports:
                issues.append(_issue(f"{prefix}.maintenance_stations[{station_index}]", "unknown_airport", f"airport {station!r} does not exist"))
        issues.extend(_sequence_issues(aircraft.original_rotation, flights_by_id, f"{prefix}.original_rotation"))
        rotation = [flights_by_id[flight_id] for flight_id in aircraft.original_rotation if flight_id in flights_by_id]
        for flight_index, flight in enumerate(rotation):
            if flight.original_aircraft != aircraft.tail_id:
                issues.append(_issue(f"{prefix}.original_rotation[{flight_index}]", "aircraft_assignment_mismatch", f"{flight.flight_id} names aircraft {flight.original_aircraft!r}"))
            if flight.original_equipment != aircraft.equipment_type:
                issues.append(_issue(f"{prefix}.original_rotation[{flight_index}]", "equipment_mismatch", f"{flight.flight_id} uses equipment {flight.original_equipment!r}"))
        if rotation and rotation[0].origin != aircraft.initial_station_at_t:
            issues.append(_issue(f"{prefix}.initial_station_at_t", "initial_station_mismatch", "initial station differs from first flight origin"))
        if rotation and rotation[-1].destination != aircraft.required_station_at_T_end:
            issues.append(_issue(f"{prefix}.required_station_at_T_end", "end_station_mismatch", "required station differs from last flight destination"))

    for index, crew in enumerate(scenario.crew):
        prefix = f"crew[{index}]"
        for field in ("start_station_at_t", "required_station_at_T_end"):
            station = getattr(crew, field)
            if station not in airports:
                issues.append(_issue(f"{prefix}.{field}", "unknown_airport", f"airport {station!r} does not exist"))
        for duty_index, duty in enumerate(crew.original_duties):
            issues.extend(_sequence_issues(duty, flights_by_id, f"{prefix}.original_duties[{duty_index}]"))
        pairing = [flights_by_id[flight_id] for flight_id in crew.original_pairing if flight_id in flights_by_id]
        for flight_index, flight in enumerate(pairing):
            if flight.original_crew != crew.crew_id:
                issues.append(_issue(f"{prefix}.original_pairing[{flight_index}]", "crew_assignment_mismatch", f"{flight.flight_id} names crew {flight.original_crew!r}"))
            if flight.original_equipment != crew.rating:
                issues.append(_issue(f"{prefix}.original_pairing[{flight_index}]", "rating_mismatch", f"crew is not rated for {flight.original_equipment!r}"))
        if pairing and pairing[0].origin != crew.start_station_at_t:
            issues.append(_issue(f"{prefix}.start_station_at_t", "initial_station_mismatch", "crew start station differs from first flight origin"))
        if pairing and pairing[-1].destination != crew.required_station_at_T_end:
            issues.append(_issue(f"{prefix}.required_station_at_T_end", "end_station_mismatch", "crew end station differs from last flight destination"))

    for index, passenger in enumerate(scenario.passengers):
        prefix = f"passengers[{index}]"
        for field in ("origin", "destination"):
            station = getattr(passenger, field)
            if station not in airports:
                issues.append(_issue(f"{prefix}.{field}", "unknown_airport", f"airport {station!r} does not exist"))
        issues.extend(_sequence_issues(passenger.original_itinerary, flights_by_id, f"{prefix}.original_itinerary"))
        itinerary = [flights_by_id[flight_id] for flight_id in passenger.original_itinerary if flight_id in flights_by_id]
        if itinerary:
            if itinerary[0].origin != passenger.origin:
                issues.append(_issue(f"{prefix}.origin", "origin_mismatch", "passenger origin differs from itinerary origin"))
            if itinerary[-1].destination != passenger.destination:
                issues.append(_issue(f"{prefix}.destination", "destination_mismatch", "passenger destination differs from itinerary destination"))
            if itinerary[0].sched_dep != passenger.original_departure:
                issues.append(_issue(f"{prefix}.original_departure", "departure_mismatch", "original_departure differs from first itinerary flight"))
            if itinerary[-1].sched_arr != passenger.scheduled_arrival:
                issues.append(_issue(f"{prefix}.scheduled_arrival", "arrival_mismatch", "scheduled_arrival differs from final itinerary flight"))

    for collection_name in ("airport_intervals", "disruptions"):
        for index, interval in enumerate(getattr(scenario, collection_name)):
            prefix = f"{collection_name}[{index}]"
            if interval.airport not in airports:
                issues.append(_issue(f"{prefix}.airport", "unknown_airport", f"airport {interval.airport!r} does not exist"))
            if interval.start_time < start or interval.end_time > end:
                issues.append(_issue(prefix, "outside_recovery_window", "interval must be fully inside the recovery window"))

    return scenario, issues


def validation_payload(data: Any) -> tuple[dict[str, Any], int]:
    scenario, issues = validate_scenario(data)
    serialized = [asdict(issue) for issue in issues]
    if issues:
        return {"valid": False, "errors": serialized, "warnings": []}, 422
    assert scenario is not None
    return {
        "valid": True,
        "errors": [],
        "warnings": [],
        "normalized_data": scenario.model_dump(mode="json"),
    }, 200
