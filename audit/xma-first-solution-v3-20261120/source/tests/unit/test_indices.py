from dataclasses import FrozenInstanceError

import pytest

from backend.core.indices import CapacityIntervalKey, OrderedIndex, build_recovery_indices
from backend.services.column_validator import validate_recovery_columns
from backend.services.validator import validate_scenario


def _validated_inputs(scenario_data, columns_data):
    scenario, scenario_issues = validate_scenario(scenario_data)
    assert scenario is not None and scenario_issues == []
    columns, column_issues = validate_recovery_columns(scenario, columns_data)
    assert columns is not None and column_issues == []
    return scenario, columns


def test_ordered_index_preserves_order_and_supports_bidirectional_lookup():
    index = OrderedIndex.from_ids(["F3", "F1", "F2"])

    assert index.ids == ("F3", "F1", "F2")
    assert index.position_of("F1") == 1
    assert index.id_at(2) == "F2"
    assert "F3" in index
    assert len(index) == 3


def test_ordered_index_unknown_id_and_position_fail_explicitly():
    index = OrderedIndex.from_ids(["F1"])

    with pytest.raises(KeyError, match="UNKNOWN"):
        index.position_of("UNKNOWN")
    with pytest.raises(IndexError):
        index.id_at(1)


def test_ordered_index_rejects_duplicate_ids():
    with pytest.raises(ValueError, match="duplicate index ID"):
        OrderedIndex.from_ids(["F1", "F1"])


def test_ordered_index_supports_an_empty_optional_set_and_is_immutable():
    index = OrderedIndex.from_ids([])

    assert index.ids == ()
    assert len(index) == 0
    with pytest.raises(TypeError):
        index.position["F1"] = 0  # type: ignore[index]
    with pytest.raises(FrozenInstanceError):
        index.ids = ("F1",)  # type: ignore[misc]


def test_recovery_indices_preserve_explicit_input_order_and_structured_capacity_keys(
    phase1_benchmark_001_data, phase1_columns_001_data
):
    scenario, columns = _validated_inputs(
        phase1_benchmark_001_data, phase1_columns_001_data
    )
    indices = build_recovery_indices(scenario, columns)

    assert indices.flights.ids == tuple(item.flight_id for item in scenario.flights)
    assert indices.flight_options.ids == tuple(
        item.option_id for item in columns.flight_options
    )
    assert indices.operate_options.ids == tuple(
        item.option_id
        for item in columns.flight_options
        if item.operation_type.value == "operate"
    )
    assert indices.cancel_options.ids == tuple(
        item.option_id
        for item in columns.flight_options
        if item.operation_type.value == "cancel"
    )
    assert indices.ferry_options.ids == ("FO_FERRY_CA_1140",)
    assert indices.revenue_operate_options.ids == indices.operate_options.ids
    assert indices.aircraft_strings.ids == tuple(
        item.string_id for item in columns.aircraft_strings
    )
    assert indices.maintenance_aircraft.ids == ("AC4",)
    assert indices.capacity_intervals.ids[0] == CapacityIntervalKey(
        airport=scenario.airport_intervals[0].airport,
        start_time=scenario.airport_intervals[0].start_time,
        end_time=scenario.airport_intervals[0].end_time,
    )
