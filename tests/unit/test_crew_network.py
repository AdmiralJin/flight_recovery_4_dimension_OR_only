from backend.config import CrewPairingGenerationConfig, PairingGenerationSource
from backend.core import CrewLegKey, build_crew_flight_network
from backend.schemas.columns import CrewSegmentType, RecoveryColumns
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


def test_crew_network_enforces_leg_eligibility_and_connection(
    toy_case_008_crew_pairing_generator_data,
    toy_case_008_crew_pairing_generator_columns_data,
):
    scenario = Scenario.model_validate(toy_case_008_crew_pairing_generator_data)
    columns = RecoveryColumns.model_validate(
        toy_case_008_crew_pairing_generator_columns_data
    )
    network = build_crew_flight_network(
        scenario, columns.flight_options, scenario.crew[0], _config()
    )
    op_f1 = CrewLegKey(CrewSegmentType.OPERATE, "S8_FO_F1_ORIG")
    op_f2 = CrewLegKey(CrewSegmentType.OPERATE, "S8_FO_F2_ORIG")
    op_f2_tight = CrewLegKey(CrewSegmentType.OPERATE, "S8_FO_F2_D10")
    op_f3 = CrewLegKey(CrewSegmentType.OPERATE, "S8_FO_F3_ORIG")
    dh_f3 = CrewLegKey(CrewSegmentType.DEADHEAD, "S8_FO_F3_ORIG")

    assert op_f1 in network.start_leg_keys
    assert op_f2 in network.successor_leg_keys[op_f1]
    assert op_f2_tight not in network.successor_leg_keys[op_f1]
    assert network.rejected_leg_reasons[op_f3] == ("qualification_mismatch",)
    assert dh_f3 in network.leg_keys
    assert network.node_count == len(network.leg_keys) + 2
    assert network.rejected_edge_counts["min_connection_violation"] > 0


def test_crew_network_rejects_cancel_ferry_and_disabled_deadhead(
    toy_case_008_crew_pairing_generator_data,
    toy_case_008_crew_pairing_generator_columns_data,
):
    scenario = Scenario.model_validate(toy_case_008_crew_pairing_generator_data)
    columns = RecoveryColumns.model_validate(
        toy_case_008_crew_pairing_generator_columns_data
    )
    network = build_crew_flight_network(
        scenario,
        columns.flight_options,
        scenario.crew[0],
        _config(allow_deadhead=False),
    )
    assert network.rejected_leg_reasons[
        CrewLegKey(CrewSegmentType.DEADHEAD, "S8_FO_F1_ORIG")
    ] == ("deadhead_disabled",)
    assert (
        "not_revenue_operate_option"
        in network.rejected_leg_reasons[
            CrewLegKey(CrewSegmentType.OPERATE, "S8_FO_F1_CANCEL")
        ]
    )
    assert (
        "not_revenue_operate_option"
        in network.rejected_leg_reasons[
            CrewLegKey(CrewSegmentType.DEADHEAD, "S8_FO_FERRY_AB")
        ]
    )
