import copy
from pathlib import Path

import pytest

from backend.config import (
    FixedColumnCostConfig,
    aircraft_string_cost,
    load_cost_config,
)
from backend.core import (
    AircraftRecoveryRequest,
    ArmBuildError,
    build_fixed_column_arm,
    solve_fixed_column_arm,
)
from backend.schemas.columns import RecoveryColumns
from backend.schemas.scenario import Scenario
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


def _one_aircraft_case():
    scenario = {
        "scenario_id": "arm_unit_case",
        "recovery_window": {
            "start_time": "2026-01-15T08:00:00Z",
            "end_time": "2026-01-15T12:00:00Z",
        },
        "airports": [
            {"airport_id": "A", "name": "Alpha"},
            {"airport_id": "B", "name": "Bravo"},
        ],
        "flights": [
            {
                "flight_id": "F1",
                "origin": "A",
                "destination": "B",
                "sched_dep": "2026-01-15T09:00:00Z",
                "sched_arr": "2026-01-15T10:00:00Z",
                "duration": 60,
                "original_aircraft": "AC1",
                "original_equipment": "E1",
                "original_crew": "C1",
                "strategic_flag": False,
                "market_flag": False,
                "min_seats": 0,
                "max_delay": 60,
            }
        ],
        "aircraft": [
            {
                "tail_id": "AC1",
                "equipment_type": "E1",
                "initial_station_at_t": "A",
                "required_station_at_T_end": "B",
                "maintenance_required": False,
                "maintenance_stations": ["B"],
                "original_rotation": ["F1"],
            }
        ],
        "crew": [
            {
                "crew_id": "C1",
                "rating": "E1",
                "start_station_at_t": "A",
                "required_station_at_T_end": "B",
                "original_duties": [["F1"]],
                "original_pairing": ["F1"],
            }
        ],
        "passengers": [],
        "airport_intervals": [
            {
                "airport": airport,
                "start_time": "2026-01-15T08:00:00Z",
                "end_time": "2026-01-15T12:00:00Z",
                "arr_capacity": 10,
                "dep_capacity": 10,
                "gate_capacity": 10,
                "curfew_flag": False,
                "weather_restrictions": [],
            }
            for airport in ("A", "B")
        ],
        "disruptions": [],
    }
    columns = {
        "schema_version": "1.0.0",
        "scenario_id": scenario["scenario_id"],
        "time_unit": "minute",
        "notes": [],
        "flight_options": [
            {
                "option_id": "FO_F1_ORIG",
                "base_flight_id": "F1",
                "operation_type": "operate",
                "change_types": ["unchanged"],
                "origin": "A",
                "destination": "B",
                "dep_time": "2026-01-15T09:00:00Z",
                "arr_time": "2026-01-15T10:00:00Z",
                "block_minutes": 60,
                "departure_delay_minutes": 0,
                "arrival_delay_minutes": 0,
                "notes": "",
            },
            {
                "option_id": "FO_F1_D30",
                "base_flight_id": "F1",
                "operation_type": "operate",
                "change_types": ["delay"],
                "origin": "A",
                "destination": "B",
                "dep_time": "2026-01-15T09:30:00Z",
                "arr_time": "2026-01-15T10:30:00Z",
                "block_minutes": 60,
                "departure_delay_minutes": 30,
                "arrival_delay_minutes": 30,
                "notes": "",
            },
            {
                "option_id": "FO_F1_CANCEL",
                "base_flight_id": "F1",
                "operation_type": "cancel",
                "change_types": ["cancel"],
                "origin": None,
                "destination": None,
                "dep_time": None,
                "arr_time": None,
                "block_minutes": None,
                "departure_delay_minutes": None,
                "arrival_delay_minutes": None,
                "notes": "",
            },
        ],
        "aircraft_strings": [
            {
                "string_id": "AS_ORIG",
                "aircraft_id": "AC1",
                "leg_option_ids": ["FO_F1_ORIG"],
                "start_station": "A",
                "end_station": "B",
                "maintenance_satisfied": True,
                "cost_components": {},
                "notes": "",
            },
            {
                "string_id": "AS_DELAY",
                "aircraft_id": "AC1",
                "leg_option_ids": ["FO_F1_D30"],
                "start_station": "A",
                "end_station": "B",
                "maintenance_satisfied": True,
                "cost_components": {},
                "notes": "",
            },
        ],
        "crew_pairings": [],
        "passenger_itineraries": [],
    }
    return scenario, columns


def _request(option_ids=("FO_F1_ORIG",)):
    return AircraftRecoveryRequest("arm_unit_case", option_ids)


def _solve(adapter, costs, scenario, columns, option_ids=("FO_F1_ORIG",)):
    return solve_fixed_column_arm(
        scenario,
        columns,
        _request(option_ids),
        costs,
        adapter,
        solver_parameters={"DualReductions": 0},
    )


def test_arm_c01_selects_exactly_one_of_two_strings(adapter, costs):
    scenario, columns = _one_aircraft_case()
    alternative = copy.deepcopy(columns["aircraft_strings"][0])
    alternative["string_id"] = "AS_ORIG_ALTERNATIVE"
    columns["aircraft_strings"].append(alternative)

    result = _solve(adapter, costs, scenario, columns)

    assert result.status is SolverStatus.OPTIMAL
    assert len(result.selected_variables) == 1
    assert result.diagnostics["string_selection_constraints"][0]["lhs"] == 1
    assert result.diagnostics["covered_required_options"] == ["FO_F1_ORIG"]


def test_arm_c02_required_option_without_covering_string_is_infeasible(adapter, costs):
    scenario, columns = _one_aircraft_case()
    columns["aircraft_strings"] = [columns["aircraft_strings"][0]]

    result = _solve(adapter, costs, scenario, columns, option_ids=("FO_F1_D30",))

    assert result.status is SolverStatus.INFEASIBLE


def test_arm_c02_duplicate_required_coverage_is_prohibited(adapter, costs):
    scenario, columns = _one_aircraft_case()
    columns["aircraft_strings"] = [columns["aircraft_strings"][0]]
    scenario["aircraft"].append(
        {
            "tail_id": "AC2",
            "equipment_type": "E1",
            "initial_station_at_t": "A",
            "required_station_at_T_end": "B",
            "maintenance_required": False,
            "maintenance_stations": ["B"],
            "original_rotation": [],
        }
    )
    second_string = copy.deepcopy(columns["aircraft_strings"][0])
    second_string.update(string_id="AS_AC2", aircraft_id="AC2")
    columns["aircraft_strings"].append(second_string)

    result = _solve(adapter, costs, scenario, columns)

    assert result.status is SolverStatus.INFEASIBLE


def test_arm_c02_rejects_non_required_revenue_option_leakage(adapter, costs):
    scenario, columns = _one_aircraft_case()
    scenario["flights"].append(
        {
            "flight_id": "F2",
            "origin": "B",
            "destination": "A",
            "sched_dep": "2026-01-15T10:30:00Z",
            "sched_arr": "2026-01-15T11:30:00Z",
            "duration": 60,
            "original_aircraft": "AC1",
            "original_equipment": "E1",
            "original_crew": "C1",
            "strategic_flag": False,
            "market_flag": False,
            "min_seats": 0,
            "max_delay": 0,
        }
    )
    scenario["aircraft"][0].update(
        required_station_at_T_end="A", original_rotation=["F1", "F2"]
    )
    scenario["crew"][0].update(
        required_station_at_T_end="A",
        original_duties=[["F1", "F2"]],
        original_pairing=["F1", "F2"],
    )
    columns["flight_options"].append(
        {
            "option_id": "FO_F2_ORIG",
            "base_flight_id": "F2",
            "operation_type": "operate",
            "change_types": ["unchanged"],
            "origin": "B",
            "destination": "A",
            "dep_time": "2026-01-15T10:30:00Z",
            "arr_time": "2026-01-15T11:30:00Z",
            "block_minutes": 60,
            "departure_delay_minutes": 0,
            "arrival_delay_minutes": 0,
            "notes": "",
        }
    )
    columns["aircraft_strings"] = [
        {
            "string_id": "AS_CHAIN_WITH_LEAK",
            "aircraft_id": "AC1",
            "leg_option_ids": ["FO_F1_ORIG", "FO_F2_ORIG"],
            "start_station": "A",
            "end_station": "A",
            "maintenance_satisfied": True,
            "cost_components": {},
            "notes": "",
        }
    ]

    result = _solve(adapter, costs, scenario, columns)

    assert result.status is SolverStatus.INFEASIBLE


def test_arm_c03_all_terminal_incompatible_strings_are_infeasible(adapter, costs):
    scenario_data, columns_data = _one_aircraft_case()
    scenario_data["aircraft"][0]["required_station_at_T_end"] = "A"
    scenario = Scenario.model_validate(scenario_data)
    columns = RecoveryColumns.model_validate(columns_data)

    build_fixed_column_arm(scenario, columns, _request(), costs, adapter)
    outcome = adapter.solve({"DualReductions": 0})

    assert outcome.status is SolverStatus.INFEASIBLE


def test_arm_c04_maintenance_required_with_satisfied_string_is_feasible(adapter, costs):
    scenario, columns = _one_aircraft_case()
    scenario["aircraft"][0]["maintenance_required"] = True

    result = _solve(adapter, costs, scenario, columns)

    assert result.status is SolverStatus.OPTIMAL
    assert result.diagnostics["maintenance_status"][0]["satisfied"]


def test_arm_c04_no_maintenance_satisfied_string_is_infeasible(adapter, costs):
    scenario_data, columns_data = _one_aircraft_case()
    scenario_data["aircraft"][0]["maintenance_required"] = True
    for aircraft_string in columns_data["aircraft_strings"]:
        aircraft_string["maintenance_satisfied"] = False
    scenario = Scenario.model_validate(scenario_data)
    columns = RecoveryColumns.model_validate(columns_data)

    build_fixed_column_arm(scenario, columns, _request(), costs, adapter)
    outcome = adapter.solve({"DualReductions": 0})

    assert outcome.status is SolverStatus.INFEASIBLE


def test_arm_objective_does_not_charge_srm_delay(adapter, costs):
    scenario, columns = _one_aircraft_case()

    result = _solve(adapter, costs, scenario, columns, option_ids=("FO_F1_D30",))

    assert result.status is SolverStatus.OPTIMAL
    assert result.objective_value == pytest.approx(0.0)
    assert result.diagnostics["objective_breakdown"] == {
        "aircraft_reassignment": 0.0,
        "ferry": 0,
        "total": 0.0,
    }


def test_aircraft_reassignment_cost_responds_to_nonzero_coefficient(
    costs, phase1_benchmark_001_data, phase1_columns_001_data
):
    scenario = Scenario.model_validate(phase1_benchmark_001_data)
    columns = RecoveryColumns.model_validate(phase1_columns_001_data)
    cost_data = costs.model_dump(mode="json")
    cost_data["coefficients"]["aircraft_reassignment"]["value"] = 100
    nonzero_costs = FixedColumnCostConfig.model_validate(cost_data)
    options = {option.option_id: option for option in columns.flight_options}
    aircraft_string = next(
        item for item in columns.aircraft_strings if item.string_id == "AS_AC1_SWAP_F10"
    )

    breakdown = aircraft_string_cost(scenario, options, aircraft_string, nonzero_costs)

    assert breakdown.reassignment_count == 1
    assert breakdown.reassignment_cost == pytest.approx(100.0)
    assert breakdown.ferry_minutes == 0
    assert breakdown.total == pytest.approx(100.0)


def test_arm_accepts_and_charges_ferry_without_revenue_coverage(adapter, costs):
    scenario, columns = _one_aircraft_case()
    scenario["flights"].append(
        {
            "flight_id": "F2",
            "origin": "B",
            "destination": "A",
            "sched_dep": "2026-01-15T10:30:00Z",
            "sched_arr": "2026-01-15T11:30:00Z",
            "duration": 60,
            "original_aircraft": "AC1",
            "original_equipment": "E1",
            "original_crew": "C1",
            "strategic_flag": False,
            "market_flag": False,
            "min_seats": 0,
            "max_delay": 0,
        }
    )
    scenario["aircraft"][0]["required_station_at_T_end"] = "A"
    scenario["aircraft"][0]["original_rotation"] = ["F1", "F2"]
    scenario["crew"][0].update(
        required_station_at_T_end="A",
        original_duties=[["F1", "F2"]],
        original_pairing=["F1", "F2"],
    )
    columns["flight_options"].append(
        {
            "option_id": "FO_F2_CANCEL",
            "base_flight_id": "F2",
            "operation_type": "cancel",
            "change_types": ["cancel"],
            "origin": None,
            "destination": None,
            "dep_time": None,
            "arr_time": None,
            "block_minutes": None,
            "departure_delay_minutes": None,
            "arrival_delay_minutes": None,
            "notes": "",
        }
    )
    columns["flight_options"].append(
        {
            "option_id": "FO_FERRY_BA",
            "base_flight_id": None,
            "operation_type": "ferry",
            "change_types": ["positioning"],
            "origin": "B",
            "destination": "A",
            "dep_time": "2026-01-15T10:00:00Z",
            "arr_time": "2026-01-15T11:00:00Z",
            "block_minutes": 60,
            "departure_delay_minutes": None,
            "arrival_delay_minutes": None,
            "notes": "",
        }
    )
    columns["aircraft_strings"] = [
        {
            "string_id": "AS_WITH_FERRY",
            "aircraft_id": "AC1",
            "leg_option_ids": ["FO_F1_ORIG", "FO_FERRY_BA"],
            "start_station": "A",
            "end_station": "A",
            "maintenance_satisfied": True,
            "cost_components": {},
            "notes": "",
        }
    ]

    result = _solve(adapter, costs, scenario, columns)

    assert result.status is SolverStatus.OPTIMAL
    assert result.diagnostics["covered_required_options"] == ["FO_F1_ORIG"]
    assert "FO_FERRY_BA" not in result.diagnostics["option_coverage"]
    assert result.diagnostics["ferry_minutes"] == 60
    assert result.diagnostics["objective_breakdown"]["ferry"] == pytest.approx(300.0)
    assert result.objective_value == pytest.approx(300.0)


def test_arm_request_rejects_duplicates_and_conflicting_base_flight(adapter, costs):
    with pytest.raises(ValueError, match="must be unique"):
        AircraftRecoveryRequest("arm_unit_case", ("FO_F1_ORIG", "FO_F1_ORIG"))

    scenario, columns = _one_aircraft_case()
    with pytest.raises(ArmBuildError, match="conflicting schedule options"):
        _solve(
            adapter,
            costs,
            scenario,
            columns,
            option_ids=("FO_F1_ORIG", "FO_F1_D30"),
        )


def test_arm_rejects_unknown_or_non_operated_required_option(adapter, costs):
    scenario, columns = _one_aircraft_case()
    with pytest.raises(ArmBuildError, match="unknown required operated option"):
        _solve(adapter, costs, scenario, columns, option_ids=("UNKNOWN",))
    with pytest.raises(ArmBuildError, match="not a revenue operate option"):
        _solve(
            adapter,
            costs,
            scenario,
            columns,
            option_ids=("FO_F1_CANCEL",),
        )


@pytest.mark.parametrize(
    ("mutation", "error_code"),
    [
        ("duplicate_string", "duplicate_id"),
        ("unknown_aircraft", "unknown_aircraft"),
        ("unknown_leg", "unknown_flight_option"),
        ("cancel_leg", "cancel_option_in_aircraft_string"),
    ],
)
def test_arm_entry_point_reuses_string_semantic_validation(
    adapter, costs, mutation, error_code
):
    scenario, columns = _one_aircraft_case()
    if mutation == "duplicate_string":
        columns["aircraft_strings"].append(
            copy.deepcopy(columns["aircraft_strings"][0])
        )
    elif mutation == "unknown_aircraft":
        columns["aircraft_strings"][0]["aircraft_id"] = "UNKNOWN"
    elif mutation == "unknown_leg":
        columns["aircraft_strings"][0]["leg_option_ids"] = ["UNKNOWN"]
    else:
        columns["aircraft_strings"][0]["leg_option_ids"] = ["FO_F1_CANCEL"]

    with pytest.raises(ArmBuildError, match=error_code):
        _solve(adapter, costs, scenario, columns)


def test_arm_rejects_aircraft_without_explicit_string(adapter, costs):
    scenario, columns = _one_aircraft_case()
    columns["aircraft_strings"] = []

    with pytest.raises(ArmBuildError, match="has no explicit candidate string"):
        _solve(adapter, costs, scenario, columns)
