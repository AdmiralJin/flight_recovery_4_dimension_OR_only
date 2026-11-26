from copy import deepcopy

import pytest
from pydantic import ValidationError

from backend.schemas.columns import RecoveryColumns


def test_columns_schema_accepts_benchmark_and_round_trips(phase1_columns_001_data):
    columns = RecoveryColumns.model_validate(phase1_columns_001_data)
    assert len(columns.flight_options) == 22
    assert len(columns.aircraft_strings) == 11
    assert len(columns.crew_pairings) == 10
    assert len(columns.passenger_itineraries) == 17
    assert RecoveryColumns.model_validate_json(columns.model_dump_json()) == columns


def test_columns_schema_forbids_unknown_fields(phase1_columns_001_data):
    phase1_columns_001_data["flight_options"][0]["mystery"] = True
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        RecoveryColumns.model_validate(phase1_columns_001_data)


def test_columns_schema_requires_timezone(phase1_columns_001_data):
    phase1_columns_001_data["flight_options"][0]["dep_time"] = "2026-01-15T08:00:00"
    with pytest.raises(ValidationError, match="timezone"):
        RecoveryColumns.model_validate(phase1_columns_001_data)


def test_cancel_option_rejects_operated_fields(phase1_columns_001_data):
    cancel = next(item for item in phase1_columns_001_data["flight_options"] if item["operation_type"] == "cancel")
    cancel["dep_time"] = "2026-01-15T11:00:00Z"
    with pytest.raises(ValidationError, match="cancel option cannot contain"):
        RecoveryColumns.model_validate(phase1_columns_001_data)


def test_fixture_is_deep_copied(phase1_columns_001_data):
    other = deepcopy(phase1_columns_001_data)
    other["flight_options"].clear()
    assert len(phase1_columns_001_data["flight_options"]) == 22
