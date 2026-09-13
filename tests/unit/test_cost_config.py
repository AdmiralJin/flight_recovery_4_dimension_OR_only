from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.config.costs import (
    CostOverrideConfig,
    CostOwner,
    CostSource,
    FixedColumnCostConfig,
    apply_cost_overrides,
    load_cost_config,
    schedule_flight_option_cost,
)
from backend.services.column_validator import validate_recovery_columns
from backend.services.validator import validate_scenario


COST_PATH = (
    Path(__file__).parents[2] / "data" / "costs" / "phase2_test_costs_v1.json"
)


@pytest.fixture
def cost_data():
    return FixedColumnCostConfig.model_validate_json(
        COST_PATH.read_text(encoding="utf-8")
    ).model_dump(mode="json")


def test_canonical_cost_profile_loads_with_units_sources_and_owners():
    costs = load_cost_config(COST_PATH)

    assert costs.cost_profile_id == "phase2_test_v1"
    assert costs.units == "abstract_cost_units"
    assert costs.coefficients.flight_cancellation.value == 25000.0
    assert (
        costs.coefficients.flight_cancellation.source
        is CostSource.PETERSEN_2010_TABLE_2
    )
    assert costs.coefficients.flight_delay_per_minute.owner is CostOwner.SRM
    assert costs.coefficients.ferry_per_minute.owner is CostOwner.ARM
    assert costs.coefficients.deadhead_per_minute.owner is CostOwner.CRM
    assert costs.coefficients.unserved_passenger.owner is CostOwner.PRM


def test_phase2_cost_ownership_is_complete_and_has_no_duplicate_owner():
    costs = load_cost_config(COST_PATH)
    expected = {
        "flight_delay_per_minute": CostOwner.SRM,
        "flight_cancellation": CostOwner.SRM,
        "origin_change": CostOwner.SRM,
        "destination_change": CostOwner.SRM,
        "aircraft_reassignment": CostOwner.ARM,
        "ferry_per_minute": CostOwner.ARM,
        "crew_reassignment": CostOwner.CRM,
        "deadhead_per_minute": CostOwner.CRM,
        "passenger_delay_per_pax_minute": CostOwner.PRM,
        "unserved_passenger": CostOwner.PRM,
    }

    actual = {
        name: coefficient.owner
        for name, coefficient in costs.coefficients
    }
    assert actual == expected


def test_cost_config_serialization_round_trip():
    costs = load_cost_config(COST_PATH)
    assert FixedColumnCostConfig.model_validate_json(costs.model_dump_json()) == costs


def test_cost_config_rejects_unknown_field(cost_data):
    cost_data["coefficients"]["flight_cancellation"]["mystery"] = True

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        FixedColumnCostConfig.model_validate(cost_data)


def test_cost_config_rejects_missing_required_coefficient(cost_data):
    del cost_data["coefficients"]["flight_cancellation"]

    with pytest.raises(ValidationError, match="Field required"):
        FixedColumnCostConfig.model_validate(cost_data)


@pytest.mark.parametrize("value", [-1.0, float("nan"), float("inf")])
def test_cost_config_rejects_negative_nan_and_infinity(cost_data, value):
    cost_data["coefficients"]["flight_delay_per_minute"]["value"] = value

    with pytest.raises(ValidationError):
        FixedColumnCostConfig.model_validate(cost_data)


@pytest.mark.parametrize(
    ("field", "key", "value", "message"),
    [
        ("flight_delay_per_minute", "owner", "ARM", "owner must be"),
        (
            "flight_delay_per_minute",
            "unit",
            "cost_unit_per_ferry_minute",
            "unit must be",
        ),
    ],
)
def test_cost_config_rejects_wrong_owner_or_dimensional_unit(
    cost_data, field, key, value, message
):
    cost_data["coefficients"][field][key] = value

    with pytest.raises(ValidationError, match=message):
        FixedColumnCostConfig.model_validate(cost_data)


def test_schedule_cost_uses_canonical_config_without_magic_numbers(
    phase1_benchmark_001_data, phase1_columns_001_data
):
    scenario, scenario_issues = validate_scenario(phase1_benchmark_001_data)
    assert scenario is not None and scenario_issues == []
    columns, column_issues = validate_recovery_columns(
        scenario, phase1_columns_001_data
    )
    assert columns is not None and column_issues == []
    costs = load_cost_config(COST_PATH)
    options = {option.option_id: option for option in columns.flight_options}

    assert schedule_flight_option_cost(
        scenario, options["FO_F2_D50"], costs
    ) == pytest.approx(50.0)
    assert schedule_flight_option_cost(
        scenario, options["FO_F3_CANCEL"], costs
    ) == pytest.approx(25000.0)
    assert schedule_flight_option_cost(
        scenario, options["FO_F11_DEST_C"], costs
    ) == pytest.approx(5000.0)
    assert schedule_flight_option_cost(
        scenario, options["FO_FERRY_CA_1140"], costs
    ) == 0.0


def test_cost_override_changes_only_effective_value_and_keeps_baseline_immutable():
    baseline = load_cost_config(COST_PATH)
    before = baseline.model_dump(mode="json")
    override = CostOverrideConfig(
        base_cost_profile_id=baseline.cost_profile_id,
        overrides={"flight_delay_per_minute": 7.5},
    )

    effective = apply_cost_overrides(baseline, override)

    assert baseline.model_dump(mode="json") == before
    assert effective.coefficients.flight_delay_per_minute.value == 7.5
    assert (
        effective.coefficients.flight_delay_per_minute.model_dump(exclude={"value"})
        == baseline.coefficients.flight_delay_per_minute.model_dump(exclude={"value"})
    )


def test_cost_override_rejects_unknown_key_and_profile_mismatch():
    baseline = load_cost_config(COST_PATH)
    with pytest.raises(ValueError, match="unknown cost override keys"):
        apply_cost_overrides(
            baseline,
            CostOverrideConfig(
                base_cost_profile_id=baseline.cost_profile_id,
                overrides={"not_a_cost": 1.0},
            ),
        )
    with pytest.raises(ValueError, match="differs from canonical profile"):
        apply_cost_overrides(
            baseline,
            CostOverrideConfig(
                base_cost_profile_id="wrong-profile",
                overrides={},
            ),
        )


@pytest.mark.parametrize("value", [-1.0, float("nan"), float("inf")])
def test_cost_override_rejects_negative_nan_and_infinity(value):
    with pytest.raises(ValidationError):
        CostOverrideConfig(
            base_cost_profile_id="phase2_test_v1",
            overrides={"flight_delay_per_minute": value},
        )
