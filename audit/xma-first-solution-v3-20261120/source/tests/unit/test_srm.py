import copy
from pathlib import Path

import pytest

from backend.config.costs import load_cost_config
from backend.core.srm import (
    MARKET_SEAT_MODE,
    SrmBuildError,
    solve_fixed_column_srm,
)
from backend.solver import GurobiAdapter, SolverStatus


@pytest.fixture
def adapter():
    available, reason = GurobiAdapter.availability()
    if not available:
        pytest.skip(reason or "Gurobi is unavailable")
    with GurobiAdapter(output_flag=False) as instance:
        yield instance


@pytest.fixture
def costs():
    return load_cost_config(
        Path(__file__).parents[2] / "data" / "costs" / "phase2_test_costs_v1.json"
    )


def _schedule_only_columns(columns_data):
    result = copy.deepcopy(columns_data)
    result["aircraft_strings"] = []
    result["crew_pairings"] = []
    result["passenger_itineraries"] = []
    return result


def _flight(scenario_data, flight_id):
    return next(
        item for item in scenario_data["flights"] if item["flight_id"] == flight_id
    )


def _options_for(columns_data, flight_id):
    return [
        item
        for item in columns_data["flight_options"]
        if item["base_flight_id"] == flight_id
    ]


def _replace_flight_options(columns_data, flight_id, replacements):
    columns_data["flight_options"] = [
        item
        for item in columns_data["flight_options"]
        if item["base_flight_id"] != flight_id
    ] + replacements


def test_srm_c01_exactly_one_and_ferry_excluded(
    adapter, costs, phase1_benchmark_001_data, phase1_columns_001_data
):
    result = solve_fixed_column_srm(
        phase1_benchmark_001_data, phase1_columns_001_data, costs, adapter
    )

    coverage = result.diagnostics["flight_coverage_constraints"]
    assert len(coverage) == len(phase1_benchmark_001_data["flights"])
    assert all(item["lhs"] == pytest.approx(1.0) for item in coverage)
    assert "x[FO_FERRY_CA_1140]" not in result.selected_variables


def test_srm_c01_missing_options_fails_explicitly(
    adapter, costs, phase1_benchmark_001_data, phase1_columns_001_data
):
    columns = _schedule_only_columns(phase1_columns_001_data)
    _replace_flight_options(columns, "F3", [])

    with pytest.raises(SrmBuildError, match="SRM-C01-FLIGHT-COVERAGE"):
        solve_fixed_column_srm(phase1_benchmark_001_data, columns, costs, adapter)


def test_srm_c02_strategic_cancel_only_is_infeasible(
    adapter, costs, phase1_benchmark_001_data, phase1_columns_001_data
):
    scenario = copy.deepcopy(phase1_benchmark_001_data)
    flight = _flight(scenario, "F3")
    flight["strategic_flag"] = True
    flight["market_flag"] = False
    flight["min_seats"] = 0
    columns = _schedule_only_columns(phase1_columns_001_data)
    cancel = next(
        item
        for item in _options_for(columns, "F3")
        if item["operation_type"] == "cancel"
    )
    _replace_flight_options(columns, "F3", [cancel])

    result = solve_fixed_column_srm(scenario, columns, costs, adapter)

    assert result.status in {
        SolverStatus.INFEASIBLE,
        SolverStatus.INFEASIBLE_OR_UNBOUNDED,
    }
    assert result.selected_variables == {}


def test_srm_c02_strategic_delayed_operate_is_allowed(
    adapter, costs, phase1_benchmark_001_data, phase1_columns_001_data
):
    scenario = copy.deepcopy(phase1_benchmark_001_data)
    flight = _flight(scenario, "F3")
    flight["strategic_flag"] = True
    flight["market_flag"] = False
    flight["min_seats"] = 0
    columns = _schedule_only_columns(phase1_columns_001_data)
    delayed = next(
        item for item in _options_for(columns, "F3") if item["option_id"] == "FO_F3_D30"
    )
    _replace_flight_options(columns, "F3", [delayed])

    result = solve_fixed_column_srm(scenario, columns, costs, adapter)

    assert result.status is SolverStatus.OPTIMAL
    assert result.diagnostics["selected_option_by_flight"]["F3"] == "FO_F3_D30"
    assert result.diagnostics["strategic_constraints"][-1]["satisfied"]


def test_srm_c02_non_strategic_flight_can_cancel(
    adapter, costs, phase1_benchmark_001_data, phase1_columns_001_data
):
    scenario = copy.deepcopy(phase1_benchmark_001_data)
    flight = _flight(scenario, "F3")
    flight["strategic_flag"] = False
    flight["market_flag"] = False
    flight["min_seats"] = 0
    columns = _schedule_only_columns(phase1_columns_001_data)
    cancel = next(
        item
        for item in _options_for(columns, "F3")
        if item["operation_type"] == "cancel"
    )
    _replace_flight_options(columns, "F3", [cancel])

    result = solve_fixed_column_srm(scenario, columns, costs, adapter)

    assert result.status is SolverStatus.OPTIMAL
    assert "F3" in result.diagnostics["cancelled_flights"]
    c_departure = next(
        item
        for item in result.diagnostics["departure_capacity_load"]
        if item["capacity_interval"]["airport"] == "C"
    )
    assert c_departure["lhs"] == pytest.approx(1.0)


def test_srm_c03_c04_capacity_and_half_open_boundary(
    adapter, costs, phase1_benchmark_001_data, phase1_columns_001_data
):
    result = solve_fixed_column_srm(
        phase1_benchmark_001_data, phase1_columns_001_data, costs, adapter
    )

    b_departure = next(
        item
        for item in result.diagnostics["departure_capacity_load"]
        if item["capacity_interval"]["airport"] == "B"
    )
    assert b_departure["lhs"] == pytest.approx(2.0)
    assert b_departure["rhs"] == pytest.approx(2.0)
    assert result.diagnostics["selected_option_by_flight"]["F2"] == "FO_F2_D50"
    assert all(
        item["satisfied"]
        for item in result.diagnostics["arrival_capacity_load"]
        + result.diagnostics["departure_capacity_load"]
    )


def test_srm_c04_overloaded_capacity_is_infeasible(
    adapter, costs, phase1_benchmark_001_data, phase1_columns_001_data
):
    scenario = copy.deepcopy(phase1_benchmark_001_data)
    for interval in scenario["airport_intervals"]:
        if interval["airport"] == "B":
            interval["dep_capacity"] = 1

    result = solve_fixed_column_srm(scenario, phase1_columns_001_data, costs, adapter)

    assert result.status in {
        SolverStatus.INFEASIBLE,
        SolverStatus.INFEASIBLE_OR_UNBOUNDED,
    }


def test_srm_c03_reduced_arrival_capacity_changes_schedule(
    adapter, costs, phase1_benchmark_001_data, phase1_columns_001_data
):
    scenario = copy.deepcopy(phase1_benchmark_001_data)
    for interval in scenario["airport_intervals"]:
        if interval["airport"] == "D":
            interval["arr_capacity"] = 2

    result = solve_fixed_column_srm(scenario, phase1_columns_001_data, costs, adapter)

    assert result.status is SolverStatus.OPTIMAL
    assert result.diagnostics["selected_option_by_flight"]["F11"] == "FO_F11_DEST_C"
    d_arrival = next(
        item
        for item in result.diagnostics["arrival_capacity_load"]
        if item["capacity_interval"]["airport"] == "D"
    )
    assert d_arrival["lhs"] == pytest.approx(2.0)
    assert d_arrival["satisfied"]


def test_srm_c05_gate_overload_is_infeasible(
    adapter, costs, phase1_benchmark_001_data, phase1_columns_001_data
):
    scenario = copy.deepcopy(phase1_benchmark_001_data)
    for interval in scenario["airport_intervals"]:
        if interval["airport"] == "B":
            interval["gate_capacity"] = 2

    result = solve_fixed_column_srm(scenario, phase1_columns_001_data, costs, adapter)

    assert result.status in {
        SolverStatus.INFEASIBLE,
        SolverStatus.INFEASIBLE_OR_UNBOUNDED,
    }


def test_srm_c06_market_proxy_cancel_only_is_infeasible(
    adapter, costs, phase1_benchmark_001_data, phase1_columns_001_data
):
    columns = _schedule_only_columns(phase1_columns_001_data)
    cancel = next(
        item
        for item in _options_for(columns, "F3")
        if item["operation_type"] == "cancel"
    )
    _replace_flight_options(columns, "F3", [cancel])

    result = solve_fixed_column_srm(phase1_benchmark_001_data, columns, costs, adapter)

    assert result.status in {
        SolverStatus.INFEASIBLE,
        SolverStatus.INFEASIBLE_OR_UNBOUNDED,
    }
    assert result.diagnostics["market_constraint_mode"] == MARKET_SEAT_MODE


def test_srm_rejects_unknown_base_flight_and_duplicate_option_id(
    adapter, costs, phase1_benchmark_001_data, phase1_columns_001_data
):
    unknown = _schedule_only_columns(phase1_columns_001_data)
    unknown["flight_options"][0]["base_flight_id"] = "UNKNOWN"
    with pytest.raises(SrmBuildError, match="unknown_flight"):
        solve_fixed_column_srm(phase1_benchmark_001_data, unknown, costs, adapter)

    duplicate = _schedule_only_columns(phase1_columns_001_data)
    duplicate["flight_options"].append(copy.deepcopy(duplicate["flight_options"][0]))
    with pytest.raises(SrmBuildError, match="duplicate_id"):
        solve_fixed_column_srm(phase1_benchmark_001_data, duplicate, costs, adapter)
