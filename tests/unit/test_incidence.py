from dataclasses import FrozenInstanceError

import pytest

from backend.core.incidence import BinaryIncidence, build_recovery_incidence
from backend.core.indices import build_recovery_indices
from backend.schemas.columns import CrewSegmentType
from backend.services.column_validator import validate_recovery_columns
from backend.services.validator import validate_scenario


@pytest.fixture
def validated_inputs(phase1_benchmark_001_data, phase1_columns_001_data):
    scenario, scenario_issues = validate_scenario(phase1_benchmark_001_data)
    assert scenario is not None and scenario_issues == []
    columns, column_issues = validate_recovery_columns(
        scenario, phase1_columns_001_data
    )
    assert columns is not None and column_issues == []
    return scenario, columns


def _by_id(items, attr, value):
    return next(item for item in items if getattr(item, attr) == value)


def test_binary_incidence_supports_stable_bidirectional_queries():
    incidence = BinaryIncidence(
        rows=("r2", "r1"),
        columns=("c2", "c1", "c3"),
        edges=(("r1", "c1"), ("r1", "c2"), ("r2", "c3")),
    )

    assert incidence.contains("r1", "c2")
    assert not incidence.contains("r2", "c1")
    assert incidence.columns_for_row("r1") == ("c2", "c1")
    assert incidence.rows_for_column("c3") == ("r2",)


def test_binary_incidence_rejects_duplicate_edges_and_unknown_dimensions():
    with pytest.raises(ValueError, match="duplicate incidence edge"):
        BinaryIncidence(("r",), ("c",), (("r", "c"), ("r", "c")))
    with pytest.raises(KeyError, match="unknown incidence row"):
        BinaryIncidence(("r",), ("c",), (("missing", "c"),))
    with pytest.raises(KeyError, match="unknown incidence column"):
        BinaryIncidence(("r",), ("c",), (("r", "missing"),))

    incidence = BinaryIncidence(("r",), ("c",))
    with pytest.raises(KeyError, match="unknown incidence row"):
        incidence.columns_for_row("missing")
    with pytest.raises(KeyError, match="unknown incidence column"):
        incidence.rows_for_column("missing")


def test_binary_incidence_is_immutable():
    incidence = BinaryIncidence(("r",), ("c",), (("r", "c"),))

    with pytest.raises(TypeError):
        incidence.row_to_columns["r"] = frozenset()  # type: ignore[index]
    with pytest.raises(AttributeError):
        incidence.row_to_columns["r"].add("other")  # type: ignore[attr-defined]
    with pytest.raises(FrozenInstanceError):
        incidence.rows = ()  # type: ignore[misc]


def test_builder_constructs_all_entity_choice_relations(validated_inputs):
    scenario, columns = validated_inputs
    incidence = build_recovery_incidence(scenario, columns)

    assert incidence.base_flight_to_options.contains("F2", "FO_F2_D50")
    assert incidence.aircraft_to_strings.contains("AC1", "AS_AC1_SWAP_F10")
    assert incidence.crew_to_pairings.contains("C1", "CP_C1_RECOVERY")
    assert incidence.passenger_group_to_itineraries.contains(
        "P4", "PI_P4_REACCOM_F8"
    )


def test_builder_constructs_operational_and_maintenance_relations(validated_inputs):
    scenario, columns = validated_inputs
    incidence = build_recovery_incidence(scenario, columns)

    assert incidence.option_to_aircraft_strings.contains(
        "FO_F2_D50", "AS_AC1_SWAP_F10"
    )
    assert incidence.option_to_operating_pairings.contains(
        "FO_F2_D50", "CP_C1_RECOVERY"
    )
    assert incidence.option_to_passenger_itineraries.contains(
        "FO_F8_ORIG", "PI_P4_REACCOM_F8"
    )
    assert incidence.maintenance_to_strings.contains(
        "AC4", "AS_AC4_SWAP_F3_ORIG"
    )


def test_deadhead_is_separate_from_operating_coverage(validated_inputs):
    scenario, columns = validated_inputs
    pairing = _by_id(columns.crew_pairings, "pairing_id", "CP_C1_RECOVERY")
    pairing.duties[0].segments[0].segment_type = CrewSegmentType.DEADHEAD

    incidence = build_recovery_incidence(scenario, columns)

    assert incidence.option_to_deadhead_pairings.contains(
        "FO_F1_ORIG", "CP_C1_RECOVERY"
    )
    assert not incidence.option_to_operating_pairings.contains(
        "FO_F1_ORIG", "CP_C1_RECOVERY"
    )


def test_ferry_uses_aircraft_and_movement_capacity_but_has_no_base_flight(
    validated_inputs,
):
    scenario, columns = validated_inputs
    incidence = build_recovery_incidence(scenario, columns)
    ferry_id = "FO_FERRY_CA_1140"
    c_interval = next(
        key for key in incidence.departure_capacity_to_options.rows if key.airport == "C"
    )
    a_interval = next(
        key for key in incidence.arrival_capacity_to_options.rows if key.airport == "A"
    )

    assert all(
        ferry_id not in incidence.base_flight_to_options.columns_for_row(flight_id)
        for flight_id in incidence.base_flight_to_options.rows
    )
    assert incidence.option_to_aircraft_strings.rows_for_column(
        "AS_AC1_CANCEL_F3_FERRY"
    ) == ("FO_F1_ORIG", "FO_F2_D50", ferry_id)
    assert incidence.departure_capacity_to_options.contains(c_interval, ferry_id)
    assert incidence.arrival_capacity_to_options.contains(a_interval, ferry_id)


def test_cancel_is_excluded_from_physical_and_movement_coverage(validated_inputs):
    scenario, columns = validated_inputs
    incidence = build_recovery_incidence(scenario, columns)
    cancel_id = "FO_F3_CANCEL"

    assert incidence.base_flight_to_options.contains("F3", cancel_id)
    assert incidence.option_to_aircraft_strings.columns_for_row(cancel_id) == ()
    assert incidence.option_to_operating_pairings.columns_for_row(cancel_id) == ()
    assert incidence.option_to_deadhead_pairings.columns_for_row(cancel_id) == ()
    assert all(
        cancel_id not in incidence.departure_capacity_to_options.columns_for_row(key)
        for key in incidence.departure_capacity_to_options.rows
    )
    assert all(
        cancel_id not in incidence.arrival_capacity_to_options.columns_for_row(key)
        for key in incidence.arrival_capacity_to_options.rows
    )


def test_capacity_intervals_use_half_open_boundaries(validated_inputs):
    scenario, columns = validated_inputs
    incidence = build_recovery_incidence(scenario, columns)
    b_interval = next(
        key
        for key in incidence.departure_capacity_to_options.rows
        if key.airport == "B"
    )

    assert incidence.departure_capacity_to_options.contains(
        b_interval, "FO_F5_ORIG"
    )
    assert incidence.departure_capacity_to_options.contains(
        b_interval, "FO_F8_ORIG"
    )
    assert not incidence.departure_capacity_to_options.contains(
        b_interval, "FO_F2_D50"
    )


def test_arrival_capacity_excludes_the_interval_end_boundary(validated_inputs):
    scenario, columns = validated_inputs
    a_interval = next(
        interval for interval in scenario.airport_intervals if interval.airport == "A"
    )
    ferry = _by_id(columns.flight_options, "option_id", "FO_FERRY_CA_1140")
    ferry.arr_time = a_interval.end_time

    incidence = build_recovery_incidence(scenario, columns)
    a_key = next(
        key for key in incidence.arrival_capacity_to_options.rows if key.airport == "A"
    )

    assert not incidence.arrival_capacity_to_options.contains(
        a_key, ferry.option_id
    )


@pytest.mark.parametrize("bad_option_id", ["UNKNOWN", "FO_F3_CANCEL"])
def test_aircraft_string_rejects_unknown_and_cancel_options(
    validated_inputs, bad_option_id
):
    scenario, columns = validated_inputs
    string = _by_id(columns.aircraft_strings, "string_id", "AS_AC1_ORIGINAL")
    string.leg_option_ids[0] = bad_option_id

    with pytest.raises(ValueError, match="unknown option|cancel option"):
        build_recovery_incidence(scenario, columns)


def test_passenger_itinerary_rejects_ferry_option(validated_inputs):
    scenario, columns = validated_inputs
    itinerary = _by_id(
        columns.passenger_itineraries, "itinerary_id", "PI_P4_REACCOM_F8"
    )
    itinerary.segments[0].flight_option_id = "FO_FERRY_CA_1140"

    with pytest.raises(ValueError, match="cannot use ferry option"):
        build_recovery_incidence(scenario, columns)


def test_builder_does_not_silently_collapse_duplicate_edges(validated_inputs):
    scenario, columns = validated_inputs
    string = _by_id(columns.aircraft_strings, "string_id", "AS_AC1_ORIGINAL")
    string.leg_option_ids.append(string.leg_option_ids[0])

    with pytest.raises(ValueError, match="duplicate incidence edge"):
        build_recovery_incidence(scenario, columns)


def test_builder_rejects_indices_from_different_inputs(validated_inputs):
    scenario, columns = validated_inputs
    indices = build_recovery_indices(scenario, columns)
    columns.flight_options.reverse()

    with pytest.raises(ValueError, match="indices do not match"):
        build_recovery_incidence(scenario, columns, indices)
