from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.config import (
    PassengerCapacityError,
    PassengerCapacityProfile,
    PassengerCapacitySource,
    load_passenger_capacity_profile,
    validate_passenger_capacity_profile,
)
from backend.services.column_validator import validate_recovery_columns
from backend.services.validator import validate_scenario


CAPACITY_PATH = (
    Path(__file__).parents[2]
    / "data"
    / "capacities"
    / "phase2_test_seat_capacity_v1.json"
)


@pytest.fixture
def validated_benchmark(phase1_benchmark_001_data, phase1_columns_001_data):
    scenario, scenario_issues = validate_scenario(phase1_benchmark_001_data)
    assert scenario is not None and scenario_issues == []
    columns, column_issues = validate_recovery_columns(
        scenario, phase1_columns_001_data
    )
    assert columns is not None and column_issues == []
    return scenario, columns


def test_capacity_profile_loads_as_read_only_versioned_contract():
    profile = load_passenger_capacity_profile(CAPACITY_PATH)

    assert profile.schema_version == "1.0.0"
    assert profile.source is PassengerCapacitySource.IMPLEMENTATION_ASSUMPTION
    assert profile.units == "seats"
    assert profile.seat_capacity_by_option_id["FO_F8_ORIG"] == 35
    with pytest.raises(TypeError):
        profile.seat_capacity_by_option_id["FO_F8_ORIG"] = 999  # type: ignore[index]
    with pytest.raises(ValidationError):
        profile.scenario_id = "changed"  # type: ignore[misc]
    assert (
        PassengerCapacityProfile.model_validate_json(profile.model_dump_json())
        == profile
    )


@pytest.mark.parametrize("value", [-1, True, 2.5, "10"])
def test_capacity_profile_rejects_non_nonnegative_integer_capacity(value):
    data = load_passenger_capacity_profile(CAPACITY_PATH).model_dump(mode="python")
    data["seat_capacity_by_option_id"] = dict(data["seat_capacity_by_option_id"])
    data["seat_capacity_by_option_id"]["FO_F1_ORIG"] = value

    with pytest.raises(ValidationError):
        PassengerCapacityProfile.model_validate(data)


def test_capacity_profile_rejects_unknown_cancel_and_ferry_options(
    validated_benchmark,
):
    scenario, columns = validated_benchmark
    base = load_passenger_capacity_profile(CAPACITY_PATH).model_dump(mode="python")

    for invalid_option in ("UNKNOWN", "FO_F3_CANCEL", "FO_FERRY_CA_1140"):
        data = deepcopy(base)
        data["seat_capacity_by_option_id"] = dict(
            data["seat_capacity_by_option_id"]
        )
        data["seat_capacity_by_option_id"][invalid_option] = 1
        profile = PassengerCapacityProfile.model_validate(data)
        with pytest.raises(PassengerCapacityError):
            validate_passenger_capacity_profile(profile, scenario, columns)


def test_capacity_profile_rejects_scenario_mismatch(validated_benchmark):
    scenario, columns = validated_benchmark
    data = load_passenger_capacity_profile(CAPACITY_PATH).model_dump(mode="python")
    data["scenario_id"] = "other"
    profile = PassengerCapacityProfile.model_validate(data)

    with pytest.raises(PassengerCapacityError, match="scenario_id differs"):
        validate_passenger_capacity_profile(profile, scenario, columns)


def test_capacity_loader_rejects_duplicate_option_key(tmp_path):
    path = tmp_path / "duplicate.json"
    path.write_text(
        '{"schema_version":"1.0.0","capacity_profile_id":"x",'
        '"scenario_id":"s","source":"test_fixture","units":"seats",'
        '"seat_capacity_by_option_id":{"FO":1,"FO":2},"notes":[]}',
        encoding="utf-8",
    )

    with pytest.raises(PassengerCapacityError, match="duplicate JSON key"):
        load_passenger_capacity_profile(path)
