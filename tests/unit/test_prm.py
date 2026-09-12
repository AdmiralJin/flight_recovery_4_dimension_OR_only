from copy import deepcopy
from pathlib import Path

import pytest

from backend.config import (
    PassengerCapacityProfile,
    load_cost_config,
    load_passenger_capacity_profile,
    passenger_itinerary_cost,
)
from backend.core import (
    PassengerRecoveryRequest,
    PrmBuildError,
    build_fixed_column_prm,
    recompute_prm_diagnostics,
    solve_fixed_column_prm,
)
from backend.schemas.columns import PassengerItinerary
from backend.services.column_validator import validate_recovery_columns
from backend.services.validator import validate_scenario
from backend.solver import GurobiAdapter, SolverStatus


ROOT = Path(__file__).parents[2]
COSTS = load_cost_config(ROOT / "data" / "costs" / "phase2_test_costs_v1.json")
TOY_CAPACITY_PATH = ROOT / "data" / "capacities" / "toy_case_003_capacity.json"
BENCHMARK_CAPACITY_PATH = (
    ROOT / "data" / "capacities" / "phase2_test_seat_capacity_v1.json"
)


def _profile_with(profile, **capacity_updates):
    data = profile.model_dump(mode="python")
    data["seat_capacity_by_option_id"] = dict(data["seat_capacity_by_option_id"])
    data["seat_capacity_by_option_id"].update(capacity_updates)
    return PassengerCapacityProfile.model_validate(data)


def _request(scenario_data, profile, option_ids=None):
    return PassengerRecoveryRequest(
        scenario_data["scenario_id"],
        tuple(option_ids or profile.seat_capacity_by_option_id),
        profile.capacity_profile_id,
    )


def _solve(scenario_data, columns_data, profile, option_ids=None):
    with GurobiAdapter(output_flag=False) as solver:
        return solve_fixed_column_prm(
            scenario_data,
            columns_data,
            _request(scenario_data, profile, option_ids),
            profile,
            COSTS,
            solver,
            solver_parameters={"DualReductions": 0},
        )


def test_passenger_itinerary_cost_uses_passenger_minutes_and_passenger_count(
    toy_case_003_columns_data,
):
    transported = PassengerItinerary.model_validate(
        toy_case_003_columns_data["passenger_itineraries"][4]
    )
    unserved = PassengerItinerary.model_validate(
        toy_case_003_columns_data["passenger_itineraries"][5]
    )

    delay = passenger_itinerary_cost(10, transported, COSTS)
    spill = passenger_itinerary_cost(10, unserved, COSTS)

    assert delay.weighted_passenger_delay_minutes == 300
    assert delay.delay_cost == pytest.approx(3000.0)
    assert delay.unserved_cost == 0.0
    assert spill.unserved_passengers == 10
    assert spill.unserved_cost == pytest.approx(25000.0)
    assert spill.delay_cost == 0.0
    with pytest.raises(ValueError, match="positive integer"):
        passenger_itinerary_cost(1.5, transported, COSTS)  # type: ignore[arg-type]


def test_prm_selects_exactly_one_and_uses_passenger_counts_for_capacity(
    toy_case_003_data, toy_case_003_columns_data
):
    profile = load_passenger_capacity_profile(TOY_CAPACITY_PATH)
    result = _solve(toy_case_003_data, toy_case_003_columns_data, profile)

    assert result.status is SolverStatus.OPTIMAL
    assert result.objective_value == pytest.approx(3000.0)
    diagnostics = result.diagnostics
    assert diagnostics["selected_itinerary_by_group"] == {
        "T3_P1": "PI_T3_P1_DIRECT",
        "T3_P2": "PI_T3_P2_ALT",
    }
    assert diagnostics["flight_seat_load"] == {
        "FO_T3_F1_ORIG": 12.0,
        "FO_T3_F2_ORIG": 10.0,
        "FO_T3_F3_ORIG": 10.0,
    }
    assert diagnostics["flight_seat_slack"]["FO_T3_F1_ORIG"] == 0.0
    assert diagnostics["all_constraints_satisfied"]
    assert all(
        item["lhs"] == pytest.approx(1.0)
        for item in diagnostics["group_selection_constraints"]
    )


def test_capacity_shortage_selects_explicit_unserved_itinerary(
    toy_case_003_data, toy_case_003_columns_data
):
    profile = _profile_with(
        load_passenger_capacity_profile(TOY_CAPACITY_PATH),
        FO_T3_F2_ORIG=0,
        FO_T3_F3_ORIG=0,
    )
    result = _solve(toy_case_003_data, toy_case_003_columns_data, profile)

    assert result.status is SolverStatus.OPTIMAL
    assert result.diagnostics["selected_itinerary_by_group"] == {
        "T3_P1": "PI_T3_P1_DIRECT",
        "T3_P2": "PI_T3_P2_UNSERVED",
    }
    assert result.diagnostics["unserved_passengers"] == 10
    assert result.objective_value == pytest.approx(25000.0)


def test_surface_segment_does_not_consume_flight_capacity(
    toy_case_003_data, toy_case_003_columns_data
):
    columns = deepcopy(toy_case_003_columns_data)
    alt = next(
        item
        for item in columns["passenger_itineraries"]
        if item["itinerary_id"] == "PI_T3_P2_ALT"
    )
    alt["segments"][0] = {
        "segment_type": "surface",
        "flight_option_id": None,
        "origin": "A",
        "destination": "B",
        "dep_time": "2026-01-15T08:15:00Z",
        "arr_time": "2026-01-15T09:15:00Z",
    }
    profile = _profile_with(
        load_passenger_capacity_profile(TOY_CAPACITY_PATH),
        FO_T3_F2_ORIG=0,
    )
    result = _solve(toy_case_003_data, columns, profile)

    assert result.status is SolverStatus.OPTIMAL
    assert result.diagnostics["selected_itinerary_by_group"]["T3_P2"] == (
        "PI_T3_P2_ALT"
    )
    assert result.diagnostics["flight_seat_load"]["FO_T3_F2_ORIG"] == 0.0
    assert result.diagnostics["flight_seat_load"]["FO_T3_F3_ORIG"] == 10.0
    assert result.diagnostics["reaccommodated_passengers"] == 10


def test_nonselected_schedule_itineraries_are_forced_to_zero(
    toy_case_003_data, toy_case_003_columns_data
):
    profile = load_passenger_capacity_profile(TOY_CAPACITY_PATH)
    result = _solve(
        toy_case_003_data,
        toy_case_003_columns_data,
        profile,
        option_ids=("FO_T3_F1_ORIG",),
    )

    assert result.status is SolverStatus.OPTIMAL
    assert set(
        result.diagnostics["fixed_column_analysis"][
            "schedule_ineligible_itinerary_ids"
        ]
    ) == {"PI_T3_P1_ALT", "PI_T3_P2_ALT"}
    assert result.diagnostics["unexpected_flight_options"] == []
    assert all(
        item["lhs"] == 0.0
        for item in result.diagnostics["schedule_consistency_constraints"]
    )


def test_no_unserved_column_can_make_shortage_infeasible(
    toy_case_003_data, toy_case_003_columns_data
):
    columns = deepcopy(toy_case_003_columns_data)
    columns["passenger_itineraries"] = [
        item
        for item in columns["passenger_itineraries"]
        if item["status"] != "unserved"
    ]
    profile = _profile_with(
        load_passenger_capacity_profile(TOY_CAPACITY_PATH),
        FO_T3_F1_ORIG=0,
        FO_T3_F2_ORIG=0,
        FO_T3_F3_ORIG=0,
    )
    result = _solve(toy_case_003_data, columns, profile)

    assert result.status is SolverStatus.INFEASIBLE
    assert result.selected_variables == {}


def test_group_without_any_itinerary_fails_before_model_solve(
    toy_case_003_data, toy_case_003_columns_data
):
    columns = deepcopy(toy_case_003_columns_data)
    columns["passenger_itineraries"] = [
        item
        for item in columns["passenger_itineraries"]
        if item["pax_group_id"] != "T3_P2"
    ]
    profile = load_passenger_capacity_profile(TOY_CAPACITY_PATH)

    with pytest.raises(PrmBuildError, match="has no explicit candidate itinerary"):
        _solve(toy_case_003_data, columns, profile)


def test_missing_capacity_for_required_option_fails_fast(
    toy_case_003_data, toy_case_003_columns_data
):
    profile = load_passenger_capacity_profile(TOY_CAPACITY_PATH)
    data = profile.model_dump(mode="python")
    mapping = dict(data["seat_capacity_by_option_id"])
    del mapping["FO_T3_F3_ORIG"]
    data["seat_capacity_by_option_id"] = mapping
    incomplete = PassengerCapacityProfile.model_validate(data)
    request = PassengerRecoveryRequest(
        toy_case_003_data["scenario_id"],
        ("FO_T3_F1_ORIG", "FO_T3_F2_ORIG", "FO_T3_F3_ORIG"),
        incomplete.capacity_profile_id,
    )

    with GurobiAdapter(output_flag=False) as solver:
        with pytest.raises(PrmBuildError, match="missing seat capacity"):
            solve_fixed_column_prm(
                toy_case_003_data,
                toy_case_003_columns_data,
                request,
                incomplete,
                COSTS,
                solver,
            )


@pytest.mark.parametrize(
    "mutation",
    [
        "unknown_group",
        "duplicate_itinerary",
        "unknown_option",
        "invalid_unserved_shape",
        "transported_missing_delay",
    ],
)
def test_prm_entry_point_reuses_column_fail_fast_validation(
    mutation, toy_case_003_data, toy_case_003_columns_data
):
    columns = deepcopy(toy_case_003_columns_data)
    if mutation == "unknown_group":
        columns["passenger_itineraries"][0]["pax_group_id"] = "UNKNOWN"
    elif mutation == "duplicate_itinerary":
        columns["passenger_itineraries"].append(
            deepcopy(columns["passenger_itineraries"][0])
        )
    elif mutation == "unknown_option":
        columns["passenger_itineraries"][0]["segments"][0][
            "flight_option_id"
        ] = "UNKNOWN"
    elif mutation == "invalid_unserved_shape":
        columns["passenger_itineraries"][2]["segments"] = deepcopy(
            columns["passenger_itineraries"][0]["segments"]
        )
    else:
        columns["passenger_itineraries"][0]["arrival_delay_minutes"] = None

    profile = load_passenger_capacity_profile(TOY_CAPACITY_PATH)
    with pytest.raises(PrmBuildError, match="columns validation failed"):
        _solve(toy_case_003_data, columns, profile)


def test_request_rejects_cancel_and_ferry_options(
    phase1_benchmark_001_data, phase1_columns_001_data
):
    profile = load_passenger_capacity_profile(BENCHMARK_CAPACITY_PATH)
    for option_id in ("FO_F3_CANCEL", "FO_FERRY_CA_1140"):
        request = PassengerRecoveryRequest(
            phase1_benchmark_001_data["scenario_id"],
            (option_id,),
            profile.capacity_profile_id,
        )
        with GurobiAdapter(output_flag=False) as solver:
            with pytest.raises(PrmBuildError, match="only revenue OPERATE"):
                solve_fixed_column_prm(
                    phase1_benchmark_001_data,
                    phase1_columns_001_data,
                    request,
                    profile,
                    COSTS,
                    solver,
                )


def test_request_rejects_scenario_and_capacity_profile_mismatch(
    toy_case_003_data, toy_case_003_columns_data
):
    profile = load_passenger_capacity_profile(TOY_CAPACITY_PATH)
    requests = (
        PassengerRecoveryRequest("other", tuple(profile.seat_capacity_by_option_id), profile.capacity_profile_id),
        PassengerRecoveryRequest(toy_case_003_data["scenario_id"], tuple(profile.seat_capacity_by_option_id), "other"),
    )

    for request in requests:
        with GurobiAdapter(output_flag=False) as solver:
            with pytest.raises(PrmBuildError, match="differs"):
                solve_fixed_column_prm(
                    toy_case_003_data,
                    toy_case_003_columns_data,
                    request,
                    profile,
                    COSTS,
                    solver,
                )


def test_independent_audit_rejects_missing_variable_values(
    toy_case_003_data, toy_case_003_columns_data
):
    profile = load_passenger_capacity_profile(TOY_CAPACITY_PATH)
    scenario, scenario_issues = validate_scenario(toy_case_003_data)
    assert scenario is not None and scenario_issues == []
    columns, column_issues = validate_recovery_columns(
        scenario, toy_case_003_columns_data
    )
    assert columns is not None and column_issues == []
    with GurobiAdapter(output_flag=False) as solver:
        model = build_fixed_column_prm(
            scenario,
            columns,
            _request(toy_case_003_data, profile),
            profile,
            COSTS,
            solver,
        )
        with pytest.raises(PrmBuildError, match="missing="):
            recompute_prm_diagnostics(model, {}, COSTS)


def test_independent_audit_rejects_fractional_group_splitting(
    toy_case_003_data, toy_case_003_columns_data
):
    profile = load_passenger_capacity_profile(TOY_CAPACITY_PATH)
    scenario, scenario_issues = validate_scenario(toy_case_003_data)
    assert scenario is not None and scenario_issues == []
    columns, column_issues = validate_recovery_columns(
        scenario, toy_case_003_columns_data
    )
    assert columns is not None and column_issues == []
    with GurobiAdapter(output_flag=False) as solver:
        model = build_fixed_column_prm(
            scenario,
            columns,
            _request(toy_case_003_data, profile),
            profile,
            COSTS,
            solver,
        )
        values = {itinerary_id: 0.0 for itinerary_id in model.variables}
        values["PI_T3_P1_DIRECT"] = 0.5
        values["PI_T3_P1_UNSERVED"] = 0.5
        values["PI_T3_P2_DIRECT"] = 0.5
        values["PI_T3_P2_UNSERVED"] = 0.5
        diagnostics = recompute_prm_diagnostics(model, values, COSTS)

    assert all(
        item["satisfied"] for item in diagnostics["group_selection_constraints"]
    )
    assert not diagnostics["all_constraints_satisfied"]
    assert any(not item["satisfied"] for item in diagnostics["variable_domain_checks"])
