from backend.config import CrewPairingGenerationConfig, PairingGenerationSource
from backend.core import (
    brute_force_legal_crew_pairings,
    generate_crew_pairings,
    pairing_semantic_key,
)
from backend.schemas.columns import RecoveryColumns
from backend.schemas.scenario import Scenario


def test_smart_pairing_generator_matches_exhaustive_oracle(
    toy_case_008_crew_pairing_generator_data,
    toy_case_008_crew_pairing_generator_columns_data,
):
    scenario = Scenario.model_validate(toy_case_008_crew_pairing_generator_data)
    columns = RecoveryColumns.model_validate(
        toy_case_008_crew_pairing_generator_columns_data
    )
    config = CrewPairingGenerationConfig(
        schema_version="1.0.0",
        profile_id="phase6_toy_oracle",
        default_min_connection_minutes=15,
        max_duty_minutes=240,
        max_deadhead_legs=1,
        allow_deadhead=True,
        allow_idle=True,
        source=PairingGenerationSource.TEST_FIXTURE,
        notes=("IMPLEMENTATION ASSUMPTION",),
    )
    smart = tuple(
        item
        for item in generate_crew_pairings(
            scenario, columns.flight_options, None, config
        )
        if item.crew_id == "S8_C1"
    )
    brute = brute_force_legal_crew_pairings(
        scenario, columns.flight_options, scenario.crew[0], config
    )
    smart_keys = {pairing_semantic_key(item) for item in smart}
    brute_keys = {pairing_semantic_key(item) for item in brute}
    assert smart_keys == brute_keys
    assert len(smart_keys) > 1
