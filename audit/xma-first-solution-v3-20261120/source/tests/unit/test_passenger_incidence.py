from copy import deepcopy
from dataclasses import FrozenInstanceError

import pytest

from backend.core import build_passenger_recovery_incidence, build_recovery_indices
from backend.schemas.columns import RecoveryColumns
from backend.services.column_validator import validate_recovery_columns
from backend.services.validator import validate_scenario


def _validated(scenario_data, columns_data):
    scenario, scenario_issues = validate_scenario(scenario_data)
    assert scenario is not None and scenario_issues == []
    columns, column_issues = validate_recovery_columns(scenario, columns_data)
    assert columns is not None and column_issues == []
    return scenario, columns


def test_passenger_incidence_is_deterministic_and_bidirectional(
    phase1_benchmark_001_data, phase1_columns_001_data
):
    scenario, columns = _validated(
        phase1_benchmark_001_data, phase1_columns_001_data
    )
    incidence = build_passenger_recovery_incidence(scenario, columns)

    assert incidence.group_to_itineraries.columns_for_row("P4") == (
        "PI_P4_ORIGINAL",
        "PI_P4_RECOVERY",
        "PI_P4_REACCOM_F8",
    )
    assert incidence.option_to_itineraries.columns_for_row("FO_F8_ORIG") == (
        "PI_P3_ORIGINAL",
        "PI_P4_REACCOM_F8",
    )
    assert incidence.itinerary_to_flight_options["PI_P4_RECOVERY"] == (
        "FO_F2_D50",
        "FO_F3_D30",
    )
    assert "PI_P5_UNSERVED" in incidence.unserved_itineraries
    assert "PI_P1_ORIGINAL" in incidence.transported_itineraries


def test_passenger_incidence_is_immutable(
    toy_case_003_data, toy_case_003_columns_data
):
    scenario, columns = _validated(toy_case_003_data, toy_case_003_columns_data)
    incidence = build_passenger_recovery_incidence(scenario, columns)

    with pytest.raises(TypeError):
        incidence.itinerary_to_flight_options["x"] = ()  # type: ignore[index]
    with pytest.raises(FrozenInstanceError):
        incidence.transported_itineraries = ()  # type: ignore[misc]


def test_surface_segment_does_not_create_flight_incidence(
    toy_case_003_data, toy_case_003_columns_data
):
    columns_data = deepcopy(toy_case_003_columns_data)
    alt = next(
        item
        for item in columns_data["passenger_itineraries"]
        if item["itinerary_id"] == "PI_T3_P2_ALT"
    )
    alt["segments"][0] = {
        "segment_type": "surface",
        "flight_option_id": None,
        "origin": "A",
        "destination": "B",
        "dep_time": "2026-01-15T08:15:00Z",
        "arr_time": "2026-01-15T09:15:00Z",
    }
    scenario, columns = _validated(toy_case_003_data, columns_data)
    incidence = build_passenger_recovery_incidence(scenario, columns)

    assert incidence.itinerary_to_flight_options["PI_T3_P2_ALT"] == (
        "FO_T3_F3_ORIG",
    )
    assert "PI_T3_P2_ALT" not in incidence.option_to_itineraries.columns_for_row(
        "FO_T3_F2_ORIG"
    )


def test_passenger_incidence_rejects_unknown_option_reference(
    toy_case_003_data, toy_case_003_columns_data
):
    scenario, issues = validate_scenario(toy_case_003_data)
    assert scenario is not None and issues == []
    columns_data = deepcopy(toy_case_003_columns_data)
    columns_data["passenger_itineraries"][0]["segments"][0][
        "flight_option_id"
    ] = "UNKNOWN"
    columns = RecoveryColumns.model_validate(columns_data)

    with pytest.raises(ValueError, match="unknown option"):
        build_passenger_recovery_incidence(scenario, columns)


def test_passenger_incidence_rejects_mismatched_indices(
    toy_case_003_data, toy_case_003_columns_data
):
    scenario, columns = _validated(toy_case_003_data, toy_case_003_columns_data)
    wrong_columns = columns.model_copy(
        update={"passenger_itineraries": columns.passenger_itineraries[:-1]}
    )
    wrong_indices = build_recovery_indices(scenario, wrong_columns)

    with pytest.raises(ValueError, match="indices do not match"):
        build_passenger_recovery_incidence(scenario, columns, wrong_indices)
