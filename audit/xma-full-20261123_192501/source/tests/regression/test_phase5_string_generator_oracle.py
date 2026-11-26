from pathlib import Path

from backend.config import load_flight_string_generation_config
from backend.core import (
    brute_force_legal_aircraft_strings,
    generate_aircraft_strings_with_metrics,
)
from backend.schemas.columns import RecoveryColumns
from backend.schemas.scenario import Scenario


ROOT = Path(__file__).parents[2]


def test_smart_generator_equals_brute_force_legal_sequence_oracle(
    toy_case_007_string_generator_data,
    toy_case_007_string_generator_columns_data,
):
    scenario = Scenario.model_validate(toy_case_007_string_generator_data)
    columns = RecoveryColumns.model_validate(
        toy_case_007_string_generator_columns_data
    )
    config = load_flight_string_generation_config(
        ROOT / "data" / "config" / "phase5_test_string_generation_v1.json"
    )
    smart = generate_aircraft_strings_with_metrics(
        scenario, columns.flight_options, None, config
    )

    for aircraft in scenario.aircraft:
        smart_keys = {
            tuple(item.leg_option_ids)
            for item in smart.strings
            if item.aircraft_id == aircraft.tail_id
        }
        brute_keys = {
            tuple(item.leg_option_ids)
            for item in brute_force_legal_aircraft_strings(
                scenario, columns.flight_options, aircraft, config
            )
        }
        assert smart_keys == brute_keys

    assert smart.metrics["generated_string_count_by_aircraft"] == {
        "S7_AC1": 3,
        "S7_AC2": 1,
        "S7_AC3": 2,
    }
