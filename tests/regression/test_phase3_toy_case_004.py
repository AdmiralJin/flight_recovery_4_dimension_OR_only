from pathlib import Path

import pytest

from backend.config import load_cost_config, load_passenger_capacity_profile
from backend.core import IntegratedRecoveryRequest, solve_integrated_fixed_column_oracle
from backend.solver import GurobiAdapter, SolverStatus


ROOT = Path(__file__).parents[2]


def test_toy_case_004_rejects_cheapest_aircraft_infeasible_schedule(
    toy_case_004_data, toy_case_004_columns_data
):
    available, reason = GurobiAdapter.availability()
    assert available, reason or "Gurobi is required for Phase 3 toy_case_004"
    costs = load_cost_config(ROOT / "data" / "costs" / "phase2_test_costs_v1.json")
    capacity = load_passenger_capacity_profile(
        ROOT / "data" / "capacities" / "toy_case_004_capacity.json"
    )
    request = IntegratedRecoveryRequest(
        "toy_case_004", costs.cost_profile_id, capacity.capacity_profile_id
    )

    with GurobiAdapter(output_flag=False) as solver:
        result = solve_integrated_fixed_column_oracle(
            toy_case_004_data, toy_case_004_columns_data, request, capacity, costs, solver
        )

    assert result.status is SolverStatus.OPTIMAL
    assert result.objective_value == pytest.approx(110.0)
    assert result.diagnostics["selected_option_by_flight"] == {
        "T4_F1": "FO_T4_F1_D10"
    }
    assert result.diagnostics["objective_breakdown"]["srm_total"] == pytest.approx(10.0)
    assert result.diagnostics["objective_breakdown"]["prm_total"] == pytest.approx(100.0)
    assert result.diagnostics["all_constraints_satisfied"]
