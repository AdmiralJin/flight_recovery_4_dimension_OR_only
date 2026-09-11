from pathlib import Path

import pytest

from backend.config import load_cost_config
from backend.core import (
    CrewRecoveryRequest,
    extract_required_operated_option_ids,
    solve_fixed_column_crm,
    solve_fixed_column_srm,
)
from backend.schemas.columns import RecoveryColumns
from backend.schemas.model_result import ModelSolveResult
from backend.solver import GurobiAdapter, SolverStatus


@pytest.fixture
def costs():
    return load_cost_config(
        Path(__file__).parents[2] / "data" / "costs" / "phase2_test_costs_v1.json"
    )


def _gurobi():
    available, reason = GurobiAdapter.availability()
    assert available, reason or "Gurobi Phase 2.4 CRM integration is unavailable"
    return GurobiAdapter(output_flag=False)


def test_phase2_srm_to_crm_benchmark_is_independently_audited(
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
    request = CrewRecoveryRequest(phase1_benchmark_001_data["scenario_id"], required)

    with _gurobi() as solver:
        crm_result = solve_fixed_column_crm(
            phase1_benchmark_001_data,
            phase1_columns_001_data,
            request,
            costs,
            solver,
            solver_parameters={"DualReductions": 0},
        )

    assert srm_result.status is SolverStatus.OPTIMAL
    assert srm_result.objective_value == pytest.approx(70.0)
    assert crm_result.status is SolverStatus.OPTIMAL
    diagnostics = crm_result.diagnostics
    assert diagnostics["all_constraints_satisfied"]
    assert set(diagnostics["covered_required_options"]) == set(required)
    assert diagnostics["uncovered_required_options"] == []
    assert diagnostics["duplicate_operating_coverage"] == []
    assert diagnostics["unexpected_operating_options"] == []
    assert diagnostics["unexpected_deadhead_options"] == []
    assert (
        diagnostics["fixed_column_analysis"]["crew_without_schedule_compatible_pairing"]
        == []
    )
    assert (
        diagnostics["fixed_column_analysis"][
            "required_options_without_eligible_operating_pairing"
        ]
        == []
    )


def test_phase2_crm_manual_schedule_is_independently_audited(
    costs,
    phase1_benchmark_001_data,
    phase1_columns_001_data,
    phase1_expected_001_data,
):
    reference = phase1_expected_001_data["reference_solution"]
    required = tuple(reference["selected_flight_option_by_flight"].values())
    request = CrewRecoveryRequest(phase1_benchmark_001_data["scenario_id"], required)

    with _gurobi() as solver:
        result = solve_fixed_column_crm(
            phase1_benchmark_001_data,
            phase1_columns_001_data,
            request,
            costs,
            solver,
        )

    diagnostics = result.diagnostics
    assert result.status is SolverStatus.OPTIMAL
    assert result.objective_value == pytest.approx(0.0)
    assert (
        diagnostics["selected_pairing_by_crew"]
        == reference["selected_crew_pairing_by_crew"]
    )
    assert diagnostics["all_constraints_satisfied"]
    assert diagnostics["constraint_violation_count"] == 0
    assert set(diagnostics["covered_required_options"]) == set(required)
    assert diagnostics["uncovered_required_options"] == []
    assert diagnostics["duplicate_operating_coverage"] == []
    assert diagnostics["unexpected_operating_options"] == []
    assert diagnostics["unexpected_deadhead_options"] == []
    assert all(item["satisfied"] for item in diagnostics["terminal_status"])
    assert diagnostics["crew_legality_status"]["validated_before_model_build"]
    assert diagnostics["deadhead_legs"] == []
    assert diagnostics["deadhead_minutes"] == 0
    assert diagnostics["crew_reassignment_count"] == 0
    assert diagnostics["objective_breakdown"]["total"] == pytest.approx(
        result.objective_value
    )


def test_phase2_cancelled_flight_is_excluded_before_crm_coverage(
    costs,
    phase1_benchmark_001_data,
    phase1_columns_001_data,
    phase1_expected_001_data,
):
    selected = dict(
        phase1_expected_001_data["reference_solution"][
            "selected_flight_option_by_flight"
        ]
    )
    selected["F3"] = "FO_F3_CANCEL"
    srm_result = ModelSolveResult(
        model_name="fixed_column_srm",
        scenario_id=phase1_benchmark_001_data["scenario_id"],
        status=SolverStatus.OPTIMAL,
        objective_value=0,
        best_bound=0,
        mip_gap=0,
        runtime_seconds=0,
        selected_variables={},
        continuous_variables={},
        solver_name="contract-fixture",
        solver_version="1",
        raw_status=2,
        termination_reason="optimal",
        diagnostics={"selected_option_by_flight": selected},
    )
    required = extract_required_operated_option_ids(
        srm_result,
        RecoveryColumns.model_validate(phase1_columns_001_data),
    )
    assert "FO_F3_CANCEL" not in required

    with _gurobi() as solver:
        result = solve_fixed_column_crm(
            phase1_benchmark_001_data,
            phase1_columns_001_data,
            CrewRecoveryRequest(phase1_benchmark_001_data["scenario_id"], required),
            costs,
            solver,
            solver_parameters={"DualReductions": 0},
        )

    # The request is valid; infeasibility is the expected fixed-pairing shortage,
    # not a mistaken attempt to crew the cancelled option.
    assert result.status is SolverStatus.INFEASIBLE
    assert result.diagnostics["required_operated_option_ids"] == list(required)
