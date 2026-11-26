from copy import deepcopy
from pathlib import Path

import pytest

from backend.config import load_cost_config, load_passenger_capacity_profile
from backend.core import (
    IntegratedOracleBuildError,
    IntegratedRecoveryRequest,
    audit_integrated_candidate,
    build_integrated_fixed_column_oracle,
    solve_integrated_fixed_column_oracle,
)
from backend.schemas.columns import RecoveryColumns
from backend.schemas.scenario import Scenario
from backend.solver import GurobiAdapter, SolverStatus


ROOT = Path(__file__).parents[2]


def _costs():
    return load_cost_config(ROOT / "data" / "costs" / "phase2_test_costs_v1.json")


def _capacity(case: str):
    return load_passenger_capacity_profile(
        ROOT / "data" / "capacities" / f"{case}_capacity.json"
    )


def _request(case: str):
    costs = _costs()
    capacity = _capacity(case)
    return IntegratedRecoveryRequest(
        case, costs.cost_profile_id, capacity.capacity_profile_id
    )


def _gurobi():
    available, reason = GurobiAdapter.availability()
    assert available, reason or "Gurobi is required for Phase 3 integration tests"
    return GurobiAdapter(output_flag=False)


def test_integrated_model_contains_x_y_z_w_in_one_solver_model(
    toy_case_005_data, toy_case_005_columns_data
):
    scenario = Scenario.model_validate(toy_case_005_data)
    columns = RecoveryColumns.model_validate(toy_case_005_columns_data)
    with _gurobi() as solver:
        model = build_integrated_fixed_column_oracle(
            scenario,
            columns,
            _request("toy_case_005"),
            _capacity("toy_case_005"),
            _costs(),
            solver,
        )

        assert set(model.x_variables) == {"FO_T5_F1_ORIG", "FO_T5_F1_D10"}
        assert set(model.y_variables) == {"AS_T5_AC1_ORIG", "AS_T5_AC1_D10"}
        assert set(model.z_variables) == {"CP_T5_C1_ORIG", "CP_T5_C1_D10"}
        assert set(model.w_variables) == {
            "PI_T5_P1_ORIG",
            "PI_T5_P1_D10",
            "PI_T5_P1_UNSERVED",
        }
        assert all(item._model_token == next(iter(model.x_variables.values()))._model_token for group in (model.x_variables, model.y_variables, model.z_variables, model.w_variables) for item in group.values())


def test_manual_candidate_audit_detects_each_cross_model_violation(
    toy_case_005_data, toy_case_005_columns_data
):
    scenario = Scenario.model_validate(toy_case_005_data)
    columns = RecoveryColumns.model_validate(toy_case_005_columns_data)
    with _gurobi() as solver:
        model = build_integrated_fixed_column_oracle(
            scenario, columns, _request("toy_case_005"), _capacity("toy_case_005"), _costs(), solver
        )

        no_crew = audit_integrated_candidate(
            model,
            selected_option_by_flight={"T5_F1": "FO_T5_F1_ORIG"},
            selected_string_by_aircraft={"T5_AC1": "AS_T5_AC1_ORIG"},
            selected_pairing_by_crew={"T5_C1": "CP_T5_C1_D10"},
            selected_itinerary_by_group={"T5_P1": "PI_T5_P1_ORIG"},
        )
        wrong_passenger = audit_integrated_candidate(
            model,
            selected_option_by_flight={"T5_F1": "FO_T5_F1_D10"},
            selected_string_by_aircraft={"T5_AC1": "AS_T5_AC1_D10"},
            selected_pairing_by_crew={"T5_C1": "CP_T5_C1_D10"},
            selected_itinerary_by_group={"T5_P1": "PI_T5_P1_ORIG"},
        )
        over_capacity = audit_integrated_candidate(
            model,
            selected_option_by_flight={"T5_F1": "FO_T5_F1_ORIG"},
            selected_string_by_aircraft={"T5_AC1": "AS_T5_AC1_ORIG"},
            selected_pairing_by_crew={"T5_C1": "CP_T5_C1_ORIG"},
            selected_itinerary_by_group={"T5_P1": "PI_T5_P1_ORIG"},
        )

    assert not no_crew["cross_model_audit"]["schedule_crew"][0]["satisfied"]
    assert any(
        not item["satisfied"]
        for item in wrong_passenger["cross_model_audit"]["passenger_schedule"]
    )
    assert any(
        not item["satisfied"]
        for item in over_capacity["cross_model_audit"]["seat_schedule"]
    )


def test_manual_candidate_audit_detects_selected_flight_without_aircraft(
    toy_case_004_data, toy_case_004_columns_data
):
    scenario = Scenario.model_validate(toy_case_004_data)
    columns = RecoveryColumns.model_validate(toy_case_004_columns_data)
    with _gurobi() as solver:
        model = build_integrated_fixed_column_oracle(
            scenario, columns, _request("toy_case_004"), _capacity("toy_case_004"), _costs(), solver
        )
        audit = audit_integrated_candidate(
            model,
            selected_option_by_flight={"T4_F1": "FO_T4_F1_ORIG"},
            selected_string_by_aircraft={"T4_AC1": "AS_T4_AC1_D10"},
            selected_pairing_by_crew={"T4_C1": "CP_T4_C1_ORIG"},
            selected_itinerary_by_group={"T4_P1": "PI_T4_P1_ORIG"},
        )

    assert any(
        not item["satisfied"]
        for item in audit["cross_model_audit"]["schedule_aircraft"]
    )


def test_complementary_aircraft_and_crew_coverage_has_no_joint_solution(
    toy_case_004_data, toy_case_004_columns_data
):
    columns = deepcopy(toy_case_004_columns_data)
    columns["crew_pairings"] = [
        item for item in columns["crew_pairings"] if item["pairing_id"] == "CP_T4_C1_ORIG"
    ]

    with _gurobi() as solver:
        result = solve_integrated_fixed_column_oracle(
            toy_case_004_data,
            columns,
            _request("toy_case_004"),
            _capacity("toy_case_004"),
            _costs(),
            solver,
            solver_parameters={"DualReductions": 0},
        )

    assert result.status is SolverStatus.INFEASIBLE
    assert result.objective_value is None


def test_missing_capacity_for_any_referenced_itinerary_option_is_rejected(
    toy_case_005_data, toy_case_005_columns_data
):
    capacity = _capacity("toy_case_005")
    capacity_data = capacity.model_dump(mode="json")
    del capacity_data["seat_capacity_by_option_id"]["FO_T5_F1_D10"]
    incomplete = type(capacity).model_validate(capacity_data)
    request = IntegratedRecoveryRequest(
        "toy_case_005", _costs().cost_profile_id, incomplete.capacity_profile_id
    )

    with _gurobi() as solver, pytest.raises(
        IntegratedOracleBuildError, match="without test/residual capacity"
    ):
        solve_integrated_fixed_column_oracle(
            toy_case_005_data,
            toy_case_005_columns_data,
            request,
            incomplete,
            _costs(),
            solver,
        )


def test_ferry_remains_arm_owned_and_has_no_schedule_variable(
    phase1_benchmark_001_data, phase1_columns_001_data
):
    capacity = load_passenger_capacity_profile(
        ROOT / "data" / "capacities" / "phase2_test_seat_capacity_v1.json"
    )
    costs = _costs()
    scenario = Scenario.model_validate(phase1_benchmark_001_data)
    columns = RecoveryColumns.model_validate(phase1_columns_001_data)
    request = IntegratedRecoveryRequest(
        scenario.scenario_id, costs.cost_profile_id, capacity.capacity_profile_id
    )
    with _gurobi() as solver:
        model = build_integrated_fixed_column_oracle(
            scenario, columns, request, capacity, costs, solver
        )

    assert "FO_FERRY_CA_1140" not in model.x_variables
    assert any(
        breakdown.ferry_cost > 0 for breakdown in model.string_costs.values()
    )


def test_cancel_selection_automatically_cuts_resource_and_passenger_use(
    toy_case_005_data, toy_case_005_columns_data
):
    scenario = deepcopy(toy_case_005_data)
    columns = deepcopy(toy_case_005_columns_data)
    columns["flight_options"].append(
        {
            "option_id": "FO_T5_F1_CANCEL",
            "base_flight_id": "T5_F1",
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
    columns["aircraft_strings"] = [
        {
            "string_id": "AS_T5_AC1_IDLE",
            "aircraft_id": "T5_AC1",
            "leg_option_ids": [],
            "start_station": "A",
            "end_station": "B",
            "maintenance_satisfied": True,
            "cost_components": {},
            "notes": "Explicit idle string for cancellation test.",
        }
    ]
    columns["crew_pairings"] = [
        {
            "pairing_id": "CP_T5_C1_IDLE",
            "crew_id": "T5_C1",
            "duties": [],
            "start_station": "A",
            "end_station": "B",
            "cost_components": {},
            "notes": "Explicit idle pairing for cancellation test.",
        }
    ]
    columns["passenger_itineraries"] = [
        item
        for item in columns["passenger_itineraries"]
        if item["itinerary_id"] == "PI_T5_P1_UNSERVED"
    ]

    with _gurobi() as solver:
        result = solve_integrated_fixed_column_oracle(
            scenario,
            columns,
            _request("toy_case_005"),
            _capacity("toy_case_005"),
            _costs(),
            solver,
        )

    assert result.status is SolverStatus.OPTIMAL
    assert result.diagnostics["selected_option_by_flight"] == {
        "T5_F1": "FO_T5_F1_CANCEL"
    }
    assert result.diagnostics["arm_audit"]["covered_required_options"] == []
    assert result.diagnostics["crm_audit"]["covered_required_options"] == []
    assert result.diagnostics["prm_audit"]["selected_itinerary_by_group"] == {
        "T5_P1": "PI_T5_P1_UNSERVED"
    }
    assert result.diagnostics["cross_model_audit"]["all_constraints_satisfied"]


def test_deadhead_on_unselected_option_makes_constructed_case_infeasible(
    toy_case_004_data, toy_case_004_columns_data
):
    scenario = deepcopy(toy_case_004_data)
    columns = deepcopy(toy_case_004_columns_data)
    scenario["flights"].append(
        {
            "flight_id": "T4_F2",
            "origin": "B",
            "destination": "A",
            "sched_dep": "2026-01-15T09:20:00Z",
            "sched_arr": "2026-01-15T09:50:00Z",
            "duration": 30,
            "original_aircraft": "T4_AC1",
            "original_equipment": "E1",
            "original_crew": "T4_C1",
            "strategic_flag": False,
            "market_flag": False,
            "min_seats": 0,
            "max_delay": 0,
        }
    )
    scenario["aircraft"][0]["original_rotation"].append("T4_F2")
    scenario["aircraft"][0]["required_station_at_T_end"] = "A"
    scenario["crew"][0]["required_station_at_T_end"] = "A"
    scenario["crew"][0]["original_duties"][0].append("T4_F2")
    scenario["crew"][0]["original_pairing"].append("T4_F2")
    columns["flight_options"].extend(
        [
            {
                "option_id": "FO_T4_FERRY_BA",
                "base_flight_id": None,
                "operation_type": "ferry",
                "change_types": ["positioning"],
                "origin": "B",
                "destination": "A",
                "dep_time": "2026-01-15T09:11:00Z",
                "arr_time": "2026-01-15T09:16:00Z",
                "block_minutes": 5,
                "departure_delay_minutes": None,
                "arrival_delay_minutes": None,
                "notes": "Returns the selected aircraft string to its required terminal.",
            },
            {
                "option_id": "FO_T4_F2_ORIG",
                "base_flight_id": "T4_F2",
                "operation_type": "operate",
                "change_types": ["unchanged"],
                "origin": "B",
                "destination": "A",
                "dep_time": "2026-01-15T09:20:00Z",
                "arr_time": "2026-01-15T09:50:00Z",
                "block_minutes": 30,
                "departure_delay_minutes": 0,
                "arrival_delay_minutes": 0,
                "notes": "",
            },
            {
                "option_id": "FO_T4_F2_CANCEL",
                "base_flight_id": "T4_F2",
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
        ]
    )
    columns["aircraft_strings"][0]["leg_option_ids"].append("FO_T4_FERRY_BA")
    columns["aircraft_strings"][0]["end_station"] = "A"
    for pairing in columns["crew_pairings"]:
        pairing["duties"][0]["segments"].append(
            {
                "segment_type": "deadhead",
                "flight_option_id": "FO_T4_F2_ORIG",
                "origin": None,
                "destination": None,
                "start_time": None,
                "end_time": None,
                "notes": "Deadhead requires T4_F2 to operate.",
            }
        )
        pairing["end_station"] = "A"

    with _gurobi() as solver:
        result = solve_integrated_fixed_column_oracle(
            scenario,
            columns,
            _request("toy_case_004"),
            _capacity("toy_case_004"),
            _costs(),
            solver,
            solver_parameters={"DualReductions": 0},
        )

    assert result.status is SolverStatus.INFEASIBLE
