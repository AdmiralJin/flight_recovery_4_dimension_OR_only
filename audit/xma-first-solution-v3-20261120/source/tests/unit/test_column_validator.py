from copy import deepcopy

import pytest

from backend.services.column_validator import validate_recovery_columns
from backend.services.validator import validate_scenario


def _by_id(items, field, value):
    return next(item for item in items if item[field] == value)


def _codes(issues):
    return {item.code for item in issues}


@pytest.fixture
def scenario(phase1_benchmark_001_data):
    result, issues = validate_scenario(phase1_benchmark_001_data)
    assert result is not None and issues == []
    return result


def test_benchmark_columns_pass_semantic_validation(scenario, phase1_columns_001_data):
    columns, issues = validate_recovery_columns(scenario, phase1_columns_001_data)
    assert columns is not None
    assert issues == []


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        (lambda d: d["flight_options"].append(deepcopy(d["flight_options"][0])), "duplicate_id"),
        (lambda d: _by_id(d["flight_options"], "option_id", "FO_F1_ORIG").update(base_flight_id="FX"), "unknown_flight"),
        (lambda d: _by_id(d["aircraft_strings"], "string_id", "AS_AC1_ORIGINAL")["leg_option_ids"].__setitem__(1, "FO_F3_CANCEL"), "cancel_option_in_aircraft_string"),
        (lambda d: _by_id(d["aircraft_strings"], "string_id", "AS_AC1_ORIGINAL")["leg_option_ids"].__setitem__(1, "FO_F5_ORIG"), "station_discontinuity"),
        (lambda d: _by_id(d["aircraft_strings"], "string_id", "AS_AC1_ORIGINAL")["leg_option_ids"].__setitem__(1, "FO_F2_D50"), "time_overlap"),
        (lambda d: _by_id(d["aircraft_strings"], "string_id", "AS_AC1_ORIGINAL").update(end_station="B"), "end_station_mismatch"),
        (lambda d: _by_id(d["aircraft_strings"], "string_id", "AS_AC4_ORIGINAL").update(maintenance_satisfied=False), "maintenance_not_satisfied"),
        (lambda d: _by_id(d["crew_pairings"], "pairing_id", "CP_C1_ORIGINAL")["duties"][0]["segments"][1].update(flight_option_id="FO_F11_ORIG"), "station_discontinuity"),
        (lambda d: _by_id(d["passenger_itineraries"], "itinerary_id", "PI_P4_REACCOM_F8").update(final_destination="C"), "destination_mismatch"),
        (lambda d: _by_id(d["passenger_itineraries"], "itinerary_id", "PI_P4_REACCOM_F8")["segments"][0].update(flight_option_id="FO_F3_CANCEL"), "invalid_passenger_flight_option"),
        (lambda d: _by_id(d["flight_options"], "option_id", "FO_F2_D50").update(departure_delay_minutes=49), "departure_delay_mismatch"),
        (lambda d: _by_id(d["flight_options"], "option_id", "FO_F2_D50").update(change_types=["unchanged"]), "change_type_mismatch"),
        (lambda d: _by_id(d["flight_options"], "option_id", "FO_F2_D50").update(block_minutes=59), "block_time_mismatch"),
    ],
)
def test_column_negative_cases_report_specific_codes(
    scenario, phase1_columns_001_data, mutation, expected_code
):
    mutation(phase1_columns_001_data)
    _, issues = validate_recovery_columns(scenario, phase1_columns_001_data)
    assert expected_code in _codes(issues)


def test_cancel_option_with_dep_time_is_structurally_rejected(scenario, phase1_columns_001_data):
    _by_id(phase1_columns_001_data["flight_options"], "option_id", "FO_F3_CANCEL")["dep_time"] = "2026-01-15T11:00:00Z"
    columns, issues = validate_recovery_columns(scenario, phase1_columns_001_data)
    assert columns is None
    assert issues


def test_phase1_does_not_claim_passenger_seat_capacity_validation(
    scenario, phase1_columns_001_data
):
    scenario.passengers[0].count = 100_000
    columns, issues = validate_recovery_columns(scenario, phase1_columns_001_data)
    assert columns is not None
    assert issues == []
