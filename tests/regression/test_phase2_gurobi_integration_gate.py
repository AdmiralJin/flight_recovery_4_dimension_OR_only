from backend.solver import GurobiAdapter, SolverStatus, VariableType


def test_phase2_gurobi_integration_is_available_and_actually_executes():
    available, reason = GurobiAdapter.availability()
    assert available, reason or "Gurobi Phase 2 integration is unavailable"

    with GurobiAdapter(output_flag=False) as solver:
        solver.create_model("phase2_gurobi_integration_gate")
        variable = solver.add_variable(
            "integration_x", variable_type=VariableType.BINARY
        )
        solver.set_objective({variable: 1.0})
        outcome = solver.solve()

        assert solver.solver_version
        assert outcome.status is SolverStatus.OPTIMAL
        assert solver.get_variable_value(variable) == 0.0
