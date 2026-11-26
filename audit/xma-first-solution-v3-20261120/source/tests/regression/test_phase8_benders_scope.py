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
    build_recovery_scope,
    solve_fixed_column_benders,
    solve_integrated_fixed_column_oracle,
)
from backend.schemas.columns import RecoveryColumns
from backend.schemas.scenario import Scenario
from backend.solver import GurobiAdapter, SolverStatus


ROOT = Path(__file__).parents[2]


def test_scope_and_full_benders_match_their_integrated_oracles(
    toy_case_006_scope_data, toy_case_006_scope_columns_data
):
    available, reason = GurobiAdapter.availability()
    assert available, reason or "Gurobi is required for Phase 8 scope regression"
    scenario = Scenario.model_validate(toy_case_006_scope_data)
    columns = RecoveryColumns.model_validate(toy_case_006_scope_columns_data)
    scope = build_recovery_scope(scenario, columns)
    costs = load_cost_config(ROOT / "data" / "costs" / "phase2_test_costs_v1.json")
    capacity = load_passenger_capacity_profile(
        ROOT / "data" / "capacities" / "toy_case_006_scope_capacity.json"
    )
    config = load_fixed_column_benders_config(
        ROOT / "data" / "config" / "phase8_test_benders_v1.json"
    )
    request = IntegratedRecoveryRequest(
        scenario.scenario_id, costs.cost_profile_id, capacity.capacity_profile_id
    )

    benders_full = solve_fixed_column_benders(
        scenario,
        columns,
        capacity,
        costs,
        config,
        solver_factory=lambda: GurobiAdapter(output_flag=False),
    )
    benders_scope = solve_fixed_column_benders(
        scenario,
        columns,
        capacity,
        costs,
        config,
        solver_factory=lambda: GurobiAdapter(output_flag=False),
        scope=scope,
    )
    with GurobiAdapter(output_flag=False) as solver:
        integrated_full = solve_integrated_fixed_column_oracle(
            scenario, columns, request, capacity, costs, solver
        )
    with GurobiAdapter(output_flag=False) as solver:
        integrated_scope = solve_integrated_fixed_column_oracle(
            scenario, columns, request, capacity, costs, solver, scope=scope
        )

    assert benders_full.status is BendersStatus.OPTIMAL
    assert benders_scope.status is BendersStatus.OPTIMAL
    assert integrated_full.status is SolverStatus.OPTIMAL
    assert integrated_scope.status is SolverStatus.OPTIMAL
    assert benders_full.objective_value == pytest.approx(2040.0)
    assert benders_full.objective_value == pytest.approx(
        integrated_full.objective_value
    )
    assert benders_scope.objective_value == pytest.approx(
        integrated_scope.objective_value
    )
    audit = benders_scope.diagnostics["integrated_audit"]
    assert audit["all_constraints_satisfied"]
    assert audit["scope_fix_audit"]["all_constraints_satisfied"]
    assert (
        audit["scope_metrics"]["free_binary_candidates"]
        < audit["scope_metrics"]["total_binary_candidates"]
    )
    assert audit["selected_option_by_flight"]["S6_U1"] == "S6_UO1"
    assert audit["selected_string_by_aircraft"]["S6_AC2"] == "S6_AS2O"
    assert audit["selected_pairing_by_crew"]["S6_C2"] == "S6_CP2O"
    assert audit["selected_itinerary_by_group"]["S6_P2"] == "S6_PI2O"
