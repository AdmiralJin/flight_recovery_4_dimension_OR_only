import pytest

from backend.solver import (HighsAdapter, GurobiAdapter, ConstraintSense as C,
                            ObjectiveSense as O, VariableType as V,
                            SolverStatus as S, SolverCapabilityError)
from backend.solver.base import SolverContractError


@pytest.mark.parametrize("factory", [HighsAdapter, GurobiAdapter])
def test_primal_dual_reduced_cost_and_objective_reset(factory):
    with factory() as s:
        s.create_model("duality")
        x, y = s.add_variable("x"), s.add_variable("y")
        c = s.add_linear_constraint({x: 1, y: 1}, C.GREATER_EQUAL, 2, name="demand")
        s.set_objective({x: 3, y: 5}, constant=-7)
        out = s.solve()
        assert out.status == S.OPTIMAL
        assert out.objective_value == pytest.approx(-1)
        assert out.best_bound == pytest.approx(-1)
        assert s.get_constraint_dual(c) == pytest.approx(3)
        assert s.get_reduced_cost(y) == pytest.approx(2)
        s.set_objective({y: 1}, constant=4)
        assert s.solve().objective_value == pytest.approx(4)


def test_mip_bounds_and_no_lp_duals():
    with HighsAdapter() as s:
        s.create_model("mip")
        x, y = (s.add_variable(k, variable_type=V.BINARY) for k in ("x", "y"))
        row = s.add_linear_constraint({x: 2, y: 1}, C.LESS_EQUAL, 2, name="cap")
        s.set_objective({x: 3, y: 2}, O.MAXIMIZE, constant=8)
        out = s.solve({"MIPGap": 0.0, "Threads": 1})
        assert out.status == S.OPTIMAL
        assert out.objective_value == pytest.approx(11)
        assert out.best_bound == pytest.approx(11)
        with pytest.raises(SolverCapabilityError):
            s.get_constraint_dual(row)


def test_infeasible_mutation_handles_and_empty_model():
    with HighsAdapter() as s:
        s.create_model("mutate")
        x = s.add_variable("x", upper_bound=1)
        s.set_objective({x: 1})
        s.solve()
        s.add_linear_constraint({x: 1}, C.GREATER_EQUAL, 2, name="impossible")
        with pytest.raises(SolverContractError):
            s.get_objective_value()
        out = s.solve()
        assert out.status == S.INFEASIBLE and out.objective_value is None
        with pytest.raises(SolverContractError):
            s.get_variable_value(x)
        s.create_model("empty")
        with pytest.raises(SolverContractError):
            s.set_objective({x: 1})
        s.set_objective({}, constant=9)
        assert s.solve().objective_value == pytest.approx(9)


def test_unbounded_and_time_limit_never_invent_incumbent():
    with HighsAdapter() as s:
        s.create_model("unbounded")
        x = s.add_variable("x", lower_bound=None)
        s.set_objective({x: -1})
        assert s.solve().status == S.UNBOUNDED
        s.create_model("limited")
        xs = [s.add_variable(str(i), variable_type=V.BINARY) for i in range(200)]
        s.add_linear_constraint({x: i+2 for i, x in enumerate(xs)}, C.LESS_EQUAL, 300, name="cap")
        s.set_objective({x: -i-1 for i, x in enumerate(xs)})
        out = s.solve({"TimeLimit": 0.0})
        if not out.has_solution:
            assert out.objective_value is None
            with pytest.raises(SolverContractError):
                s.get_variable_value(xs[0])
def test_contradictory_constant_row_is_infeasible():
    from backend.solver import HighsAdapter
    from backend.solver.base import ConstraintSense, SolverStatus
    with HighsAdapter() as solver:
        solver.create_model("constant_contradiction")
        solver.add_linear_constraint({}, ConstraintSense.EQUAL, 1, name="impossible")
        solver.set_objective({})
        result = solver.solve()
        assert result.status == SolverStatus.INFEASIBLE
        assert not result.has_solution
        assert result.objective_value is None and result.best_bound is None
