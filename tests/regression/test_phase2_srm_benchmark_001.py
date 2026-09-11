from pathlib import Path

import pytest

from backend.config.costs import load_cost_config
from backend.core.srm import solve_fixed_column_srm
from backend.solver import GurobiAdapter, SolverStatus


def test_phase2_srm_benchmark_001_is_independently_audited(
    phase1_benchmark_001_data, phase1_columns_001_data
):
    available, reason = GurobiAdapter.availability()
    if not available:
        pytest.skip(reason or "Gurobi is unavailable")
    costs = load_cost_config(
        Path(__file__).parents[2] / "data" / "costs" / "phase2_test_costs_v1.json"
    )

    with GurobiAdapter(output_flag=False) as solver:
        result = solve_fixed_column_srm(
            phase1_benchmark_001_data,
            phase1_columns_001_data,
            costs,
            solver,
        )

    diagnostics = result.diagnostics
    selected = diagnostics["selected_option_by_flight"]
    assert result.status is SolverStatus.OPTIMAL
    assert len(selected) == len(phase1_benchmark_001_data["flights"])
    assert diagnostics["all_constraints_satisfied"]
    assert diagnostics["constraint_violation_count"] == 0
    assert all(
        item["lhs"] == pytest.approx(1.0)
        for item in diagnostics["flight_coverage_constraints"]
    )
    assert all(item["satisfied"] for item in diagnostics["strategic_constraints"])
    assert all(item["satisfied"] for item in diagnostics["market_proxy_constraints"])
    assert all(item["satisfied"] for item in diagnostics["arrival_capacity_load"])
    assert all(item["satisfied"] for item in diagnostics["departure_capacity_load"])
    assert all(item["satisfied"] for item in diagnostics["gate_inventory"])

    b_departure = next(
        item
        for item in diagnostics["departure_capacity_load"]
        if item["capacity_interval"]["airport"] == "B"
    )
    assert b_departure["lhs"] <= b_departure["rhs"]
    assert selected["F2"] == "FO_F2_D50"
    assert result.objective_value == pytest.approx(
        diagnostics["objective_breakdown"]["total"]
    )
    assert result.objective_value == pytest.approx(
        sum(
            value
            for key, value in diagnostics["objective_breakdown"].items()
            if key != "total"
        )
    )
