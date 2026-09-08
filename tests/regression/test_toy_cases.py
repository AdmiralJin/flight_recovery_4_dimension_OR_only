import json
from pathlib import Path

from backend.services.validator import validate_scenario


def test_toy_case_001_matches_phase0_expectation(toy_case):
    expected_path = Path(__file__).parents[2] / "data" / "expected" / "toy_case_001_expected.json"
    expected = json.loads(expected_path.read_text(encoding="utf-8"))["validation"]
    scenario, issues = validate_scenario(toy_case)

    assert scenario is not None
    observed = {
        "valid": not issues,
        "error_count": len(issues),
        "airport_count": len(scenario.airports),
        "flight_count": len(scenario.flights),
        "aircraft_count": len(scenario.aircraft),
        "crew_count": len(scenario.crew),
        "passenger_group_count": len(scenario.passengers),
    }
    assert observed == expected

