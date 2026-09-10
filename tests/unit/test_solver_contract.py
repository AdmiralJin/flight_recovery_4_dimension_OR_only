from dataclasses import FrozenInstanceError

import pytest

from backend.solver.base import SolverCapabilities, SolverOutcome, SolverStatus
from backend.solver.gurobi import normalize_gurobi_status


def test_solver_capabilities_are_explicit_and_immutable():
    capabilities = SolverCapabilities(
        supports_mip=True,
        supports_lp_duals=True,
        supports_reduced_costs=True,
        supports_mip_gap=True,
        supports_objective_bound=True,
    )

    assert capabilities.supports_lp_duals
    with pytest.raises(FrozenInstanceError):
        capabilities.supports_mip = False  # type: ignore[misc]


@pytest.mark.parametrize(
    ("raw_status", "solution_count", "expected"),
    [
        (2, 1, SolverStatus.OPTIMAL),
        (3, 0, SolverStatus.INFEASIBLE),
        (4, 0, SolverStatus.INFEASIBLE_OR_UNBOUNDED),
        (5, 0, SolverStatus.UNBOUNDED),
        (9, 1, SolverStatus.FEASIBLE),
        (8, 0, SolverStatus.NO_SOLUTION),
        (12, 0, SolverStatus.ERROR),
        (999, 0, SolverStatus.ERROR),
    ],
)
def test_gurobi_raw_status_is_normalized(
    raw_status, solution_count, expected
):
    assert normalize_gurobi_status(raw_status, solution_count) is expected


def test_solver_outcome_distinguishes_feasible_from_optimal():
    outcome = SolverOutcome(
        model_name="limited_mip",
        status=SolverStatus.FEASIBLE,
        raw_status=9,
        termination_reason="time_limit",
        runtime_seconds=1.0,
        objective_value=8.0,
        best_bound=7.0,
        mip_gap=0.125,
        diagnostics={},
    )

    assert outcome.has_solution
    assert outcome.status is not SolverStatus.OPTIMAL
