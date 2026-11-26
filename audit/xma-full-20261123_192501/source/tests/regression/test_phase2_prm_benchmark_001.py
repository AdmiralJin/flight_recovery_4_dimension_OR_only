from pathlib import Path

import pytest

from backend.config import load_cost_config, load_passenger_capacity_profile
from backend.core import (
    PassengerRecoveryRequest,
    extract_required_operated_option_ids,
    solve_fixed_column_prm,
    solve_fixed_column_srm,
)
from backend.schemas.columns import RecoveryColumns
from backend.solver import GurobiAdapter, SolverStatus


ROOT = Path(__file__).parents[2]


@pytest.fixture
def costs():
    return load_cost_config(ROOT / "data" / "costs" / "phase2_test_costs_v1.json")


@pytest.fixture
def capacity():
    return load_passenger_capacity_profile(
        ROOT / "data" / "capacities" / "phase2_test_seat_capacity_v1.json"
    )


def _gurobi():
    available, reason = GurobiAdapter.availability()
    assert available, reason or "Gurobi Phase 2.5 PRM integration is unavailable"
    return GurobiAdapter(output_flag=False)


def test_phase2_prm_manual_reference_reproduces_passenger_metrics(
    costs,
    capacity,
    phase1_benchmark_001_data,
    phase1_columns_001_data,
    phase1_expected_001_data,
):
    reference = phase1_expected_001_data["reference_solution"]
    required = tuple(reference["selected_flight_option_by_flight"].values())
    request = PassengerRecoveryRequest(
        phase1_benchmark_001_data["scenario_id"],
        required,
        capacity.capacity_profile_id,
    )

    with _gurobi() as solver:
        result = solve_fixed_column_prm(
            phase1_benchmark_001_data,
            phase1_columns_001_data,
            request,
            capacity,
            costs,
            solver,
        )

    assert result.status is SolverStatus.OPTIMAL
    assert result.objective_value == pytest.approx(18000.0)
    diagnostics = result.diagnostics
    assert diagnostics["selected_itinerary_by_group"] == reference[
        "selected_passenger_itinerary_by_group"
    ]
    assert diagnostics["weighted_passenger_delay_minutes"] == 1800
    assert diagnostics["reaccommodated_passengers"] == 15
    assert diagnostics["unserved_passengers"] == 0
    assert diagnostics["capacity_violations"] == []
    assert diagnostics["unexpected_flight_options"] == []
    assert diagnostics["all_constraints_satisfied"]
    assert diagnostics["objective_breakdown"]["total"] == pytest.approx(
        result.objective_value
    )


def test_phase2_srm_to_prm_handoff_is_feasible_and_audited(
    costs, capacity, phase1_benchmark_001_data, phase1_columns_001_data
):
    with _gurobi() as solver:
        srm_result = solve_fixed_column_srm(
            phase1_benchmark_001_data,
            phase1_columns_001_data,
            costs,
            solver,
        )
    required = extract_required_operated_option_ids(
        srm_result,
        RecoveryColumns.model_validate(phase1_columns_001_data),
    )
    request = PassengerRecoveryRequest(
        phase1_benchmark_001_data["scenario_id"],
        required,
        capacity.capacity_profile_id,
    )

    with _gurobi() as solver:
        result = solve_fixed_column_prm(
            phase1_benchmark_001_data,
            phase1_columns_001_data,
            request,
            capacity,
            costs,
            solver,
        )

    assert srm_result.status is SolverStatus.OPTIMAL
    assert srm_result.objective_value == pytest.approx(70.0)
    assert result.status is SolverStatus.OPTIMAL
    assert result.objective_value == pytest.approx(45000.0)
    diagnostics = result.diagnostics
    assert diagnostics["weighted_passenger_delay_minutes"] == 1500
    assert diagnostics["unserved_passengers"] == 12
    assert diagnostics["selected_itinerary_by_group"]["P6"] == "PI_P6_UNSERVED"
    assert diagnostics["all_constraints_satisfied"]


def test_toy_case_003_is_a_hand_calculable_capacity_oracle(
    costs, toy_case_003_data, toy_case_003_columns_data
):
    capacity = load_passenger_capacity_profile(
        ROOT / "data" / "capacities" / "toy_case_003_capacity.json"
    )
    request = PassengerRecoveryRequest(
        toy_case_003_data["scenario_id"],
        tuple(capacity.seat_capacity_by_option_id),
        capacity.capacity_profile_id,
    )

    with _gurobi() as solver:
        result = solve_fixed_column_prm(
            toy_case_003_data,
            toy_case_003_columns_data,
            request,
            capacity,
            costs,
            solver,
        )

    assert result.status is SolverStatus.OPTIMAL
    assert result.objective_value == pytest.approx(3000.0)
    assert result.diagnostics["selected_itinerary_by_group"] == {
        "T3_P1": "PI_T3_P1_DIRECT",
        "T3_P2": "PI_T3_P2_ALT",
    }
    assert result.diagnostics["flight_seat_slack"] == {
        "FO_T3_F1_ORIG": 0.0,
        "FO_T3_F2_ORIG": 0.0,
        "FO_T3_F3_ORIG": 0.0,
    }
    assert result.diagnostics["weighted_passenger_delay_minutes"] == 300
    assert result.diagnostics["reaccommodated_passengers"] == 10
    assert result.diagnostics["unserved_passengers"] == 0
