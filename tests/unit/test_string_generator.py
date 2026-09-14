from pathlib import Path

import pytest

from backend.config import load_flight_string_generation_config
from backend.core import (
    RecoveryScope,
    generate_aircraft_strings_with_metrics,
    validate_generated_aircraft_string,
)
from backend.schemas.columns import AircraftString, RecoveryColumns
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


def _candidate(aircraft, option_ids):
    return AircraftString(
        string_id="TEST_STRING",
        aircraft_id=aircraft.tail_id,
        leg_option_ids=option_ids,
        start_station=aircraft.initial_station_at_t,
        end_station=aircraft.required_station_at_T_end,
        maintenance_satisfied=True,
        cost_components={},
        notes="",
    )


def test_turn_profile_is_versioned_and_immutable():
    config = load_flight_string_generation_config(
        ROOT / "data" / "config" / "phase5_test_string_generation_v1.json"
    )
    assert config.profile_id == "phase5_test_string_generation_v1"
    assert config.min_turn_minutes("E1") == 0
    assert config.min_turn_minutes("E2") == 15
    with pytest.raises(TypeError):
        config.equipment_overrides["E2"] = 20  # type: ignore[index]


def test_independent_validator_rejects_station_turn_terminal_and_duplicate(
    toy_case_007_string_generator_data,
    toy_case_007_string_generator_columns_data,
):
    scenario, columns, config = _inputs(
        toy_case_007_string_generator_data,
        toy_case_007_string_generator_columns_data,
    )
    aircraft = scenario.aircraft[0]
    cases = {
        "station_discontinuity": ["S7_O1", "S7_UO1"],
        "turn_time_violation": ["S7_O1", "S7_O2", "S7_O4"],
        "last_leg_terminal_mismatch": ["S7_O1", "S7_O3"],
        "duplicate_flight_option": ["S7_O1", "S7_O1"],
    }
    for expected, option_ids in cases.items():
        result = validate_generated_aircraft_string(
            scenario,
            columns.flight_options,
            aircraft,
            _candidate(aircraft, option_ids),
            config,
        )
        assert not result.valid
        assert expected in result.violations


def test_idle_and_maintenance_terminal_semantics(
    toy_case_007_string_generator_data,
    toy_case_007_string_generator_columns_data,
):
    scenario, columns, config = _inputs(
        toy_case_007_string_generator_data,
        toy_case_007_string_generator_columns_data,
    )
    ac1 = scenario.aircraft[0]
    ac2 = scenario.aircraft[1]
    assert validate_generated_aircraft_string(
        scenario, columns.flight_options, ac1, _candidate(ac1, []), config
    ).valid
    assert "idle_terminal_mismatch" in validate_generated_aircraft_string(
        scenario, columns.flight_options, ac2, _candidate(ac2, []), config
    ).violations

    maintenance_aircraft = ac1.model_copy(
        update={
            "maintenance_required": True,
            "maintenance_stations": ["B"],
        }
    )
    result = validate_generated_aircraft_string(
        scenario,
        columns.flight_options,
        maintenance_aircraft,
        _candidate(maintenance_aircraft, ["S7_O1", "S7_O3", "S7_O4"]),
        config,
    )
    assert "maintenance_station_mismatch" in result.violations


def test_generator_retains_original_supports_ferry_and_has_no_duplicates(
    toy_case_007_string_generator_data,
    toy_case_007_string_generator_columns_data,
):
    scenario, columns, config = _inputs(
        toy_case_007_string_generator_data,
        toy_case_007_string_generator_columns_data,
    )
    result = generate_aircraft_strings_with_metrics(
        scenario, columns.flight_options, None, config
    )
    keys = [(item.aircraft_id, tuple(item.leg_option_ids)) for item in result.strings]
    assert len(keys) == len(set(keys))
    assert ("S7_AC1", ("S7_O1", "S7_O3", "S7_O4")) in keys
    assert ("S7_AC1", ("S7_FERRY_AC", "S7_O4")) in keys
    assert ("S7_AC1", ()) in keys
    assert result.metrics["generated_string_count_by_aircraft"] == {
        "S7_AC1": 3,
        "S7_AC2": 1,
        "S7_AC3": 2,
    }


def test_scope_enumerates_only_scoped_aircraft_and_keeps_other_originals(
    toy_case_007_string_generator_data,
    toy_case_007_string_generator_columns_data,
):
    scenario, columns, config = _inputs(
        toy_case_007_string_generator_data,
        toy_case_007_string_generator_columns_data,
    )
    scope = RecoveryScope(
        direct_flight_ids=(),
        flight_ids=(),
        aircraft_ids=("S7_AC1",),
        crew_ids=(),
        passenger_group_ids=(),
        flight_option_ids=(),
        aircraft_string_ids=(),
        crew_pairing_ids=(),
        passenger_itinerary_ids=(),
        propagation_reasons={},
        iteration_count=1,
    )
    result = generate_aircraft_strings_with_metrics(
        scenario, columns.flight_options, scope, config
    )
    by_aircraft = {
        aircraft.tail_id: [
            tuple(item.leg_option_ids)
            for item in result.strings
            if item.aircraft_id == aircraft.tail_id
        ]
        for aircraft in scenario.aircraft
    }
    assert len(by_aircraft["S7_AC1"]) == 3
    assert by_aircraft["S7_AC2"] == [("S7_UO1",)]
    assert by_aircraft["S7_AC3"] == [("S7_O2",)]
    assert result.metrics["scoped_aircraft_count"] == 1


def test_generator_output_is_deterministic(
    toy_case_007_string_generator_data,
    toy_case_007_string_generator_columns_data,
):
    scenario, columns, config = _inputs(
        toy_case_007_string_generator_data,
        toy_case_007_string_generator_columns_data,
    )
    first = generate_aircraft_strings_with_metrics(
        scenario, columns.flight_options, None, config
    )
    second = generate_aircraft_strings_with_metrics(
        scenario, tuple(reversed(columns.flight_options)), None, config
    )
    first_values = [item.model_dump(mode="json") for item in first.strings]
    second_values = [item.model_dump(mode="json") for item in second.strings]
    assert first_values == second_values
