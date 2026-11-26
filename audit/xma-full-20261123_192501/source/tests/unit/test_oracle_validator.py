import pytest

from backend.services.column_validator import validate_recovery_columns
from backend.services.oracle_validator import validate_recovery_expected
from backend.services.validator import validate_scenario


def _codes(issues):
    return {item.code for item in issues}


@pytest.fixture
def phase1_inputs(phase1_benchmark_001_data, phase1_columns_001_data):
    scenario, scenario_issues = validate_scenario(phase1_benchmark_001_data)
    assert scenario is not None and scenario_issues == []
    columns, column_issues = validate_recovery_columns(scenario, phase1_columns_001_data)
    assert columns is not None and column_issues == []
    return scenario, columns


def test_benchmark_expected_passes_semantic_validation(phase1_inputs, phase1_expected_001_data):
    expected, issues = validate_recovery_expected(*phase1_inputs, phase1_expected_001_data)
    assert expected is not None
    assert issues == []


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        (lambda d: d["reference_solution"]["selected_aircraft_string_by_aircraft"].update(AC1="AS_UNKNOWN"), "unknown_aircraft_string"),
        (lambda d: d["reference_solution"]["selected_aircraft_string_by_aircraft"].update(AC1="AS_AC1_ORIGINAL"), "missing_aircraft_coverage"),
        (lambda d: d["reference_solution"]["selected_aircraft_string_by_aircraft"].update(AC4="AS_AC4_RECOVERY"), "duplicate_aircraft_coverage"),
        (lambda d: d["reference_solution"]["selected_crew_pairing_by_crew"].update(C1="CP_C1_ORIGINAL"), "missing_crew_coverage"),
        (lambda d: d["reference_solution"]["selected_flight_option_by_flight"].update(F2="FO_F2_ORIG"), "departure_capacity_exceeded"),
        (lambda d: d["reference_solution"]["metrics"].update(total_flight_departure_delay_minutes=81), "metric_mismatch"),
        (lambda d: d.update(scenario_id="wrong_scenario"), "scenario_id_mismatch"),
        (lambda d: d["reference_solution"]["resolved_flights"][1].update(departure_delay_minutes=49), "resolved_flight_mismatch"),
        (lambda d: d["reference_solution"]["passenger_outcomes"][0].update(arrival_delay_minutes=49), "passenger_outcome_mismatch"),
        (lambda d: d["reference_solution"]["recovery_actions"][0]["to"].update(dep="2026-01-15T10:31:00Z"), "recovery_action_mismatch"),
    ],
)
def test_expected_negative_cases_report_specific_codes(
    phase1_inputs, phase1_expected_001_data, mutation, expected_code
):
    mutation(phase1_expected_001_data)
    _, issues = validate_recovery_expected(*phase1_inputs, phase1_expected_001_data)
    assert expected_code in _codes(issues)


def test_capacity_intervals_are_half_open(
    phase1_benchmark_001_data, phase1_columns_001_data, phase1_expected_001_data
):
    scenario, _ = validate_scenario(phase1_benchmark_001_data)
    assert scenario is not None
    columns, _ = validate_recovery_columns(scenario, phase1_columns_001_data)
    assert columns is not None
    _, issues = validate_recovery_expected(scenario, columns, phase1_expected_001_data)
    assert "departure_capacity_exceeded" not in _codes(issues)

    b_interval = next(item for item in scenario.airport_intervals if item.airport == "B")
    b_interval.end_time = b_interval.end_time.replace(minute=31)
    _, issues = validate_recovery_expected(scenario, columns, phase1_expected_001_data)
    assert "departure_capacity_exceeded" in _codes(issues)


def test_phase1_intentionally_does_not_validate_gate_occupancy(
    phase1_inputs, phase1_expected_001_data
):
    scenario, columns = phase1_inputs
    for interval in scenario.airport_intervals:
        interval.gate_capacity = 0
    _, issues = validate_recovery_expected(scenario, columns, phase1_expected_001_data)
    assert issues == []
