import gurobipy as gp
from gurobipy import GRB
import numpy as np
import pytest

from backend.business.xma.model import new_model


@pytest.fixture
def model():
    m, env = new_model("adapter_equivalence")
    m.highs = True
    yield m
    m.dispose()
    env.dispose()


def assert_cold_equivalent(m):
    m.optimize()
    status, obj, duals = m.Status, m.ObjVal, dict(m.duals)
    # Independently optimize the native model (different solver and translation).
    m.native.optimize()
    assert status == m.native.Status
    if status == GRB.OPTIMAL:
        assert obj == pytest.approx(m.native.ObjVal)
        if not m.IsMIP:
            a = m.native.getA()
            cost = np.asarray(m.native.getAttr("Obj"))
            pi = np.asarray([duals[r.ConstrName] for r in m.native.getConstrs()])
            rc = cost - a.T @ pi
            for v, reduced in zip(m.native.getVars(), rc):
                val = m.value(v)
                assert val >= v.LB - 1e-6 and val <= v.UB + 1e-6
                if val > v.LB + 1e-6:
                    assert reduced <= 1e-6
                if val < v.UB - 1e-6:
                    assert reduced >= -1e-6


def test_batch_translation_mixed_rows_bounds_integrality_and_constant(model):
    x = model.addVar(lb=-2, ub=7, vtype=GRB.INTEGER, name="x")
    y = model.addVar(lb=0, ub=9, name="y")
    model.addConstr(2*x + 3*y >= 4, name="lower")
    model.addConstr(x - y <= 2, name="upper")
    model.addConstr(x + y == 3, name="equal")
    model.setObjective(-x + 2*y + 17)
    problem = model._problem()
    np.testing.assert_array_equal(problem[2].toarray(), [[2, 3], [1, -1], [1, 1]])
    np.testing.assert_array_equal(problem[-1], [1, 0])
    assert_cold_equivalent(model)


def test_added_column_rhs_cost_bounds_phase_switch_reuse_basis(model):
    x = model.addVar(lb=0, obj=5, name="x")
    r = model.addConstr(x >= 2, name="demand")
    assert_cold_equivalent(model)
    solver = model._lp_solver
    y = model.addVar(lb=0, obj=3, column=gp.Column([1], [r]), name="y")
    assert_cold_equivalent(model)
    assert model._lp_solver is solver and solver.getBasis().valid
    r.RHS = 3
    x.Obj = 2
    y.UB = 0
    model.native.ObjCon = 11
    assert_cold_equivalent(model)
    assert model.reuse_statistics == {"lp_rebuilds": 1, "lp_reuses": 2, "lp_added_columns": 1}
    assert model.ObjVal == pytest.approx(17)


def test_structural_changes_rebuild_and_infeasible_lp_clears_stale_duals(model):
    x = model.addVar(lb=0, ub=2, obj=1, name="x")
    r = model.addConstr(x >= 1, name="r")
    assert_cold_equivalent(model)
    model.chgCoeff(r, x, 2)
    assert_cold_equivalent(model)
    assert model.reuse_statistics["lp_rebuilds"] == 2
    r.RHS = 10
    assert_cold_equivalent(model)
    assert model.Status == GRB.INFEASIBLE and model.duals == {} and model.primal == {}
    model.remove(r)
    model.addConstr(x <= 1, name="replacement")
    assert_cold_equivalent(model)
    assert model.reuse_statistics["lp_rebuilds"] == 3


def test_memory_failure_never_retries_another_high_memory_path(model, monkeypatch):
    model.addVar(name="x")
    def fail(_):
        raise MemoryError("allocation")
    monkeypatch.setattr(model, "_solve_highspy", fail)
    monkeypatch.setattr(model, "_solve_scipy", lambda _: pytest.fail("must not retry"))
    with pytest.raises(MemoryError):
        model.optimize()


def test_native_lp_cancellation_works_during_simplex(model):
    rng = np.random.default_rng(20261106)
    variables = [model.addVar(lb=0, ub=1, obj=-float(c), name=f"x{i}") for i, c in enumerate(rng.uniform(1, 10, 400))]
    for i in range(200):
        ids = rng.choice(400, 40, replace=False)
        model.addConstr(gp.quicksum(float(c)*variables[j] for j, c in zip(ids, rng.uniform(.1, 1, 40))) <= 8, name=f"r{i}")
    checks = []
    def stop():
        checks.append(1)
        return len(checks) > 2
    model.cancel_check = stop
    model.optimize()
    assert len(checks) > 2 and model.Status == GRB.INTERRUPTED and model.duals == {}
