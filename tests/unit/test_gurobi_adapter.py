import pytest

from backend.solver import (
    ConstraintSense,
    GurobiAdapter,
    ObjectiveSense,
    SolverCapabilityError,
    SolverStatus,
    VariableType,
)


@pytest.fixture
def adapter():
    available, reason = GurobiAdapter.availability()
    if not available:
        pytest.skip(reason or "Gurobi is unavailable")
    with GurobiAdapter(output_flag=False) as instance:
        yield instance


def test_gurobi_capabilities_and_version_are_explicit(adapter):
    assert adapter.solver_name == "Gurobi"
    assert adapter.solver_version == "13.0.3"
    assert adapter.capabilities.supports_mip
    assert adapter.capabilities.supports_lp_duals
    assert adapter.capabilities.supports_reduced_costs
    assert adapter.capabilities.supports_mip_gap
    assert adapter.capabilities.supports_objective_bound


def test_gurobi_lp_matches_analytical_primal_dual_and_reduced_cost(adapter):
    adapter.create_model("analytical_lp")
    x = adapter.add_variable("x")
    y = adapter.add_variable("y")
    demand = adapter.add_linear_constraint(
        {x: 1.0, y: 1.0},
        ConstraintSense.GREATER_EQUAL,
        1.0,
        name="demand",
    )
    adapter.set_objective({x: 1.0, y: 2.0})

    outcome = adapter.solve({"Method": 0})

    assert outcome.status is SolverStatus.OPTIMAL
    assert outcome.raw_status == 2
    assert outcome.termination_reason == "optimal"
    assert outcome.objective_value == pytest.approx(1.0)
    assert outcome.best_bound == pytest.approx(1.0)
    assert outcome.mip_gap is None
    assert adapter.get_variable_value(x) == pytest.approx(1.0)
    assert adapter.get_variable_value(y) == pytest.approx(0.0)
    assert adapter.get_constraint_dual(demand) == pytest.approx(1.0)
    assert adapter.get_reduced_cost(x) == pytest.approx(0.0)
    assert adapter.get_reduced_cost(y) == pytest.approx(1.0)
    assert adapter.get_objective_value() == pytest.approx(1.0)
    assert adapter.get_status() is SolverStatus.OPTIMAL
    assert adapter.get_runtime_seconds() >= 0.0


def test_gurobi_binary_mip_matches_analytical_solution_bound_and_gap(adapter):
    adapter.create_model("analytical_mip")
    x = adapter.add_variable("x", variable_type=VariableType.BINARY)
    y = adapter.add_variable("y", variable_type=VariableType.BINARY)
    adapter.add_linear_constraint(
        {x: 2.0, y: 1.0},
        ConstraintSense.LESS_EQUAL,
        2.0,
        name="capacity",
    )
    adapter.set_objective(
        {x: 3.0, y: 2.0}, ObjectiveSense.MAXIMIZE
    )

    outcome = adapter.solve()

    assert outcome.status is SolverStatus.OPTIMAL
    assert outcome.objective_value == pytest.approx(3.0)
    assert outcome.best_bound == pytest.approx(3.0)
    assert outcome.mip_gap == pytest.approx(0.0)
    assert adapter.get_variable_value(x) == pytest.approx(1.0)
    assert adapter.get_variable_value(y) == pytest.approx(0.0)
    assert adapter.get_best_bound() == pytest.approx(3.0)
    assert adapter.get_mip_gap() == pytest.approx(0.0)
    assert outcome.runtime_seconds >= 0.0
    with pytest.raises(SolverCapabilityError, match="unavailable for a MIP"):
        adapter.get_reduced_cost(x)


def test_gurobi_infeasible_and_unbounded_statuses_have_no_fake_solution(adapter):
    adapter.create_model("infeasible_lp")
    x = adapter.add_variable("x", upper_bound=1.0)
    adapter.add_linear_constraint(
        {x: 1.0}, ConstraintSense.GREATER_EQUAL, 2.0, name="impossible"
    )
    infeasible = adapter.solve({"DualReductions": 0})

    assert infeasible.status is SolverStatus.INFEASIBLE
    assert infeasible.objective_value is None
    assert infeasible.mip_gap is None

    adapter.create_model("unbounded_lp")
    x = adapter.add_variable("x")
    adapter.set_objective({x: -1.0})
    unbounded = adapter.solve({"DualReductions": 0})

    assert unbounded.status is SolverStatus.UNBOUNDED
    assert unbounded.objective_value is None
    assert unbounded.mip_gap is None


def test_gurobi_api_error_is_reported_as_error_not_infeasible(adapter):
    adapter.create_model("bad_parameter")
    adapter.add_variable("x")

    outcome = adapter.solve({"DefinitelyNotAParameter": 1})

    assert outcome.status is SolverStatus.ERROR
    assert outcome.termination_reason == "solver_error"
    assert outcome.objective_value is None
    assert "error_message" in outcome.diagnostics
