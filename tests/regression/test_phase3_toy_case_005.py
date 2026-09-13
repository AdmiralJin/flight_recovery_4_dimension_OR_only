from pathlib import Path

import pytest

from backend.config import load_cost_config, load_passenger_capacity_profile
from backend.core import IntegratedRecoveryRequest, solve_integrated_fixed_column_oracle
from backend.solver import GurobiAdapter, SolverStatus


ROOT = Path(__file__).parents[2]


def test_toy_case_005_passenger_cost_and_capacity_change_schedule_choice(
    toy_case_005_data, toy_case_005_columns_data
):
    available, reason = GurobiAdapter.availability()
    assert available, reason or "Gurobi is required for Phase 3 toy_case_005"
    costs = load_cost_config(ROOT / "data" / "costs" / "phase2_test_costs_v1.json")
    capacity = load_passenger_capacity_profile(
        ROOT / "data" / "capacities" / "toy_case_005_capacity.json"
    )
    request = IntegratedRecoveryRequest(
        "toy_case_005", costs.cost_profile_id, capacity.capacity_profile_id
    )

    with GurobiAdapter(output_flag=False) as solver:
        result = solve_integrated_fixed_column_oracle(
            toy_case_005_data, toy_case_005_columns_data, request, capacity, costs, solver
        )

    assert result.status is SolverStatus.OPTIMAL
    assert result.objective_value == pytest.approx(1010.0)
    assert result.diagnostics["selected_option_by_flight"] == {
        "T5_F1": "FO_T5_F1_D10"
    }
    assert result.diagnostics["selected_itinerary_by_group"] == {
        "T5_P1": "PI_T5_P1_D10"
    }
    seat_checks = result.diagnostics["cross_model_audit"]["seat_schedule"]
    assert all(item["satisfied"] for item in seat_checks)
    assert result.diagnostics["prm_audit"]["unserved_passengers"] == 0
