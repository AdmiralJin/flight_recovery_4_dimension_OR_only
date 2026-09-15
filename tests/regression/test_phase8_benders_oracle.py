from pathlib import Path

import pytest

from backend.config import (
    load_cost_config,
    load_fixed_column_benders_config,
    load_passenger_capacity_profile,
)
from backend.core import (
    BendersStatus,
    IntegratedRecoveryRequest,
    solve_fixed_column_benders,
    solve_integrated_fixed_column_oracle,
)
from backend.solver import GurobiAdapter, SolverStatus


ROOT = Path(__file__).parents[2]


def _costs():
    return load_cost_config(ROOT / "data" / "costs" / "phase2_test_costs_v1.json")


def _config():
    return load_fixed_column_benders_config(
        ROOT / "data" / "config" / "phase8_test_benders_v1.json"
    )


def _solve_pair(data, columns_data, capacity_name):
    costs = _costs()
    capacity = load_passenger_capacity_profile(
        ROOT / "data" / "capacities" / capacity_name
    )
    benders = solve_fixed_column_benders(
        data,
        columns_data,
        capacity,
        costs,
        _config(),
        solver_factory=lambda: GurobiAdapter(output_flag=False),
    )
    request = IntegratedRecoveryRequest(
        data["scenario_id"], costs.cost_profile_id, capacity.capacity_profile_id
    )
    with GurobiAdapter(output_flag=False) as solver:
        integrated = solve_integrated_fixed_column_oracle(
            data, columns_data, request, capacity, costs, solver
        )
    return benders, integrated


@pytest.mark.parametrize(
    ("data_fixture", "columns_fixture", "capacity_name", "expected"),
    (
        (
            "toy_case_004_data",
            "toy_case_004_columns_data",
            "toy_case_004_capacity.json",
            110.0,
        ),
        (
            "toy_case_005_data",
            "toy_case_005_columns_data",
            "toy_case_005_capacity.json",
            1010.0,
        ),
    ),
)
def test_existing_cross_model_cases_match_integrated_oracle(
    request, data_fixture, columns_fixture, capacity_name, expected
):
    available, reason = GurobiAdapter.availability()
    assert available, reason or "Gurobi is required for Phase 8 regression"
    benders, integrated = _solve_pair(
        request.getfixturevalue(data_fixture),
        request.getfixturevalue(columns_fixture),
        capacity_name,
    )
    assert benders.status is BendersStatus.OPTIMAL
    assert integrated.status is SolverStatus.OPTIMAL
    assert benders.objective_value == pytest.approx(expected)
    assert benders.objective_value == pytest.approx(integrated.objective_value)
    assert benders.diagnostics["integrated_audit"]["all_constraints_satisfied"]


def test_toy_case_010_exercises_feasibility_and_optimality_cuts(
    toy_case_010_fixed_column_benders_data,
    toy_case_010_fixed_column_benders_columns_data,
):
    available, reason = GurobiAdapter.availability()
    assert available, reason or "Gurobi is required for Phase 8 regression"
    benders, integrated = _solve_pair(
        toy_case_010_fixed_column_benders_data,
        toy_case_010_fixed_column_benders_columns_data,
        "toy_case_010_fixed_column_benders_capacity.json",
    )
    assert integrated.status is SolverStatus.OPTIMAL
    assert benders.status is BendersStatus.OPTIMAL
    assert benders.objective_value == pytest.approx(220.0)
    assert benders.objective_value == pytest.approx(integrated.objective_value)
    assert benders.diagnostics["cut_counts"]["feasibility"] >= 1
    assert benders.diagnostics["cut_counts"]["arm_optimality"] >= 1
    assert benders.diagnostics["cut_counts"]["crm_optimality"] >= 1
    assert benders.diagnostics["cut_counts"]["prm_optimality"] >= 1
    assert benders.iterations[0].infeasible_subproblems == ("arm",)
    assert benders.iterations[-1].absolute_gap == pytest.approx(0.0)
    assert benders.selected_flight_options == ("FO_T10_F1_D20",)
    assert benders.diagnostics["integrated_audit"]["all_constraints_satisfied"]
