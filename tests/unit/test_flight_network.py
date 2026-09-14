from copy import deepcopy
from datetime import timedelta
from pathlib import Path

from backend.config import load_flight_string_generation_config
from backend.core import (
    build_aircraft_flight_network,
    validate_flight_option_for_aircraft,
)
from backend.schemas.columns import FlightOption, RecoveryColumns
from backend.schemas.scenario import Scenario


ROOT = Path(__file__).parents[2]


def _inputs(scenario_data, columns_data):
    return (
        Scenario.model_validate(scenario_data),
        RecoveryColumns.model_validate(columns_data),
        load_flight_string_generation_config(
            ROOT / "data" / "config" / "phase5_test_string_generation_v1.json"
        ),
    )


def test_network_requires_station_and_explicit_turn_time(
    toy_case_007_string_generator_data,
    toy_case_007_string_generator_columns_data,
):
    scenario, columns, config = _inputs(
        toy_case_007_string_generator_data,
        toy_case_007_string_generator_columns_data,
    )
    network = build_aircraft_flight_network(
        scenario, columns.flight_options, scenario.aircraft[0], config
    )

    assert network.min_turn_minutes == 15
    assert "S7_O2" not in network.successor_option_ids["S7_O1"]
    assert "S7_O3" in network.successor_option_ids["S7_O1"]
    assert "S7_UO1" not in network.start_option_ids
    assert network.rejected_edge_counts["station_mismatch"] > 0
    assert network.rejected_edge_counts["turn_time_violation"] > 0


def test_cancel_is_excluded_and_existing_ferry_is_supported(
    toy_case_007_string_generator_data,
    toy_case_007_string_generator_columns_data,
):
    scenario, columns, config = _inputs(
        toy_case_007_string_generator_data,
        toy_case_007_string_generator_columns_data,
    )
    aircraft = scenario.aircraft[0]
    by_id = {item.option_id: item for item in columns.flight_options}

    cancel = validate_flight_option_for_aircraft(
        scenario, by_id["S7_CANCEL_F1"], aircraft
    )
    ferry = validate_flight_option_for_aircraft(
        scenario, by_id["S7_FERRY_AC"], aircraft
    )
    assert not cancel.eligible
    assert cancel.reasons == ("cancel_excluded",)
    assert ferry.eligible
    assert "S7_FERRY_AC" in build_aircraft_flight_network(
        scenario, columns.flight_options, aircraft, config
    ).option_ids


def test_option_eligibility_rejects_max_delay_and_recovery_horizon(
    toy_case_007_string_generator_data,
    toy_case_007_string_generator_columns_data,
):
    scenario, columns, _ = _inputs(
        toy_case_007_string_generator_data,
        toy_case_007_string_generator_columns_data,
    )
    original = columns.flight_options[0]
    delayed = FlightOption.model_validate(
        {
            **original.model_dump(mode="json"),
            "option_id": "S7_D40",
            "change_types": ["delay"],
            "dep_time": original.dep_time + timedelta(minutes=40),
            "arr_time": original.arr_time + timedelta(minutes=40),
            "departure_delay_minutes": 40,
            "arrival_delay_minutes": 40,
        }
    )
    outside = FlightOption.model_validate(
        {
            **original.model_dump(mode="json"),
            "option_id": "S7_OUTSIDE",
            "change_types": ["delay"],
            "dep_time": "2026-01-15T11:30:00Z",
            "arr_time": "2026-01-15T12:30:00Z",
            "departure_delay_minutes": 210,
            "arrival_delay_minutes": 210,
        }
    )

    assert "max_delay_exceeded" in validate_flight_option_for_aircraft(
        scenario, delayed, scenario.aircraft[0]
    ).reasons
    assert "outside_recovery_horizon" in validate_flight_option_for_aircraft(
        scenario, outside, scenario.aircraft[0]
    ).reasons


def test_curfew_is_local_hard_restriction_but_capacity_reduction_is_not(
    toy_case_007_string_generator_data,
    toy_case_007_string_generator_columns_data,
    toy_case_006_scope_data,
    toy_case_006_scope_columns_data,
):
    data = deepcopy(toy_case_007_string_generator_data)
    data["airport_intervals"][0]["curfew_flag"] = True
    scenario, columns, _ = _inputs(
        data, toy_case_007_string_generator_columns_data
    )
    assert "departure_curfew" in validate_flight_option_for_aircraft(
        scenario, columns.flight_options[0], scenario.aircraft[0]
    ).reasons

    scope_scenario, scope_columns, _ = _inputs(
        toy_case_006_scope_data, toy_case_006_scope_columns_data
    )
    direct_option = scope_columns.flight_options[0]
    assert validate_flight_option_for_aircraft(
        scope_scenario, direct_option, scope_scenario.aircraft[0]
    ).eligible


def test_network_build_is_deterministic(
    toy_case_007_string_generator_data,
    toy_case_007_string_generator_columns_data,
):
    scenario, columns, config = _inputs(
        toy_case_007_string_generator_data,
        toy_case_007_string_generator_columns_data,
    )
    first = build_aircraft_flight_network(
        scenario, columns.flight_options, scenario.aircraft[0], config
    )
    second = build_aircraft_flight_network(
        scenario, tuple(reversed(columns.flight_options)), scenario.aircraft[0], config
    )
    assert first == second
