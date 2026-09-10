from backend.services.column_validator import validate_recovery_columns
from backend.services.oracle_validator import validate_recovery_expected
from backend.services.recovery_metrics import recompute_recovery_metrics
from backend.services.validator import validate_scenario


def test_metrics_are_recomputed_from_resolved_data(
    phase1_benchmark_001_data, phase1_columns_001_data, phase1_expected_001_data
):
    scenario, _ = validate_scenario(phase1_benchmark_001_data)
    assert scenario is not None
    columns, _ = validate_recovery_columns(scenario, phase1_columns_001_data)
    assert columns is not None
    expected, _ = validate_recovery_expected(scenario, columns, phase1_expected_001_data)
    assert expected is not None

    # The function must not echo either declared metrics object.
    expected.reference_solution.metrics.total_flight_departure_delay_minutes = 999
    expected.oracle_invariants.required_metrics.passenger_delay_minutes_weighted = 999
    metrics = recompute_recovery_metrics(scenario, columns, expected)

    assert metrics.total_flight_departure_delay_minutes == 80
    assert metrics.aircraft_reassignments == 2
    assert metrics.crew_reassignments == 0
    assert metrics.passenger_reaccommodated_count == 15
    assert metrics.passenger_delay_minutes_weighted == 1800
    assert metrics.unserved_passengers == 0
