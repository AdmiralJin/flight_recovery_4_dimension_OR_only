import copy

import pytest

from backend.core.gate_inventory import (
    GateInventoryBuildError,
    build_gate_inventory_data,
)
from backend.schemas.columns import RecoveryColumns
from backend.schemas.scenario import Scenario
from backend.services.validator import validate_scenario


def _inputs(scenario_data, columns_data):
    scenario, issues = validate_scenario(copy.deepcopy(scenario_data))
    assert scenario is not None
    assert issues == []
    columns = RecoveryColumns.model_validate(copy.deepcopy(columns_data))
    return scenario, columns


def _checkpoint(gate_data, airport, timestamp):
    return next(
        item
        for item in gate_data.checkpoints_for_airport(airport)
        if item.timestamp.isoformat().replace("+00:00", "Z") == timestamp
    )


def _varying_gate_inputs(*, terminal_end="2026-01-15T16:00:00Z"):
    scenario = Scenario.model_validate(
        {
            "scenario_id": "gate_boundary_case",
            "recovery_window": {
                "start_time": "2026-01-15T08:00:00Z",
                "end_time": "2026-01-15T16:00:00Z",
            },
            "airports": [{"airport_id": "A", "name": "Alpha"}],
            "flights": [],
            "aircraft": [],
            "crew": [],
            "passengers": [],
            "airport_intervals": [
                {
                    "airport": "A",
                    "start_time": "2026-01-15T08:00:00Z",
                    "end_time": "2026-01-15T12:00:00Z",
                    "arr_capacity": 10,
                    "dep_capacity": 10,
                    "gate_capacity": 4,
                    "curfew_flag": False,
                    "weather_restrictions": [],
                },
                {
                    "airport": "A",
                    "start_time": "2026-01-15T12:00:00Z",
                    "end_time": terminal_end,
                    "arr_capacity": 10,
                    "dep_capacity": 10,
                    "gate_capacity": 3,
                    "curfew_flag": False,
                    "weather_restrictions": [],
                },
            ],
            "disruptions": [],
        }
    )
    columns = RecoveryColumns.model_validate(
        {
            "schema_version": "1.0.0",
            "scenario_id": scenario.scenario_id,
            "time_unit": "minute",
            "notes": [],
            "flight_options": [],
            "aircraft_strings": [],
            "crew_pairings": [],
            "passenger_itineraries": [],
        }
    )
    return scenario, columns


def test_gate_internal_boundary_uses_next_interval():
    scenario, columns = _varying_gate_inputs()

    checkpoint = _checkpoint(
        build_gate_inventory_data(scenario, columns),
        "A",
        "2026-01-15T12:00:00Z",
    )

    assert checkpoint.gate_capacity == 3
    assert checkpoint.capacity_source_key.start_time.isoformat() == (
        "2026-01-15T12:00:00+00:00"
    )


def test_gate_terminal_boundary_accepts_varying_capacities():
    scenario, columns = _varying_gate_inputs()

    checkpoint = _checkpoint(
        build_gate_inventory_data(scenario, columns),
        "A",
        "2026-01-15T16:00:00Z",
    )

    assert checkpoint.gate_capacity == 3
    assert checkpoint.capacity_source_key.end_time == scenario.recovery_window.end_time


def test_gate_terminal_boundary_rejects_ambiguous_capacity():
    scenario, columns = _varying_gate_inputs(terminal_end="2026-01-15T15:00:00Z")

    with pytest.raises(GateInventoryBuildError, match="ambiguous terminal"):
        build_gate_inventory_data(scenario, columns)


def test_gate_builder_tracks_departure_and_arrival_inventory(
    phase1_benchmark_001_data, phase1_columns_001_data
):
    scenario, columns = _inputs(phase1_benchmark_001_data, phase1_columns_001_data)

    gate_data = build_gate_inventory_data(scenario, columns)

    at_a_start = _checkpoint(gate_data, "A", "2026-01-15T08:00:00Z")
    at_b_arrival = _checkpoint(gate_data, "B", "2026-01-15T09:00:00Z")
    assert at_a_start.initial_ground == 1
    assert at_a_start.coefficient_by_option["FO_F1_ORIG"] == -1
    assert at_b_arrival.initial_ground == 0
    assert at_b_arrival.coefficient_by_option["FO_F1_ORIG"] == 1


def test_gate_builder_nets_same_timestamp_events(
    phase1_benchmark_001_data, phase1_columns_001_data
):
    scenario, columns = _inputs(phase1_benchmark_001_data, phase1_columns_001_data)

    checkpoint = _checkpoint(
        build_gate_inventory_data(scenario, columns),
        "C",
        "2026-01-15T11:30:00Z",
    )

    assert checkpoint.coefficient_by_option["FO_F2_D50"] == 1
    assert checkpoint.coefficient_by_option["FO_F3_D30"] == -1
    assert checkpoint.coefficient_by_option["FO_F10_D20"] == -1


def test_gate_builder_excludes_cancel_and_ferry_and_is_immutable(
    phase1_benchmark_001_data, phase1_columns_001_data
):
    scenario, columns = _inputs(phase1_benchmark_001_data, phase1_columns_001_data)

    gate_data = build_gate_inventory_data(scenario, columns)
    all_coefficients = {
        option_id
        for checkpoint in gate_data.checkpoints
        for option_id in checkpoint.coefficient_by_option
    }

    assert "FO_F3_CANCEL" not in all_coefficients
    assert "FO_FERRY_CA_1140" not in all_coefficients
    with pytest.raises(TypeError):
        gate_data.initial_ground_by_airport["A"] = 99
    with pytest.raises(TypeError):
        gate_data.checkpoints[0].coefficient_by_option["bad"] = 1


def test_gate_builder_is_deterministic(
    phase1_benchmark_001_data, phase1_columns_001_data
):
    scenario, columns = _inputs(phase1_benchmark_001_data, phase1_columns_001_data)

    first = build_gate_inventory_data(scenario, columns)
    second = build_gate_inventory_data(scenario, columns)

    assert [item.checkpoint_id for item in first.checkpoints] == [
        item.checkpoint_id for item in second.checkpoints
    ]
    assert [dict(item.coefficient_by_option) for item in first.checkpoints] == [
        dict(item.coefficient_by_option) for item in second.checkpoints
    ]


def test_gate_builder_rejects_initial_inventory_above_capacity(
    phase1_benchmark_001_data, phase1_columns_001_data
):
    scenario_data = copy.deepcopy(phase1_benchmark_001_data)
    for interval in scenario_data["airport_intervals"]:
        if interval["airport"] == "D":
            interval["gate_capacity"] = 0
    scenario, columns = _inputs(scenario_data, phase1_columns_001_data)

    with pytest.raises(GateInventoryBuildError, match="initial ground inventory"):
        build_gate_inventory_data(scenario, columns)


def test_gate_builder_rejects_movement_airport_without_interval(
    phase1_benchmark_001_data, phase1_columns_001_data
):
    scenario_data = copy.deepcopy(phase1_benchmark_001_data)
    scenario_data["airport_intervals"] = [
        interval
        for interval in scenario_data["airport_intervals"]
        if interval["airport"] != "C"
    ]
    scenario, columns = _inputs(scenario_data, phase1_columns_001_data)

    with pytest.raises(GateInventoryBuildError, match="no AirportInterval"):
        build_gate_inventory_data(scenario, columns)


def test_gate_builder_rejects_duplicate_option_coefficient_source(
    phase1_benchmark_001_data, phase1_columns_001_data
):
    columns_data = copy.deepcopy(phase1_columns_001_data)
    columns_data["flight_options"].append(
        copy.deepcopy(columns_data["flight_options"][0])
    )
    scenario, columns = _inputs(phase1_benchmark_001_data, columns_data)

    with pytest.raises(GateInventoryBuildError, match="duplicate flight option ID"):
        build_gate_inventory_data(scenario, columns)
