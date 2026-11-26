from pathlib import Path

import pytest

from backend.config import load_cost_config, load_passenger_capacity_profile
from backend.core import (
    INTEGRATED_MODEL_NAME,
    IntegratedRecoveryRequest,
    build_recovery_scope,
    solve_integrated_fixed_column_oracle,
)
from backend.schemas.columns import RecoveryColumns
from backend.schemas.scenario import Scenario
from backend.solver import GurobiAdapter, SolverStatus


ROOT = Path(__file__).parents[2]


def _costs():
    return load_cost_config(ROOT / "data" / "costs" / "phase2_test_costs_v1.json")


def _solve(data, columns_data, capacity_name, scope):
    scenario = Scenario.model_validate(data)
    columns = RecoveryColumns.model_validate(columns_data)
    costs = _costs()
    capacity = load_passenger_capacity_profile(
        ROOT / "data" / "capacities" / capacity_name
    )
    request = IntegratedRecoveryRequest(
        scenario.scenario_id, costs.cost_profile_id, capacity.capacity_profile_id
    )
    with GurobiAdapter(output_flag=False) as solver:
        return solve_integrated_fixed_column_oracle(
            data,
            columns_data,
            request,
            capacity,
            costs,
            solver,
            scope=scope,
        )


def test_scope_toy_reduces_free_decisions_without_changing_optimum(
    toy_case_006_scope_data, toy_case_006_scope_columns_data
):
    available, reason = GurobiAdapter.availability()
    assert available, reason or "Gurobi is required for Phase 4 regression"
    scenario = Scenario.model_validate(toy_case_006_scope_data)
    columns = RecoveryColumns.model_validate(toy_case_006_scope_columns_data)
    scope = build_recovery_scope(scenario, columns)

    full = _solve(
        toy_case_006_scope_data,
        toy_case_006_scope_columns_data,
        "toy_case_006_scope_capacity.json",
        None,
    )
    limited = _solve(
        toy_case_006_scope_data,
        toy_case_006_scope_columns_data,
        "toy_case_006_scope_capacity.json",
        scope,
    )

    assert full.model_name == INTEGRATED_MODEL_NAME
    assert limited.model_name == INTEGRATED_MODEL_NAME
    assert full.status is SolverStatus.OPTIMAL
    assert limited.status is SolverStatus.OPTIMAL
    assert limited.objective_value == pytest.approx(full.objective_value, abs=1e-6)
    assert limited.objective_value == pytest.approx(2040.0)
    assert limited.diagnostics["all_constraints_satisfied"]
    assert limited.diagnostics["cross_model_audit"]["all_constraints_satisfied"]
    assert limited.diagnostics["scope_fix_audit"]["all_constraints_satisfied"]
    metrics = limited.diagnostics["scope_metrics"]
    assert metrics["scoped_flights"] < metrics["total_flights"]
    assert metrics["free_binary_candidates"] < metrics["total_binary_candidates"]
    assert limited.diagnostics["selected_option_by_flight"]["S6_U1"] == "S6_UO1"
    assert limited.diagnostics["selected_string_by_aircraft"]["S6_AC2"] == "S6_AS2O"
    assert limited.diagnostics["selected_pairing_by_crew"]["S6_C2"] == "S6_CP2O"
    assert limited.diagnostics["selected_itinerary_by_group"]["S6_P2"] == "S6_PI2O"


def test_phase1_benchmark_full_closure_preserves_phase3_optimum(
    phase1_benchmark_001_data, phase1_columns_001_data
):
    available, reason = GurobiAdapter.availability()
    assert available, reason or "Gurobi is required for Phase 4 regression"
    scenario = Scenario.model_validate(phase1_benchmark_001_data)
    columns = RecoveryColumns.model_validate(phase1_columns_001_data)
    scope = build_recovery_scope(scenario, columns)

    full = _solve(
        phase1_benchmark_001_data,
        phase1_columns_001_data,
        "phase2_test_seat_capacity_v1.json",
        None,
    )
    limited = _solve(
        phase1_benchmark_001_data,
        phase1_columns_001_data,
        "phase2_test_seat_capacity_v1.json",
        scope,
    )

    assert full.status is SolverStatus.OPTIMAL
    assert limited.status is SolverStatus.OPTIMAL
    assert full.objective_value == pytest.approx(18080.0)
    assert limited.objective_value == pytest.approx(full.objective_value, abs=1e-6)
    assert limited.diagnostics["all_constraints_satisfied"]
    assert limited.diagnostics["scope_metrics"]["free_binary_ratio"] == 1.0
