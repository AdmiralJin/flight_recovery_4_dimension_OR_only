from copy import deepcopy
from dataclasses import replace

import pytest

from backend.core import (
    ScopeBuildError,
    build_recovery_scope,
    direct_disrupted_flight_ids,
    resolve_original_candidates,
    scope_metrics,
    validate_recovery_scope,
)
from backend.schemas.columns import RecoveryColumns
from backend.schemas.scenario import Scenario


def _validated(data, columns):
    return Scenario.model_validate(data), RecoveryColumns.model_validate(columns)


def test_direct_departure_seed_uses_half_open_interval(
    toy_case_006_scope_data, toy_case_006_scope_columns_data
):
    scenario, _ = _validated(
        toy_case_006_scope_data, toy_case_006_scope_columns_data
    )
    assert direct_disrupted_flight_ids(scenario) == ("S6_F1",)

    at_end = deepcopy(toy_case_006_scope_data)
    at_end["flights"][0]["sched_dep"] = "2026-01-15T08:10:00Z"
    at_end["flights"][0]["sched_arr"] = "2026-01-15T09:10:00Z"
    assert direct_disrupted_flight_ids(Scenario.model_validate(at_end)) == ()


def test_multiple_disruptions_are_unioned_in_scenario_order(
    toy_case_006_scope_data, toy_case_006_scope_columns_data
):
    data = deepcopy(toy_case_006_scope_data)
    data["disruptions"].append(
        {
            "airport": "D",
            "start_time": "2026-01-15T08:20:00Z",
            "end_time": "2026-01-15T08:40:00Z",
            "capacity_change": -1,
            "restriction_type": "departure_capacity_reduction",
        }
    )
    scenario, _ = _validated(data, toy_case_006_scope_columns_data)
    assert direct_disrupted_flight_ids(scenario) == ("S6_F1", "S6_U1")


def test_fixed_point_propagates_flight_to_all_owners_and_downstream_flight(
    toy_case_006_scope_data, toy_case_006_scope_columns_data
):
    scenario, columns = _validated(
        toy_case_006_scope_data, toy_case_006_scope_columns_data
    )
    scope = build_recovery_scope(scenario, columns)

    assert scope.direct_flight_ids == ("S6_F1",)
    assert scope.flight_ids == ("S6_F1", "S6_F2")
    assert scope.aircraft_ids == ("S6_AC1",)
    assert scope.crew_ids == ("S6_C1",)
    assert scope.passenger_group_ids == ("S6_P1",)
    assert scope.iteration_count == 2
    assert any(
        reason.startswith("CANDIDATE_STRING:")
        for reason in scope.propagation_reasons["S6_F2"]
    )
    assert any(
        reason.startswith("CANDIDATE_PAIRING:")
        for reason in scope.propagation_reasons["S6_F2"]
    )
    assert any(
        reason.startswith("CANDIDATE_ITINERARY:")
        for reason in scope.propagation_reasons["S6_F2"]
    )


def test_scope_is_deterministic_stably_ordered_and_immutable(
    toy_case_006_scope_data, toy_case_006_scope_columns_data
):
    scenario, columns = _validated(
        toy_case_006_scope_data, toy_case_006_scope_columns_data
    )
    first = build_recovery_scope(scenario, columns)
    second = build_recovery_scope(scenario, columns)
    assert first == second
    assert tuple(first.propagation_reasons) == tuple(
        sorted(first.propagation_reasons)
    )
    with pytest.raises(TypeError):
        first.propagation_reasons["S6_F1"] = ("changed",)  # type: ignore[index]


def test_unsupported_restriction_type_fails_explicitly(
    toy_case_006_scope_data, toy_case_006_scope_columns_data
):
    data = deepcopy(toy_case_006_scope_data)
    data["disruptions"][0]["restriction_type"] = "wind_restriction"
    scenario, columns = _validated(data, toy_case_006_scope_columns_data)
    with pytest.raises(ScopeBuildError, match="unsupported.*wind_restriction"):
        build_recovery_scope(scenario, columns)


def test_shared_capacity_row_adds_other_base_flight(
    toy_case_006_scope_data, toy_case_006_scope_columns_data
):
    data = deepcopy(toy_case_006_scope_data)
    columns_data = deepcopy(toy_case_006_scope_columns_data)
    data["flights"][2].update(
        {"origin": "A", "original_aircraft": "S6_AC2", "original_crew": "S6_C2"}
    )
    data["aircraft"][1]["initial_station_at_t"] = "A"
    data["crew"][1]["start_station_at_t"] = "A"
    data["passengers"][1].update(
        {"origin": "A", "original_departure": "2026-01-15T08:30:00Z"}
    )
    columns_data["flight_options"][4]["origin"] = "A"
    columns_data["aircraft_strings"][2]["start_station"] = "A"
    columns_data["crew_pairings"][2]["start_station"] = "A"
    scenario, columns = _validated(data, columns_data)

    scope = build_recovery_scope(scenario, columns)
    assert "S6_U1" in scope.flight_ids
    assert any(
        reason.startswith("SHARED_DEPARTURE_CAPACITY:")
        for reason in scope.propagation_reasons["S6_U1"]
    )


def test_shared_gate_checkpoint_adds_flight_from_another_capacity_row(
    toy_case_006_scope_data, toy_case_006_scope_columns_data
):
    data = deepcopy(toy_case_006_scope_data)
    columns_data = deepcopy(toy_case_006_scope_columns_data)
    data["flights"][2].update(
        {
            "origin": "A",
            "sched_dep": "2026-01-15T10:00:00Z",
            "sched_arr": "2026-01-15T11:00:00Z",
        }
    )
    data["aircraft"][1]["initial_station_at_t"] = "A"
    data["crew"][1]["start_station_at_t"] = "A"
    data["passengers"][1].update(
        {
            "origin": "A",
            "original_departure": "2026-01-15T10:00:00Z",
            "scheduled_arrival": "2026-01-15T11:00:00Z",
        }
    )
    data["airport_intervals"][1]["end_time"] = "2026-01-15T09:00:00Z"
    data["airport_intervals"].insert(
        2,
        {
            "airport": "A",
            "start_time": "2026-01-15T09:00:00Z",
            "end_time": "2026-01-15T12:00:00Z",
            "arr_capacity": 10,
            "dep_capacity": 10,
            "gate_capacity": 10,
            "curfew_flag": False,
            "weather_restrictions": [],
        },
    )
    columns_data["flight_options"][4].update(
        {
            "origin": "A",
            "dep_time": "2026-01-15T10:00:00Z",
            "arr_time": "2026-01-15T11:00:00Z",
        }
    )
    columns_data["aircraft_strings"][2]["start_station"] = "A"
    columns_data["crew_pairings"][2]["start_station"] = "A"
    columns_data["passenger_itineraries"][2].update(
        {
            "arrival_time": "2026-01-15T11:00:00Z",
            "arrival_delay_minutes": 0,
        }
    )
    scenario, columns = _validated(data, columns_data)

    scope = build_recovery_scope(scenario, columns)
    assert "S6_U1" in scope.flight_ids
    assert any(
        reason.startswith("SHARED_GATE_CHECKPOINT:")
        for reason in scope.propagation_reasons["S6_U1"]
    )
    assert not any(
        reason.startswith("SHARED_DEPARTURE_CAPACITY:")
        for reason in scope.propagation_reasons["S6_U1"]
    )


def test_deadhead_reference_scopes_crew_and_crew_candidate_flight(
    toy_case_006_scope_data, toy_case_006_scope_columns_data
):
    columns_data = deepcopy(toy_case_006_scope_columns_data)
    columns_data["crew_pairings"][2]["duties"][0]["segments"].append(
        {
            "segment_type": "deadhead",
            "flight_option_id": "S6_D2",
            "origin": None,
            "destination": None,
            "start_time": None,
            "end_time": None,
            "notes": "Scope propagation test only.",
        }
    )
    scenario, columns = _validated(toy_case_006_scope_data, columns_data)

    scope = build_recovery_scope(scenario, columns)
    assert "S6_C2" in scope.crew_ids
    assert "S6_U1" in scope.flight_ids
    assert any(
        "S6_CP2O" in reason
        for reason in scope.propagation_reasons["S6_C2"]
    )
    assert any(
        reason.startswith("CANDIDATE_PAIRING:S6_CP2O:S6_UO1")
        for reason in scope.propagation_reasons["S6_U1"]
    )


def test_shared_seat_option_adds_competing_passenger_group(
    toy_case_006_scope_data, toy_case_006_scope_columns_data
):
    columns_data = deepcopy(toy_case_006_scope_columns_data)
    alternative = deepcopy(columns_data["passenger_itineraries"][2])
    alternative.update(
        {
            "itinerary_id": "S6_PI2_ALT",
            "segments": [
                {
                    "segment_type": "flight",
                    "flight_option_id": "S6_D2",
                    "origin": None,
                    "destination": None,
                    "dep_time": None,
                    "arr_time": None,
                }
            ],
            "final_destination": "C",
            "arrival_time": "2026-01-15T10:50:00Z",
            "arrival_delay_minutes": 80,
        }
    )
    columns_data["passenger_itineraries"].append(alternative)
    scenario, columns = _validated(toy_case_006_scope_data, columns_data)

    scope = build_recovery_scope(scenario, columns)
    assert "S6_P2" in scope.passenger_group_ids
    assert any(
        reason.startswith("SHARED_SEAT_CAPACITY:S6_D2")
        for reason in scope.propagation_reasons["S6_P2"]
    )


def test_semantic_original_resolver_does_not_depend_on_candidate_names(
    toy_case_006_scope_data, toy_case_006_scope_columns_data
):
    scenario, columns = _validated(
        toy_case_006_scope_data, toy_case_006_scope_columns_data
    )
    originals = resolve_original_candidates(scenario, columns)
    assert originals.flight_option_by_flight["S6_F1"] == "S6_O1"
    assert originals.aircraft_string_by_aircraft["S6_AC1"] == "S6_AS1O"
    assert originals.crew_pairing_by_crew["S6_C1"] == "S6_CP1O"
    assert originals.passenger_itinerary_by_group["S6_P1"] == "S6_PI1O"


def test_semantic_original_resolver_rejects_nonunique_match(
    toy_case_006_scope_data, toy_case_006_scope_columns_data
):
    columns_data = deepcopy(toy_case_006_scope_columns_data)
    duplicate = deepcopy(columns_data["flight_options"][0])
    duplicate["option_id"] = "S6_DUPLICATE_SEMANTIC_ORIGINAL"
    columns_data["flight_options"].append(duplicate)
    scenario, columns = _validated(toy_case_006_scope_data, columns_data)
    with pytest.raises(ScopeBuildError, match="must be unique"):
        resolve_original_candidates(scenario, columns)


def test_validate_scope_rejects_broken_closure(
    toy_case_006_scope_data, toy_case_006_scope_columns_data
):
    scenario, columns = _validated(
        toy_case_006_scope_data, toy_case_006_scope_columns_data
    )
    scope = build_recovery_scope(scenario, columns)
    broken = replace(scope, flight_ids=("S6_F1",))
    with pytest.raises(ScopeBuildError, match="closure"):
        validate_recovery_scope(scenario, columns, broken)


def test_scope_metrics_show_real_reduction(
    toy_case_006_scope_data, toy_case_006_scope_columns_data
):
    scenario, columns = _validated(
        toy_case_006_scope_data, toy_case_006_scope_columns_data
    )
    metrics = scope_metrics(
        scenario, columns, build_recovery_scope(scenario, columns)
    )
    assert metrics["scoped_flights"] == 2
    assert metrics["total_flights"] == 3
    assert metrics["free_binary_candidates"] < metrics["total_binary_candidates"]
    assert metrics["free_binary_ratio"] == pytest.approx(10 / 14)


def test_phase1_benchmark_safely_closes_to_full_scope(
    phase1_benchmark_001_data, phase1_columns_001_data
):
    scenario, columns = _validated(
        phase1_benchmark_001_data, phase1_columns_001_data
    )
    scope = build_recovery_scope(scenario, columns)
    assert scope.direct_flight_ids == ("F2", "F5", "F8")
    assert scope.flight_ids == tuple(item.flight_id for item in scenario.flights)
    assert scope.aircraft_ids == tuple(item.tail_id for item in scenario.aircraft)
    assert scope.crew_ids == tuple(item.crew_id for item in scenario.crew)
    assert scope.passenger_group_ids == tuple(
        item.pax_group_id for item in scenario.passengers
    )
