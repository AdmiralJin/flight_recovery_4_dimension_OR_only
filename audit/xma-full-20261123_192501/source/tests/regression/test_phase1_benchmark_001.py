from backend.services.column_validator import validate_recovery_columns
from backend.services.oracle_validator import validate_recovery_expected
from backend.services.recovery_metrics import recompute_recovery_metrics
from backend.services.validator import validate_scenario


def test_phase1_benchmark_full_validation_chain(
    phase1_benchmark_001_data, phase1_columns_001_data, phase1_expected_001_data
):
    scenario, scenario_issues = validate_scenario(phase1_benchmark_001_data)
    assert scenario is not None and scenario_issues == []
    columns, column_issues = validate_recovery_columns(scenario, phase1_columns_001_data)
    assert columns is not None and column_issues == []
    expected, oracle_issues = validate_recovery_expected(scenario, columns, phase1_expected_001_data)
    assert expected is not None and oracle_issues == []

    assert (len(scenario.airports), len(scenario.flights), len(scenario.aircraft), len(scenario.crew), len(scenario.passengers)) == (4, 12, 4, 5, 8)
    assert (len(columns.flight_options), len(columns.aircraft_strings), len(columns.crew_pairings), len(columns.passenger_itineraries)) == (22, 11, 10, 17)

    reference = expected.reference_solution
    assert reference.selected_flight_option_by_flight["F2"] == "FO_F2_D50"
    assert reference.selected_flight_option_by_flight["F3"] == "FO_F3_ORIG"
    assert reference.selected_flight_option_by_flight["F10"] == "FO_F10_D20"
    assert reference.selected_flight_option_by_flight["F11"] == "FO_F11_D10"
    assert reference.selected_aircraft_string_by_aircraft["AC1"] == "AS_AC1_SWAP_F10"
    assert reference.selected_aircraft_string_by_aircraft["AC4"] == "AS_AC4_SWAP_F3_ORIG"
    assert reference.selected_passenger_itinerary_by_group["P4"] == "PI_P4_REACCOM_F8"

    options = {item.option_id: item for item in columns.flight_options}
    strings = {item.string_id: item for item in columns.aircraft_strings}
    assert [options[item].base_flight_id for item in strings["AS_AC1_SWAP_F10"].leg_option_ids] == ["F1", "F2", "F10"]
    assert [options[item].base_flight_id for item in strings["AS_AC4_SWAP_F3_ORIG"].leg_option_ids] == ["F3", "F11", "F12"]

    metrics = recompute_recovery_metrics(scenario, columns, expected)
    assert metrics.model_dump() == {
        "operated_flights": 12,
        "cancelled_flights": 0,
        "delayed_flights": 3,
        "origin_changed_flights": 0,
        "destination_changed_flights": 0,
        "aircraft_reassignments": 2,
        "crew_reassignments": 0,
        "passenger_reaccommodated_groups": 1,
        "passenger_reaccommodated_count": 15,
        "total_flight_departure_delay_minutes": 80,
        "passenger_delay_minutes_weighted": 1800,
        "unserved_passengers": 0,
    }
