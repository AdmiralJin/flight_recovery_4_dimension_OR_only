from pathlib import Path

import pytest

from backend.config import load_cost_config
from backend.core import (
    AircraftRecoveryRequest,
    extract_required_operated_option_ids,
    solve_fixed_column_arm,
    solve_fixed_column_srm,
)
from backend.schemas.columns import RecoveryColumns
from backend.solver import GurobiAdapter, SolverStatus


@pytest.fixture
def costs():
    return load_cost_config(
        Path(__file__).parents[2] / "data" / "costs" / "phase2_test_costs_v1.json"
    )


def _gurobi():
    available, reason = GurobiAdapter.availability()
    if not available:
        pytest.skip(reason or "Gurobi is unavailable")
    return GurobiAdapter(output_flag=False)


def test_phase2_srm_to_arm_benchmark_exposes_fixed_column_shortage(
    costs, phase1_benchmark_001_data, phase1_columns_001_data
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
    request = AircraftRecoveryRequest(
        phase1_benchmark_001_data["scenario_id"], required
    )

    with _gurobi() as solver:
        arm_result = solve_fixed_column_arm(
            phase1_benchmark_001_data,
            phase1_columns_001_data,
            request,
            costs,
            solver,
            solver_parameters={"DualReductions": 0},
        )

    analysis = arm_result.diagnostics["fixed_column_analysis"]
    assert srm_result.status is SolverStatus.OPTIMAL
    assert srm_result.objective_value == pytest.approx(70.0)
    assert arm_result.status is SolverStatus.INFEASIBLE
    assert analysis["aircraft_without_schedule_compatible_string"] == ["AC4"]
    assert set(analysis["required_options_without_eligible_string"]) == {
        "FO_F3_ORIG",
        "FO_F11_ORIG",
        "FO_F12_ORIG",
    }


def test_phase2_arm_benchmark_manual_schedule_is_independently_audited(
    costs,
    phase1_benchmark_001_data,
    phase1_columns_001_data,
    phase1_expected_001_data,
):
    required = tuple(
        phase1_expected_001_data["reference_solution"][
            "selected_flight_option_by_flight"
        ].values()
    )
    request = AircraftRecoveryRequest(
        phase1_benchmark_001_data["scenario_id"], required
    )

    with _gurobi() as solver:
        result = solve_fixed_column_arm(
            phase1_benchmark_001_data,
            phase1_columns_001_data,
            request,
            costs,
            solver,
        )

    diagnostics = result.diagnostics
    assert result.status is SolverStatus.OPTIMAL
    assert result.objective_value == pytest.approx(0.0)
    assert diagnostics["all_constraints_satisfied"]
    assert diagnostics["constraint_violation_count"] == 0
    assert len(diagnostics["selected_string_by_aircraft"]) == len(
        phase1_benchmark_001_data["aircraft"]
    )
    assert set(diagnostics["covered_required_options"]) == set(required)
    assert diagnostics["uncovered_required_options"] == []
    assert diagnostics["duplicate_coverage"] == []
    assert diagnostics["unexpected_revenue_options"] == []
    assert all(item["satisfied"] for item in diagnostics["terminal_status"])
    assert all(item["satisfied"] for item in diagnostics["maintenance_status"])
    assert diagnostics["ferry_legs"] == []
    assert diagnostics["ferry_minutes"] == 0
    assert diagnostics["aircraft_reassignment_count"] == 2
    assert diagnostics["objective_breakdown"]["total"] == pytest.approx(
        result.objective_value
    )
