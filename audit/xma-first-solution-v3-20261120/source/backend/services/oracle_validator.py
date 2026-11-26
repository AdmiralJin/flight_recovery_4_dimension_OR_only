from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any

from pydantic import ValidationError

from backend.schemas.columns import (
    CrewSegmentType,
    FlightOperationType,
    PassengerItineraryStatus,
    PassengerSegmentType,
    RecoveryColumns,
)
from backend.schemas.expected import (
    RecoveryActionType,
    RecoveryEntityType,
    RecoveryExpected,
    ResolvedFlightStatus,
)
from backend.schemas.scenario import Scenario

from .recovery_metrics import recompute_recovery_metrics
from .validation_common import ValidationIssue, issue, pydantic_issues


def _action_time(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _require_exact_map_keys(
    mapping: dict[str, str],
    expected_ids: set[str],
    location: str,
    missing_code: str,
    unknown_code: str,
) -> list[ValidationIssue]:
    issues = [
        issue(f"{location}.{item_id}", missing_code, f"{item_id!r} has no selection")
        for item_id in sorted(expected_ids - mapping.keys())
    ]
    issues.extend(
        issue(f"{location}.{item_id}", unknown_code, f"{item_id!r} does not exist")
        for item_id in sorted(mapping.keys() - expected_ids)
    )
    return issues


def validate_recovery_expected(
    scenario: Scenario,
    columns: RecoveryColumns,
    data: Any,
) -> tuple[RecoveryExpected | None, list[ValidationIssue]]:
    try:
        expected = RecoveryExpected.model_validate(data)
    except ValidationError as exc:
        return None, pydantic_issues(exc)

    issues: list[ValidationIssue] = []
    if expected.scenario_id != scenario.scenario_id or expected.scenario_id != columns.scenario_id:
        issues.append(issue("scenario_id", "scenario_id_mismatch", "expected, columns, and scenario IDs must match"))

    reference = expected.reference_solution
    flights = {item.flight_id: item for item in scenario.flights}
    aircraft = {item.tail_id: item for item in scenario.aircraft}
    crew = {item.crew_id: item for item in scenario.crew}
    passengers = {item.pax_group_id: item for item in scenario.passengers}
    options = {item.option_id: item for item in columns.flight_options}
    strings = {item.string_id: item for item in columns.aircraft_strings}
    pairings = {item.pairing_id: item for item in columns.crew_pairings}
    itineraries = {item.itinerary_id: item for item in columns.passenger_itineraries}

    selected_options = reference.selected_flight_option_by_flight
    issues.extend(_require_exact_map_keys(selected_options, set(flights), "reference_solution.selected_flight_option_by_flight", "missing_flight_selection", "unknown_flight"))
    for flight_id, option_id in selected_options.items():
        location = f"reference_solution.selected_flight_option_by_flight.{flight_id}"
        option = options.get(option_id)
        if option is None:
            issues.append(issue(location, "unknown_flight_option", f"flight option {option_id!r} does not exist"))
        elif option.base_flight_id != flight_id:
            issues.append(issue(location, "flight_option_base_mismatch", f"option belongs to {option.base_flight_id!r}"))

    selected_strings = reference.selected_aircraft_string_by_aircraft
    issues.extend(_require_exact_map_keys(selected_strings, set(aircraft), "reference_solution.selected_aircraft_string_by_aircraft", "missing_aircraft_selection", "unknown_aircraft"))
    for aircraft_id, string_id in selected_strings.items():
        location = f"reference_solution.selected_aircraft_string_by_aircraft.{aircraft_id}"
        string = strings.get(string_id)
        if string is None:
            issues.append(issue(location, "unknown_aircraft_string", f"aircraft string {string_id!r} does not exist"))
        elif string.aircraft_id != aircraft_id:
            issues.append(issue(location, "aircraft_string_owner_mismatch", f"string belongs to {string.aircraft_id!r}"))

    selected_pairings = reference.selected_crew_pairing_by_crew
    issues.extend(_require_exact_map_keys(selected_pairings, set(crew), "reference_solution.selected_crew_pairing_by_crew", "missing_crew_selection", "unknown_crew"))
    for crew_id, pairing_id in selected_pairings.items():
        location = f"reference_solution.selected_crew_pairing_by_crew.{crew_id}"
        pairing = pairings.get(pairing_id)
        if pairing is None:
            issues.append(issue(location, "unknown_crew_pairing", f"crew pairing {pairing_id!r} does not exist"))
        elif pairing.crew_id != crew_id:
            issues.append(issue(location, "crew_pairing_owner_mismatch", f"pairing belongs to {pairing.crew_id!r}"))

    selected_itineraries = reference.selected_passenger_itinerary_by_group
    issues.extend(_require_exact_map_keys(selected_itineraries, set(passengers), "reference_solution.selected_passenger_itinerary_by_group", "missing_passenger_selection", "unknown_passenger_group"))
    for group_id, itinerary_id in selected_itineraries.items():
        location = f"reference_solution.selected_passenger_itinerary_by_group.{group_id}"
        itinerary = itineraries.get(itinerary_id)
        if itinerary is None:
            issues.append(issue(location, "unknown_passenger_itinerary", f"passenger itinerary {itinerary_id!r} does not exist"))
        elif itinerary.pax_group_id != group_id:
            issues.append(issue(location, "passenger_itinerary_owner_mismatch", f"itinerary belongs to {itinerary.pax_group_id!r}"))
        elif itinerary.status is PassengerItineraryStatus.TRANSPORTED:
            for segment in itinerary.segments:
                if segment.segment_type is not PassengerSegmentType.FLIGHT:
                    continue
                option = options.get(segment.flight_option_id or "")
                if option is not None and option.base_flight_id is not None:
                    if selected_options.get(option.base_flight_id) != option.option_id:
                        issues.append(issue(location, "unselected_flight_option", f"itinerary uses unselected option {option.option_id!r}"))

    aircraft_coverage: Counter[str] = Counter()
    aircraft_owner: dict[str, str] = {}
    for aircraft_id, string_id in selected_strings.items():
        string = strings.get(string_id)
        if string is None or string.aircraft_id != aircraft_id:
            continue
        for option_id in string.leg_option_ids:
            aircraft_coverage[option_id] += 1
            aircraft_owner[option_id] = aircraft_id

    crew_coverage: Counter[str] = Counter()
    crew_owner: dict[str, str] = {}
    for crew_id, pairing_id in selected_pairings.items():
        pairing = pairings.get(pairing_id)
        if pairing is None or pairing.crew_id != crew_id:
            continue
        for duty in pairing.duties:
            for segment in duty.segments:
                if segment.segment_type is CrewSegmentType.OPERATE and segment.flight_option_id:
                    crew_coverage[segment.flight_option_id] += 1
                    crew_owner[segment.flight_option_id] = crew_id

    for flight_id, option_id in selected_options.items():
        option = options.get(option_id)
        if option is None:
            continue
        location = f"reference_solution.selected_flight_option_by_flight.{flight_id}"
        aircraft_count = aircraft_coverage[option_id]
        crew_count = crew_coverage[option_id]
        if option.operation_type is FlightOperationType.OPERATE:
            if aircraft_count == 0:
                issues.append(issue(location, "missing_aircraft_coverage", "selected operated option has no aircraft coverage"))
            elif aircraft_count > 1:
                issues.append(issue(location, "duplicate_aircraft_coverage", "selected operated option has duplicate aircraft coverage"))
            if crew_count == 0:
                issues.append(issue(location, "missing_crew_coverage", "selected operated option has no crew coverage"))
            elif crew_count > 1:
                issues.append(issue(location, "duplicate_crew_coverage", "selected operated option has duplicate crew coverage"))
        elif option.operation_type is FlightOperationType.CANCEL:
            if aircraft_count:
                issues.append(issue(location, "cancelled_flight_has_aircraft_coverage", "cancel option has aircraft coverage"))
            if crew_count:
                issues.append(issue(location, "cancelled_flight_has_crew_coverage", "cancel option has crew coverage"))

    resolved_by_flight: dict[str, Any] = {}
    for index, resolved in enumerate(reference.resolved_flights):
        location = f"reference_solution.resolved_flights[{index}]"
        if resolved.flight_id not in flights:
            issues.append(issue(f"{location}.flight_id", "unknown_flight", f"flight {resolved.flight_id!r} does not exist"))
            continue
        if resolved.flight_id in resolved_by_flight:
            issues.append(issue(f"{location}.flight_id", "duplicate_id", f"flight {resolved.flight_id!r} is resolved more than once"))
        resolved_by_flight[resolved.flight_id] = resolved
        selected_id = selected_options.get(resolved.flight_id)
        option = options.get(selected_id or "")
        if selected_id != resolved.selected_option_id:
            issues.append(issue(f"{location}.selected_option_id", "resolved_flight_mismatch", "resolved option differs from selected option"))
        if option is None:
            continue
        if option.operation_type is FlightOperationType.CANCEL:
            if resolved.status is not ResolvedFlightStatus.CANCELLED:
                issues.append(issue(f"{location}.status", "resolved_flight_mismatch", "cancel option must resolve as cancelled"))
        else:
            expected_values = {
                "status": ResolvedFlightStatus.OPERATED,
                "change_types": option.change_types,
                "recovered_origin": option.origin,
                "recovered_destination": option.destination,
                "recovered_dep": option.dep_time,
                "recovered_arr": option.arr_time,
                "departure_delay_minutes": option.departure_delay_minutes,
                "arrival_delay_minutes": option.arrival_delay_minutes,
                "aircraft_id": aircraft_owner.get(option.option_id),
                "crew_id": crew_owner.get(option.option_id),
            }
            for field, value in expected_values.items():
                if getattr(resolved, field) != value:
                    issues.append(issue(f"{location}.{field}", "resolved_flight_mismatch", f"expected {value!r}"))
    for flight_id in sorted(set(flights) - resolved_by_flight.keys()):
        issues.append(issue("reference_solution.resolved_flights", "missing_resolved_flight", f"flight {flight_id!r} is missing"))

    selected_operated = [
        options[option_id]
        for option_id in selected_options.values()
        if option_id in options and options[option_id].operation_type is FlightOperationType.OPERATE
    ]
    for index, interval in enumerate(scenario.airport_intervals):
        departures = sum(
            option.origin == interval.airport
            and interval.start_time <= option.dep_time < interval.end_time  # type: ignore[operator]
            for option in selected_operated
        )
        arrivals = sum(
            option.destination == interval.airport
            and interval.start_time <= option.arr_time < interval.end_time  # type: ignore[operator]
            for option in selected_operated
        )
        if departures > interval.dep_capacity:
            issues.append(issue(f"airport_intervals[{index}].dep_capacity", "departure_capacity_exceeded", f"{departures} departures exceed capacity {interval.dep_capacity}"))
        if arrivals > interval.arr_capacity:
            issues.append(issue(f"airport_intervals[{index}].arr_capacity", "arrival_capacity_exceeded", f"{arrivals} arrivals exceed capacity {interval.arr_capacity}"))
    # Gate occupancy has no approved recovered-event algorithm in Phase 1 and is intentionally not validated.

    outcomes: dict[str, Any] = {}
    for index, outcome in enumerate(reference.passenger_outcomes):
        location = f"reference_solution.passenger_outcomes[{index}]"
        passenger = passengers.get(outcome.pax_group_id)
        if passenger is None:
            issues.append(issue(f"{location}.pax_group_id", "unknown_passenger_group", f"passenger group {outcome.pax_group_id!r} does not exist"))
            continue
        if outcome.pax_group_id in outcomes:
            issues.append(issue(f"{location}.pax_group_id", "duplicate_id", "passenger outcome appears more than once"))
        outcomes[outcome.pax_group_id] = outcome
        itinerary_id = selected_itineraries.get(outcome.pax_group_id)
        itinerary = itineraries.get(itinerary_id or "")
        if itinerary is None:
            continue
        expected_unserved = passenger.count if itinerary.status is PassengerItineraryStatus.UNSERVED else 0
        expected_values = {
            "selected_itinerary_id": itinerary_id,
            "status": itinerary.status,
            "arrival_time": itinerary.arrival_time,
            "arrival_delay_minutes": itinerary.arrival_delay_minutes,
            "unserved_count": expected_unserved,
        }
        for field, value in expected_values.items():
            if getattr(outcome, field) != value:
                issues.append(issue(f"{location}.{field}", "passenger_outcome_mismatch", f"expected {value!r}"))
    for group_id in sorted(set(passengers) - outcomes.keys()):
        issues.append(issue("reference_solution.passenger_outcomes", "missing_passenger_outcome", f"passenger group {group_id!r} is missing"))

    entity_sets = {
        RecoveryEntityType.FLIGHT: set(flights),
        RecoveryEntityType.AIRCRAFT: set(aircraft),
        RecoveryEntityType.CREW: set(crew),
        RecoveryEntityType.PASSENGER_GROUP: set(passengers),
    }
    for index, action in enumerate(reference.recovery_actions):
        location = f"reference_solution.recovery_actions[{index}]"
        if action.entity_id not in entity_sets[action.entity_type]:
            issues.append(issue(f"{location}.entity_id", "unknown_recovery_entity", f"{action.entity_id!r} does not exist"))
            continue
        action_mismatch = False
        if action.action_type is RecoveryActionType.DELAY:
            original = flights.get(action.entity_id)
            resolved = resolved_by_flight.get(action.entity_id)
            action_mismatch = (
                action.entity_type is not RecoveryEntityType.FLIGHT
                or original is None
                or resolved is None
                or action.from_ is None
                or action.to is None
                or _action_time(action.from_.get("dep")) != original.sched_dep
                or _action_time(action.from_.get("arr")) != original.sched_arr
                or _action_time(action.to.get("dep")) != resolved.recovered_dep
                or _action_time(action.to.get("arr")) != resolved.recovered_arr
            )
        elif action.action_type is RecoveryActionType.AIRCRAFT_REASSIGNMENT:
            original = flights.get(action.entity_id)
            resolved = resolved_by_flight.get(action.entity_id)
            action_mismatch = (
                action.entity_type is not RecoveryEntityType.FLIGHT
                or original is None
                or resolved is None
                or action.from_ is None
                or action.to is None
                or action.from_.get("aircraft_id") != original.original_aircraft
                or action.to.get("aircraft_id") != resolved.aircraft_id
            )
        elif action.action_type is RecoveryActionType.CREW_REASSIGNMENT:
            original = flights.get(action.entity_id)
            resolved = resolved_by_flight.get(action.entity_id)
            action_mismatch = (
                action.entity_type is not RecoveryEntityType.FLIGHT
                or original is None
                or resolved is None
                or action.from_ is None
                or action.to is None
                or action.from_.get("crew_id") != original.original_crew
                or action.to.get("crew_id") != resolved.crew_id
            )
        elif action.action_type is RecoveryActionType.PASSENGER_REACCOMMODATION:
            passenger = passengers.get(action.entity_id)
            itinerary = itineraries.get(selected_itineraries.get(action.entity_id, ""))
            recovered_sequence = []
            if itinerary is not None:
                for segment in itinerary.segments:
                    option = options.get(segment.flight_option_id or "")
                    if segment.segment_type is PassengerSegmentType.FLIGHT and option is not None and option.base_flight_id:
                        recovered_sequence.append(option.base_flight_id)
            action_mismatch = (
                action.entity_type is not RecoveryEntityType.PASSENGER_GROUP
                or passenger is None
                or itinerary is None
                or action.from_ is None
                or action.to is None
                or action.from_.get("itinerary") != passenger.original_itinerary
                or action.to.get("itinerary") != recovered_sequence
            )
        if action_mismatch:
            issues.append(issue(location, "recovery_action_mismatch", "action from/to contradicts the resolved recovery"))

    observed = recompute_recovery_metrics(scenario, columns, expected)
    for location, declared in (
        ("reference_solution.metrics", reference.metrics),
        ("oracle_invariants.required_metrics", expected.oracle_invariants.required_metrics),
    ):
        for field in type(observed).model_fields:
            if getattr(declared, field) != getattr(observed, field):
                issues.append(issue(f"{location}.{field}", "metric_mismatch", f"declared {getattr(declared, field)}, computed {getattr(observed, field)}"))

    required_options = expected.oracle_invariants.required_flight_option_by_flight
    for flight_id, option_id in required_options.items():
        location = f"oracle_invariants.required_flight_option_by_flight.{flight_id}"
        if flight_id not in flights:
            issues.append(issue(location, "unknown_flight", f"flight {flight_id!r} does not exist"))
            continue
        option = options.get(option_id)
        if option is None:
            issues.append(issue(location, "unknown_flight_option", f"flight option {option_id!r} does not exist"))
        elif option.base_flight_id != flight_id:
            issues.append(issue(location, "flight_option_base_mismatch", f"option belongs to {option.base_flight_id!r}"))
        elif selected_options.get(flight_id) != option_id:
            issues.append(issue(location, "oracle_invariant_mismatch", "reference selection violates required option invariant"))
    cancelled_from_required = {
        flight_id
        for flight_id, option_id in required_options.items()
        if option_id in options and options[option_id].operation_type is FlightOperationType.CANCEL
    }
    if set(expected.oracle_invariants.expected_cancelled_flights) != cancelled_from_required:
        issues.append(issue("oracle_invariants.expected_cancelled_flights", "oracle_invariant_mismatch", "cancelled flight invariant disagrees with required options"))

    return expected, issues
