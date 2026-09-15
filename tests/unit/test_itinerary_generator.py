from datetime import timedelta

import pytest

from backend.config import (
    ItineraryGenerationSource,
    PassengerItineraryGenerationConfig,
    PassengerItineraryGenerationConfigError,
    load_passenger_itinerary_generation_config,
)
from backend.core import (
    PassengerItineraryGenerationError,
    RecoveryScope,
    generate_passenger_itineraries,
    itinerary_semantic_key,
    replace_passenger_itineraries,
    validate_generated_passenger_itinerary,
)
from backend.schemas.columns import (
    PassengerItinerary,
    PassengerItineraryStatus,
    PassengerSegment,
    PassengerSegmentType,
    RecoveryColumns,
)
from backend.schemas.common import minutes_between
from backend.schemas.scenario import Scenario


def _config(**updates):
    data = {
        "schema_version": "1.0.0",
        "profile_id": "phase7_generator_unit",
        "default_mct_minutes": 30,
        "max_flight_legs": 2,
        "allow_unserved": True,
        "allow_surface": False,
        "source": ItineraryGenerationSource.TEST_FIXTURE,
        "notes": ("IMPLEMENTATION ASSUMPTION",),
    }
    data.update(updates)
    return PassengerItineraryGenerationConfig.model_validate(data)


@pytest.fixture
def phase7_case(
    toy_case_009_passenger_itinerary_generator_data,
    toy_case_009_passenger_itinerary_generator_columns_data,
):
    return (
        Scenario.model_validate(toy_case_009_passenger_itinerary_generator_data),
        RecoveryColumns.model_validate(
            toy_case_009_passenger_itinerary_generator_columns_data
        ),
    )


def _candidate(passenger, columns, *option_ids):
    options = {item.option_id: item for item in columns.flight_options}
    last = options[option_ids[-1]]
    delay = max(0, minutes_between(passenger.scheduled_arrival, last.arr_time))
    return PassengerItinerary(
        itinerary_id="TEST_PI",
        pax_group_id=passenger.pax_group_id,
        status=PassengerItineraryStatus.TRANSPORTED,
        segments=[
            PassengerSegment(
                segment_type=PassengerSegmentType.FLIGHT,
                flight_option_id=option_id,
                origin=None,
                destination=None,
                dep_time=None,
                arr_time=None,
            )
            for option_id in option_ids
        ],
        final_destination=passenger.destination,
        arrival_time=last.arr_time,
        arrival_delay_minutes=delay,
    )


def test_config_is_frozen_versioned_and_rejects_duplicate_keys(tmp_path):
    config = _config()
    with pytest.raises(Exception):
        config.max_flight_legs = 3
    path = tmp_path / "duplicate.json"
    path.write_text(
        '{"schema_version":"1.0.0","profile_id":"x","profile_id":"y"}',
        encoding="utf-8",
    )
    with pytest.raises(
        PassengerItineraryGenerationConfigError, match="duplicate JSON key"
    ):
        load_passenger_itinerary_generation_config(path)


def test_generator_is_deterministic_unique_and_emits_original_and_unserved(
    phase7_case,
):
    scenario, columns = phase7_case
    first = generate_passenger_itineraries(
        scenario, columns.flight_options, None, _config()
    )
    second = generate_passenger_itineraries(
        scenario, tuple(reversed(columns.flight_options)), None, _config()
    )
    assert [item.model_dump(mode="json") for item in first] == [
        item.model_dump(mode="json") for item in second
    ]
    keys = [itinerary_semantic_key(item) for item in first]
    assert len(keys) == len(set(keys))
    assert (
        "S9_P1",
        "transported",
        (("flight", "S9_FO_F2_ORIG"), ("flight", "S9_FO_F3_ORIG")),
    ) in keys
    assert ("S9_P1", "unserved", ()) in keys
    assert ("S9_P2", "unserved", ()) in keys


def test_arrival_delay_handles_early_and_delayed_arrival(phase7_case):
    scenario, columns = phase7_case
    generated = generate_passenger_itineraries(
        scenario, columns.flight_options, None, _config()
    )
    by_key = {itinerary_semantic_key(item): item for item in generated}
    early = by_key[("S9_P1", "transported", (("flight", "S9_FO_F1_ORIG"),))]
    delayed = by_key[
        (
            "S9_P1",
            "transported",
            (("flight", "S9_FO_F5_ORIG"), ("flight", "S9_FO_F6_ORIG")),
        )
    ]
    assert early.arrival_delay_minutes == 0
    assert delayed.arrival_delay_minutes == 20


def test_scope_keeps_only_original_for_out_of_scope_group(phase7_case):
    scenario, columns = phase7_case
    scope = RecoveryScope(
        direct_flight_ids=(),
        flight_ids=(),
        aircraft_ids=(),
        crew_ids=(),
        passenger_group_ids=("S9_P1",),
        flight_option_ids=(),
        aircraft_string_ids=(),
        crew_pairing_ids=(),
        passenger_itinerary_ids=(),
        propagation_reasons={},
        iteration_count=1,
    )
    generated = generate_passenger_itineraries(
        scenario, columns.flight_options, scope, _config()
    )
    p2 = [item for item in generated if item.pax_group_id == "S9_P2"]
    assert len(p2) == 1
    assert itinerary_semantic_key(p2[0])[2] == (
        ("flight", "S9_FO_F5_ORIG"),
        ("flight", "S9_FO_F6_ORIG"),
    )


@pytest.mark.parametrize(
    ("mutation", "violation"),
    [
        ("ownership", "passenger_ownership_mismatch"),
        ("unknown", "unknown_flight_option:UNKNOWN"),
        ("cancel", "not_revenue_operate_option"),
        ("ferry", "not_revenue_operate_option"),
        ("origin", "origin_mismatch"),
        ("destination", "destination_mismatch"),
        ("station", "station_discontinuity"),
        ("mct", "mct_violation"),
        ("duplicate_option", "duplicate_flight_option"),
        ("duplicate_base", "duplicate_base_flight"),
        ("max_legs", "max_flight_legs_exceeded"),
        ("arrival", "arrival_time_mismatch"),
        ("delay", "arrival_delay_mismatch"),
        ("surface", "surface_disabled"),
    ],
)
def test_independent_validator_rejects_core_illegalities(
    phase7_case, mutation, violation
):
    scenario, columns = phase7_case
    passenger = scenario.passengers[0]
    candidate = _candidate(passenger, columns, "S9_FO_F2_ORIG", "S9_FO_F3_ORIG")
    if mutation == "ownership":
        candidate = candidate.model_copy(update={"pax_group_id": "OTHER"})
    elif mutation in {"unknown", "cancel", "ferry"}:
        option_id = {
            "unknown": "UNKNOWN",
            "cancel": "S9_FO_F1_CANCEL",
            "ferry": "S9_FO_FERRY_AD",
        }[mutation]
        segment = candidate.segments[0].model_copy(
            update={"flight_option_id": option_id}
        )
        candidate = candidate.model_copy(update={"segments": [segment]})
    elif mutation == "origin":
        candidate = _candidate(passenger, columns, "S9_FO_F3_ORIG")
    elif mutation == "destination":
        candidate = _candidate(passenger, columns, "S9_FO_F2_ORIG")
    elif mutation == "station":
        candidate = _candidate(passenger, columns, "S9_FO_F2_ORIG", "S9_FO_F5_ORIG")
    elif mutation == "mct":
        candidate = _candidate(passenger, columns, "S9_FO_F2_ORIG", "S9_FO_F4_ORIG")
    elif mutation == "duplicate_option":
        candidate = _candidate(passenger, columns, "S9_FO_F2_ORIG", "S9_FO_F2_ORIG")
    elif mutation == "duplicate_base":
        candidate = _candidate(passenger, columns, "S9_FO_F2_ORIG", "S9_FO_F2_REROUTE")
    elif mutation == "max_legs":
        candidate = _candidate(
            passenger,
            columns,
            "S9_FO_F2_ORIG",
            "S9_FO_F3_ORIG",
            "S9_FO_F1_ORIG",
        )
    elif mutation == "arrival":
        candidate = candidate.model_copy(
            update={"arrival_time": candidate.arrival_time + timedelta(minutes=1)}
        )
    elif mutation == "delay":
        candidate = candidate.model_copy(update={"arrival_delay_minutes": 99})
    else:
        surface = PassengerSegment(
            segment_type=PassengerSegmentType.SURFACE,
            flight_option_id=None,
            origin="A",
            destination="D",
            dep_time=scenario.recovery_window.start_time,
            arr_time=scenario.recovery_window.start_time + timedelta(minutes=60),
        )
        candidate = candidate.model_copy(update={"segments": [surface]})

    audit = validate_generated_passenger_itinerary(
        scenario, columns.flight_options, passenger, candidate, _config()
    )
    assert not audit.valid
    assert violation in audit.violations


def test_validator_rejects_time_overlap_horizon_departure_and_unserved_shape(
    phase7_case,
):
    scenario, columns = phase7_case
    passenger = scenario.passengers[0]
    overlap = columns.flight_options[3].model_copy(
        update={
            "dep_time": columns.flight_options[1].arr_time - timedelta(minutes=1),
            "arr_time": columns.flight_options[1].arr_time + timedelta(minutes=59),
        }
    )
    overlap_columns = columns.model_copy(
        update={
            "flight_options": [
                *columns.flight_options[:3],
                overlap,
                *columns.flight_options[4:],
            ]
        }
    )
    candidate = _candidate(passenger, overlap_columns, "S9_FO_F2_ORIG", "S9_FO_F4_ORIG")
    audit = validate_generated_passenger_itinerary(
        scenario, overlap_columns.flight_options, passenger, candidate, _config()
    )
    assert "time_overlap" in audit.violations

    outside = columns.flight_options[0].model_copy(
        update={"arr_time": scenario.recovery_window.end_time + timedelta(minutes=1)}
    )
    outside_columns = columns.model_copy(
        update={"flight_options": [outside, *columns.flight_options[1:]]}
    )
    candidate = _candidate(passenger, outside_columns, "S9_FO_F1_ORIG")
    audit = validate_generated_passenger_itinerary(
        scenario, outside_columns.flight_options, passenger, candidate, _config()
    )
    assert "outside_recovery_horizon" in audit.violations

    late_ready = passenger.model_copy(
        update={
            "original_departure": columns.flight_options[0].dep_time
            + timedelta(minutes=1)
        }
    )
    candidate = _candidate(late_ready, columns, "S9_FO_F1_ORIG")
    assert (
        "departure_before_passenger_ready"
        in validate_generated_passenger_itinerary(
            scenario, columns.flight_options, late_ready, candidate, _config()
        ).violations
    )

    unserved = PassengerItinerary(
        itinerary_id="TEST_UNSERVED",
        pax_group_id=passenger.pax_group_id,
        status=PassengerItineraryStatus.UNSERVED,
        segments=[],
        final_destination=None,
        arrival_time=None,
        arrival_delay_minutes=None,
    ).model_copy(update={"arrival_delay_minutes": 1})
    assert (
        "unserved_shape_violation"
        in validate_generated_passenger_itinerary(
            scenario, columns.flight_options, passenger, unserved, _config()
        ).violations
    )


def test_max_leg_no_path_error_capacity_independence_and_replacement(phase7_case):
    scenario, columns = phase7_case
    large_group = scenario.passengers[0].model_copy(update={"count": 999999})
    large_scenario = scenario.model_copy(
        update={"passengers": [large_group, scenario.passengers[1]]}
    )
    normal = generate_passenger_itineraries(
        scenario, columns.flight_options, None, _config()
    )
    large = generate_passenger_itineraries(
        large_scenario, columns.flight_options, None, _config()
    )
    assert [itinerary_semantic_key(item) for item in normal] == [
        itinerary_semantic_key(item) for item in large
    ]
    replaced = replace_passenger_itineraries(columns, normal)
    assert replaced.flight_options == columns.flight_options
    assert tuple(replaced.passenger_itineraries) == normal

    stranded = scenario.passengers[0].model_copy(
        update={"origin": "E", "destination": "E"}
    )
    stranded_scenario = scenario.model_copy(update={"passengers": [stranded]})
    generated = generate_passenger_itineraries(
        stranded_scenario, columns.flight_options, None, _config()
    )
    assert len(generated) == 1
    assert generated[0].status is PassengerItineraryStatus.UNSERVED
    with pytest.raises(
        PassengerItineraryGenerationError, match="has no legal candidate"
    ):
        generate_passenger_itineraries(
            stranded_scenario,
            columns.flight_options,
            None,
            _config(allow_unserved=False),
        )
