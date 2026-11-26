from copy import deepcopy

import pytest
from pydantic import ValidationError

from backend.schemas.model_result import ModelSolveResult
from backend.solver.base import SolverOutcome, SolverStatus


def _result_data(status="optimal"):
    return {
        "model_name": "contract_test",
        "scenario_id": "scenario_001",
        "status": status,
        "objective_value": 7.0,
        "best_bound": 7.0,
        "mip_gap": 0.0,
        "runtime_seconds": 0.01,
        "selected_variables": {"x": 1.0},
        "continuous_variables": {"flow": 2.5},
        "solver_name": "Gurobi",
        "solver_version": "13.0.3",
        "raw_status": 2,
        "termination_reason": "optimal",
        "diagnostics": {"node_count": 0},
    }


def test_optimal_model_result_round_trips_without_using_recovery_expected():
    result = ModelSolveResult.model_validate(_result_data())

    restored = ModelSolveResult.model_validate_json(result.model_dump_json())
    assert restored == result
    assert result.status is SolverStatus.OPTIMAL


def test_feasible_model_result_preserves_incumbent_bound_and_reason():
    data = _result_data("feasible")
    data.update(
        objective_value=8.0,
        best_bound=7.0,
        mip_gap=0.125,
        raw_status=9,
        termination_reason="time_limit",
    )

    result = ModelSolveResult.model_validate(data)

    assert result.status is SolverStatus.FEASIBLE
    assert result.objective_value == 8.0
    assert result.best_bound == 7.0
    assert result.mip_gap == 0.125


@pytest.mark.parametrize(
    "status", ["infeasible", "unbounded", "infeasible_or_unbounded", "error"]
)
def test_no_solution_statuses_do_not_require_or_allow_fake_solution(status):
    data = _result_data(status)
    data.update(
        objective_value=None,
        best_bound=None,
        mip_gap=None,
        selected_variables={},
        continuous_variables={},
    )

    result = ModelSolveResult.model_validate(data)

    assert result.objective_value is None
    assert result.selected_variables == {}
    assert result.continuous_variables == {}


def test_no_solution_result_rejects_objective_or_variable_values():
    data = _result_data("infeasible")
    data.update(best_bound=None, mip_gap=None)

    with pytest.raises(ValidationError, match="objective_value=null"):
        ModelSolveResult.model_validate(data)

    data["objective_value"] = None
    with pytest.raises(ValidationError, match="cannot contain variable values"):
        ModelSolveResult.model_validate(data)


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("objective_value",), float("nan")),
        (("runtime_seconds",), float("inf")),
        (("selected_variables", "x"), float("-inf")),
    ],
)
def test_model_result_rejects_non_finite_numbers(path, value):
    data = deepcopy(_result_data())
    target = data
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value

    with pytest.raises(ValidationError, match="finite"):
        ModelSolveResult.model_validate(data)


def test_model_result_rejects_unknown_fields():
    data = _result_data()
    data["recovery_solution"] = {"not": "part of this contract"}

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        ModelSolveResult.model_validate(data)


def test_model_result_can_be_built_from_solver_outcome():
    outcome = SolverOutcome(
        model_name="tiny_mip",
        status=SolverStatus.OPTIMAL,
        raw_status=2,
        termination_reason="optimal",
        runtime_seconds=0.1,
        objective_value=3.0,
        best_bound=3.0,
        mip_gap=0.0,
        diagnostics={"solution_count": 1},
    )

    result = ModelSolveResult.from_solver_outcome(
        scenario_id="scenario_001",
        outcome=outcome,
        solver_name="Gurobi",
        solver_version="13.0.3",
        selected_variables={"x": 1.0},
    )

    assert result.status is SolverStatus.OPTIMAL
    assert result.selected_variables == {"x": 1.0}
