from backend.config import (
    ItineraryGenerationSource,
    PassengerItineraryGenerationConfig,
)
from backend.core import build_passenger_flight_network
from backend.schemas.columns import RecoveryColumns
from backend.schemas.scenario import Scenario


def _config():
    return PassengerItineraryGenerationConfig(
        schema_version="1.0.0",
        profile_id="phase7_network_unit",
        default_mct_minutes=30,
        max_flight_legs=2,
        allow_unserved=True,
        allow_surface=False,
        source=ItineraryGenerationSource.TEST_FIXTURE,
        notes=("IMPLEMENTATION ASSUMPTION",),
    )


def test_network_enforces_option_start_terminal_and_edge_rules(
    toy_case_009_passenger_itinerary_generator_data,
    toy_case_009_passenger_itinerary_generator_columns_data,
):
    scenario = Scenario.model_validate(toy_case_009_passenger_itinerary_generator_data)
    columns = RecoveryColumns.model_validate(
        toy_case_009_passenger_itinerary_generator_columns_data
    )
    network = build_passenger_flight_network(
        scenario, columns.flight_options, scenario.passengers[0], _config()
    )

    assert "S9_FO_F2_ORIG" in network.start_option_ids
    assert "S9_FO_F3_ORIG" not in network.start_option_ids
    assert "S9_FO_F1_ORIG" in network.terminal_option_ids
    assert "S9_FO_F3_ORIG" in network.successor_option_ids["S9_FO_F2_ORIG"]
    assert "S9_FO_F4_ORIG" not in network.successor_option_ids["S9_FO_F2_ORIG"]
    assert "S9_FO_F2_REROUTE" not in network.successor_option_ids["S9_FO_F2_ORIG"]
    assert network.rejected_edge_counts["mct_violation"] > 0
    assert network.rejected_edge_counts["same_base_flight"] > 0
    assert network.rejected_option_reasons["S9_FO_F1_CANCEL"] == (
        "not_revenue_operate_option",
    )
    assert network.rejected_option_reasons["S9_FO_FERRY_AD"] == (
        "not_revenue_operate_option",
    )


def test_network_is_deterministic_under_reversed_input_and_rejects_horizon(
    toy_case_009_passenger_itinerary_generator_data,
    toy_case_009_passenger_itinerary_generator_columns_data,
):
    scenario = Scenario.model_validate(toy_case_009_passenger_itinerary_generator_data)
    columns = RecoveryColumns.model_validate(
        toy_case_009_passenger_itinerary_generator_columns_data
    )
    passenger = scenario.passengers[0]
    first = build_passenger_flight_network(
        scenario, columns.flight_options, passenger, _config()
    )
    second = build_passenger_flight_network(
        scenario, tuple(reversed(columns.flight_options)), passenger, _config()
    )
    assert first == second

    outside = columns.flight_options[0].model_copy(
        update={
            "option_id": "S9_OUTSIDE",
            "arr_time": scenario.recovery_window.end_time.replace(hour=13),
        }
    )
    network = build_passenger_flight_network(
        scenario, (*columns.flight_options, outside), passenger, _config()
    )
    assert "outside_recovery_horizon" in network.rejected_option_reasons["S9_OUTSIDE"]
