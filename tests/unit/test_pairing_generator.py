import json

import pytest

from backend.config import (
    CrewPairingGenerationConfig,
    CrewPairingGenerationConfigError,
    PairingGenerationSource,
    load_crew_pairing_generation_config,
)
from backend.core import (
    RecoveryScope,
    generate_crew_pairings,
    pairing_semantic_key,
    validate_generated_crew_pairing,
)
from backend.schemas.columns import (
    CrewDuty,
    CrewPairing,
    CrewSegment,
    CrewSegmentType,
    RecoveryColumns,
)
from backend.schemas.scenario import Scenario


def _config(**updates):
    data = {
        "schema_version": "1.0.0",
        "profile_id": "unit_phase6",
        "default_min_connection_minutes": 15,
        "max_duty_minutes": 480,
        "max_deadhead_legs": 1,
        "allow_deadhead": True,
        "allow_idle": True,
        "source": PairingGenerationSource.TEST_FIXTURE,
        "notes": ("IMPLEMENTATION ASSUMPTION",),
    }
    data.update(updates)
    return CrewPairingGenerationConfig.model_validate(data)


def _pairing(crew, *legs):
    return CrewPairing(
        pairing_id="TEST_PAIRING",
        crew_id=crew.crew_id,
        duties=[
            CrewDuty(
                duty_id="TEST_D1",
                segments=[
                    CrewSegment(
                        segment_type=segment_type,
                        flight_option_id=option_id,
                        origin=None,
                        destination=None,
                        start_time=None,
                        end_time=None,
                    )
                    for segment_type, option_id in legs
                ],
            )
        ],
        start_station=crew.start_station_at_t,
        end_station=crew.required_station_at_T_end,
    )


@pytest.fixture
def phase6_case(
    toy_case_008_crew_pairing_generator_data,
    toy_case_008_crew_pairing_generator_columns_data,
):
    return (
        Scenario.model_validate(toy_case_008_crew_pairing_generator_data),
        RecoveryColumns.model_validate(
            toy_case_008_crew_pairing_generator_columns_data
        ),
    )


def test_config_is_versioned_frozen_and_rejects_duplicate_json_keys(tmp_path):
    config = _config()
    with pytest.raises(Exception):
        config.max_duty_minutes = 10
    path = tmp_path / "duplicate.json"
    path.write_text(
        '{"schema_version":"1.0.0","profile_id":"x","profile_id":"y"}',
        encoding="utf-8",
    )
    with pytest.raises(CrewPairingGenerationConfigError, match="duplicate JSON key"):
        load_crew_pairing_generation_config(path)


def test_generator_is_deterministic_unique_and_retains_original(phase6_case):
    scenario, columns = phase6_case
    first = generate_crew_pairings(scenario, columns.flight_options, None, _config())
    second = generate_crew_pairings(scenario, columns.flight_options, None, _config())
    assert [item.model_dump(mode="json") for item in first] == [
        item.model_dump(mode="json") for item in second
    ]
    keys = [pairing_semantic_key(item) for item in first]
    assert len(keys) == len(set(keys))
    assert (
        "S8_C1",
        (
            ("operate", "S8_FO_F1_ORIG"),
            ("operate", "S8_FO_F2_ORIG"),
        ),
    ) in keys
    assert any("deadhead" in tuple(role for role, _ in key[1]) for key in keys)


def test_scope_generates_only_original_for_out_of_scope_crew(phase6_case):
    scenario, columns = phase6_case
    scope = RecoveryScope(
        direct_flight_ids=(),
        flight_ids=(),
        aircraft_ids=(),
        crew_ids=("S8_C1",),
        passenger_group_ids=(),
        flight_option_ids=(),
        aircraft_string_ids=(),
        crew_pairing_ids=(),
        passenger_itinerary_ids=(),
        propagation_reasons={},
        iteration_count=1,
    )
    generated = generate_crew_pairings(
        scenario, columns.flight_options, scope, _config()
    )
    c2 = [item for item in generated if item.crew_id == "S8_C2"]
    assert len(c2) == 1
    assert pairing_semantic_key(c2[0])[1] == (("operate", "S8_FO_F3_ORIG"),)


@pytest.mark.parametrize(
    ("legs", "updates", "violation"),
    [
        (((CrewSegmentType.OPERATE, "S8_FO_F3_ORIG"),), {}, "qualification_mismatch"),
        (
            (
                (CrewSegmentType.OPERATE, "S8_FO_F1_ORIG"),
                (CrewSegmentType.OPERATE, "S8_FO_F2_D10"),
            ),
            {},
            "min_connection_violation",
        ),
        (
            (
                (CrewSegmentType.OPERATE, "S8_FO_F2_ORIG"),
                (CrewSegmentType.OPERATE, "S8_FO_F1_ORIG"),
            ),
            {},
            "time_overlap",
        ),
        (
            (
                (CrewSegmentType.OPERATE, "S8_FO_F1_ORIG"),
                (CrewSegmentType.OPERATE, "S8_FO_F3_ORIG"),
            ),
            {},
            "station_discontinuity",
        ),
        (
            ((CrewSegmentType.OPERATE, "S8_FO_F1_ORIG"),),
            {},
            "last_leg_terminal_mismatch",
        ),
        (
            (
                (CrewSegmentType.OPERATE, "S8_FO_F2_ORIG"),
                (CrewSegmentType.OPERATE, "S8_FO_F2_D10"),
            ),
            {},
            "duplicate_base_flight",
        ),
        (
            (
                (CrewSegmentType.OPERATE, "S8_FO_F1_ORIG"),
                (CrewSegmentType.OPERATE, "S8_FO_F2_ORIG"),
            ),
            {"max_duty_minutes": 100},
            "duty_time_violation",
        ),
        (
            ((CrewSegmentType.DEADHEAD, "S8_FO_F1_ORIG"),),
            {"allow_deadhead": False},
            "deadhead_disabled",
        ),
        (
            (
                (CrewSegmentType.DEADHEAD, "S8_FO_F1_ORIG"),
                (CrewSegmentType.DEADHEAD, "S8_FO_F2_ORIG"),
            ),
            {},
            "deadhead_limit_violation",
        ),
        (
            ((CrewSegmentType.OPERATE, "S8_FO_F1_CANCEL"),),
            {},
            "not_revenue_operate_option",
        ),
        (
            ((CrewSegmentType.DEADHEAD, "S8_FO_FERRY_AB"),),
            {},
            "not_revenue_operate_option",
        ),
    ],
)
def test_independent_validator_rejects_illegal_pairings(
    phase6_case, legs, updates, violation
):
    scenario, columns = phase6_case
    candidate = _pairing(scenario.crew[0], *legs)
    audit = validate_generated_crew_pairing(
        scenario,
        columns.flight_options,
        scenario.crew[0],
        candidate,
        _config(**updates),
    )
    assert not audit.valid
    assert violation in audit.violations


def test_idle_pairing_and_deadhead_operating_semantics(phase6_case):
    scenario, columns = phase6_case
    c1_idle = _pairing(scenario.crew[0])
    c2_idle = _pairing(scenario.crew[1])
    assert validate_generated_crew_pairing(
        scenario, columns.flight_options, scenario.crew[0], c1_idle, _config()
    ).valid
    assert (
        "idle_terminal_mismatch"
        in validate_generated_crew_pairing(
            scenario, columns.flight_options, scenario.crew[1], c2_idle, _config()
        ).violations
    )

    deadhead = _pairing(scenario.crew[1], (CrewSegmentType.DEADHEAD, "S8_FO_F3_ORIG"))
    assert validate_generated_crew_pairing(
        scenario, columns.flight_options, scenario.crew[1], deadhead, _config()
    ).valid
    assert pairing_semantic_key(deadhead)[1] == (("deadhead", "S8_FO_F3_ORIG"),)


def test_validator_rejects_horizon_and_ownership_mismatch(phase6_case):
    scenario, columns = phase6_case
    crew = scenario.crew[0]
    candidate = _pairing(crew, (CrewSegmentType.OPERATE, "S8_FO_F1_ORIG"))
    candidate = candidate.model_copy(update={"crew_id": "OTHER"})
    options = list(columns.flight_options)
    options[0] = options[0].model_copy(
        update={"arr_time": scenario.recovery_window.end_time.replace(hour=13)}
    )
    audit = validate_generated_crew_pairing(
        scenario, options, crew, candidate, _config()
    )
    assert "crew_ownership_mismatch" in audit.violations
    assert "recovery_horizon_violation" in audit.violations
