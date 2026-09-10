import json
from pathlib import Path

from backend.services.validator import validate_scenario


PROJECT_ROOT = Path(__file__).parents[2]


def test_phase1_validation_001_matches_expected_facts():
    data = json.loads(
        (PROJECT_ROOT / "data" / "examples" / "phase1_validation_001.json").read_text(encoding="utf-8")
    )
    expected = json.loads(
        (PROJECT_ROOT / "data" / "expected" / "phase1_validation_001_expected.json").read_text(encoding="utf-8")
    )
    scenario, issues = validate_scenario(data)

    assert scenario is not None
    assert issues == []
    validation = expected["validation"]
    assert len(scenario.airports) == validation["airport_count"]
    assert len(scenario.flights) == validation["flight_count"]
    assert len(scenario.aircraft) == validation["aircraft_count"]
    assert len([item for item in scenario.aircraft if item.original_rotation]) == validation["operating_aircraft_count"]
    assert len([item for item in scenario.aircraft if not item.original_rotation]) == validation["reserve_aircraft_count"]
    assert len(scenario.crew) == validation["crew_count"]
    assert len([item for item in scenario.crew if item.original_pairing]) == validation["operating_crew_count"]
    assert len([item for item in scenario.crew if not item.original_pairing]) == validation["reserve_crew_count"]
    assert len(scenario.passengers) == validation["passenger_group_count"]
    assert len(scenario.airport_intervals) == validation["airport_interval_count"]
    assert len(scenario.disruptions) == validation["disruption_count"]

    check = expected["deterministic_checks"]["constrained_bucket"]
    bucket = next(
        interval
        for interval in scenario.airport_intervals
        if interval.airport == check["airport"]
        and interval.start_time.isoformat().replace("+00:00", "Z") == check["start_time"]
        and interval.end_time.isoformat().replace("+00:00", "Z") == check["end_time"]
    )
    departures = [
        flight.flight_id
        for flight in scenario.flights
        if flight.origin == check["airport"]
        and flight.sched_dep >= bucket.start_time
        and flight.sched_dep < bucket.end_time
    ]
    assert departures == check["scheduled_departures"]
    assert len(departures) - check["departure_capacity"] == check["minimum_departure_relief"]
