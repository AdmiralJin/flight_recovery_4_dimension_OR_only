import pytest

from backend.services.validator import validate_scenario


def locations_and_codes(issues):
    return {(issue.location, issue.code) for issue in issues}


def test_toy_case_passes_all_cross_entity_checks(toy_case):
    scenario, issues = validate_scenario(toy_case)
    assert scenario is not None
    assert issues == []


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        (lambda d: d["flights"][0].update(origin="UNKNOWN"), ("flights[0].origin", "unknown_airport")),
        (lambda d: d["flights"][0].update(original_aircraft="MISSING"), ("flights[0].original_aircraft", "unknown_aircraft")),
        (lambda d: d["flights"][0].update(original_crew="MISSING"), ("flights[0].original_crew", "unknown_crew")),
        (lambda d: d["flights"][1].update(original_equipment="E2"), ("flights[1].original_equipment", "equipment_mismatch")),
        (lambda d: d["aircraft"][0].update(original_rotation=["F2", "F3"]), ("flights[0].original_aircraft", "missing_from_rotation")),
        (lambda d: d["airports"].append(dict(d["airports"][0])), ("airports[3].airport_id", "duplicate_id")),
        (lambda d: d["airport_intervals"][0].update(airport="UNKNOWN"), ("airport_intervals[0].airport", "unknown_airport")),
    ],
)
def test_reference_failures_report_exact_locations(toy_case, mutation, expected):
    mutation(toy_case)
    _, issues = validate_scenario(toy_case)
    assert expected in locations_and_codes(issues)


def test_aircraft_rotation_checks_station_and_time_continuity(toy_case):
    toy_case["aircraft"][0]["original_rotation"] = ["F1", "F6", "F3"]
    _, issues = validate_scenario(toy_case)
    codes = locations_and_codes(issues)
    assert ("aircraft[0].original_rotation[1]", "station_discontinuity") in codes
    assert ("aircraft[0].original_rotation[1]", "aircraft_assignment_mismatch") in codes


def test_crew_duty_checks_flight_existence_and_rating(toy_case):
    toy_case["crew"][0]["rating"] = "E2"
    _, issues = validate_scenario(toy_case)
    assert ("crew[0].original_pairing[0]", "rating_mismatch") in locations_and_codes(issues)


def test_passenger_itinerary_checks_od_and_timestamps(toy_case):
    toy_case["passengers"][0]["destination"] = "B"
    toy_case["passengers"][0]["scheduled_arrival"] = "2026-01-15T11:00:00Z"
    _, issues = validate_scenario(toy_case)
    codes = locations_and_codes(issues)
    assert ("passengers[0].destination", "destination_mismatch") in codes
    assert ("passengers[0].scheduled_arrival", "arrival_mismatch") in codes


def test_flight_outside_recovery_window_is_rejected(toy_case):
    toy_case["recovery_window"]["end_time"] = "2026-01-15T12:00:00Z"
    _, issues = validate_scenario(toy_case)
    assert ("flights[2]", "outside_recovery_window") in locations_and_codes(issues)
