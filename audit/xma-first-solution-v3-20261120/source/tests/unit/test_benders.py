from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.config import (
    FixedColumnBendersConfigError,
    load_cost_config,
    load_fixed_column_benders_config,
    load_passenger_capacity_profile,
)
from backend.core import (
    BendersCut,
    BendersCutType,
    BendersStatus,
    BendersSubproblem,
    FixedColumnBendersError,
    audit_benders_cut,
    build_fixed_column_benders_master,
    build_recovery_scope,
    build_scope_restricted_columns,
    compute_benders_big_m,
    schedule_signature,
    solve_fixed_column_benders,
)
from backend.schemas.columns import RecoveryColumns
from backend.schemas.scenario import Scenario
from backend.solver import GurobiAdapter, SolverStatus


ROOT = Path(__file__).parents[2]


def _config():
    return load_fixed_column_benders_config(
        ROOT / "data" / "config" / "phase8_test_benders_v1.json"
    )


def _costs():
    return load_cost_config(ROOT / "data" / "costs" / "phase2_test_costs_v1.json")


def _toy10_capacity():
    return load_passenger_capacity_profile(
        ROOT / "data" / "capacities" / "toy_case_010_fixed_column_benders_capacity.json"
    )


def _require_gurobi():
    available, reason = GurobiAdapter.availability()
    assert available, reason or "Gurobi is required for Phase 8 tests"


def test_benders_config_is_strict_frozen_and_versioned(tmp_path):
    config = _config()
    assert config.algorithm == "logic_based_fixed_column_benders"
    assert config.max_iterations == 500
    with pytest.raises(ValidationError):
        config.max_iterations = 2

    raw = config.model_dump(mode="json")
    raw["enable_arm"] = 1
    with pytest.raises(ValidationError):
        type(config).model_validate(raw)
    raw = config.model_dump(mode="json")
    raw["schema_version"] = "2.0.0"
    with pytest.raises(ValidationError):
        type(config).model_validate(raw)
    raw = config.model_dump(mode="json")
    raw["extra"] = "forbidden"
    with pytest.raises(ValidationError):
        type(config).model_validate(raw)

    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text(
        '{"schema_version":"1.0.0","schema_version":"1.0.0"}',
        encoding="utf-8",
    )
    with pytest.raises(FixedColumnBendersConfigError, match="duplicate JSON key"):
        load_fixed_column_benders_config(duplicate)


def test_schedule_signature_is_deterministic_and_exact(
    toy_case_010_fixed_column_benders_data,
    toy_case_010_fixed_column_benders_columns_data,
):
    scenario = Scenario.model_validate(toy_case_010_fixed_column_benders_data)
    columns = RecoveryColumns.model_validate(
        toy_case_010_fixed_column_benders_columns_data
    )
    values = {
        "FO_T10_F1_ORIG": 0.0,
        "FO_T10_F1_D10": 0.0,
        "FO_T10_F1_D20": 1.0,
    }
    reversed_columns = columns.model_copy(
        update={"flight_options": list(reversed(columns.flight_options))}
    )
    assert schedule_signature(scenario, columns, values) == ("FO_T10_F1_D20",)
    assert schedule_signature(scenario, reversed_columns, values) == ("FO_T10_F1_D20",)
    with pytest.raises(FixedColumnBendersError, match="exactly one"):
        schedule_signature(
            scenario,
            columns,
            {**values, "FO_T10_F1_D10": 1.0},
        )
    with pytest.raises(FixedColumnBendersError, match="x IDs differ"):
        schedule_signature(scenario, columns, {"FO_T10_F1_D20": 1.0})


def test_cut_algebra_identity_and_validation():
    visited = ("A", "C")
    feasibility = BendersCut(BendersCutType.FEASIBILITY, None, visited)
    assert not audit_benders_cut(feasibility, ("A", "C"))["satisfied"]
    assert audit_benders_cut(feasibility, ("B", "C"))["satisfied"]
    assert audit_benders_cut(feasibility, ("A", "D"))["satisfied"]
    assert audit_benders_cut(feasibility, ("B", "D"))["satisfied"]

    optimality = BendersCut(
        BendersCutType.OPTIMALITY,
        BendersSubproblem.PRM,
        visited,
        recourse_value=100.0,
        big_m=500.0,
    )
    tight = audit_benders_cut(optimality, visited, theta_value=100.0)
    changed = audit_benders_cut(optimality, ("B", "C"), theta_value=0.0)
    assert tight["required_theta"] == pytest.approx(100.0)
    assert tight["satisfied"]
    assert changed["required_theta"] == pytest.approx(-400.0)
    assert changed["satisfied"]
    assert (
        optimality.cut_id
        == BendersCut(
            BendersCutType.OPTIMALITY,
            BendersSubproblem.PRM,
            visited,
            100.0,
            500.0,
        ).cut_id
    )
    with pytest.raises(FixedColumnBendersError, match="at least recourse_value"):
        BendersCut(
            BendersCutType.OPTIMALITY,
            BendersSubproblem.ARM,
            visited,
            10.0,
            9.0,
        )


def test_scope_restricted_view_keeps_original_only_for_out_of_scope_owners(
    toy_case_006_scope_data, toy_case_006_scope_columns_data
):
    scenario = Scenario.model_validate(toy_case_006_scope_data)
    columns = RecoveryColumns.model_validate(toy_case_006_scope_columns_data)
    scope = build_recovery_scope(scenario, columns)
    restricted = build_scope_restricted_columns(scenario, columns, scope)

    assert restricted is not columns
    assert [
        item.string_id
        for item in restricted.aircraft_strings
        if item.aircraft_id == "S6_AC2"
    ] == ["S6_AS2O"]
    assert [
        item.pairing_id for item in restricted.crew_pairings if item.crew_id == "S6_C2"
    ] == ["S6_CP2O"]
    assert [
        item.itinerary_id
        for item in restricted.passenger_itineraries
        if item.pax_group_id == "S6_P2"
    ] == ["S6_PI2O"]
    assert columns == RecoveryColumns.model_validate(toy_case_006_scope_columns_data)


def test_big_m_is_deterministic_and_bounds_owner_recourse(
    toy_case_010_fixed_column_benders_data,
    toy_case_010_fixed_column_benders_columns_data,
):
    scenario = Scenario.model_validate(toy_case_010_fixed_column_benders_data)
    columns = RecoveryColumns.model_validate(
        toy_case_010_fixed_column_benders_columns_data
    )
    first = compute_benders_big_m(scenario, columns, _costs())
    second = compute_benders_big_m(scenario, columns, _costs())
    assert first == second
    assert first.arm == 0.0
    assert first.crm == 0.0
    assert first.prm == 2500.0
    assert first.prm >= 200.0

    invalid = columns.model_copy(update={"aircraft_strings": []})
    with pytest.raises(FixedColumnBendersError, match="has no candidate"):
        compute_benders_big_m(scenario, invalid, _costs())


def test_master_applies_theta_cuts_and_deduplicates(
    toy_case_010_fixed_column_benders_data,
    toy_case_010_fixed_column_benders_columns_data,
):
    _require_gurobi()
    scenario = Scenario.model_validate(toy_case_010_fixed_column_benders_data)
    columns = RecoveryColumns.model_validate(
        toy_case_010_fixed_column_benders_columns_data
    )
    cuts = (
        BendersCut(BendersCutType.FEASIBILITY, None, ("FO_T10_F1_ORIG",)),
        BendersCut(BendersCutType.FEASIBILITY, None, ("FO_T10_F1_D10",)),
        BendersCut(
            BendersCutType.OPTIMALITY,
            BendersSubproblem.PRM,
            ("FO_T10_F1_D20",),
            200.0,
            2500.0,
        ),
    )
    with GurobiAdapter(output_flag=False) as solver:
        master = build_fixed_column_benders_master(
            scenario, columns, _costs(), _config(), cuts, solver
        )
        outcome = solver.solve()
        assert outcome.status is SolverStatus.OPTIMAL
        assert outcome.objective_value == pytest.approx(220.0)
        assert solver.get_variable_value(
            master.theta_variables[BendersSubproblem.PRM]
        ) == pytest.approx(200.0)
        assert solver.get_variable_value(
            master.srm_model.variables["FO_T10_F1_D20"]
        ) == pytest.approx(1.0)

    with GurobiAdapter(output_flag=False) as solver:
        with pytest.raises(FixedColumnBendersError, match="duplicate cut key"):
            build_fixed_column_benders_master(
                scenario, columns, _costs(), _config(), (cuts[0], cuts[0]), solver
            )


def test_master_scope_fix_matches_integrated_semantics(
    toy_case_006_scope_data, toy_case_006_scope_columns_data
):
    _require_gurobi()
    scenario = Scenario.model_validate(toy_case_006_scope_data)
    columns = RecoveryColumns.model_validate(toy_case_006_scope_columns_data)
    scope = build_recovery_scope(scenario, columns)
    with GurobiAdapter(output_flag=False) as solver:
        master = build_fixed_column_benders_master(
            scenario, columns, _costs(), _config(), (), solver, scope=scope
        )
        outcome = solver.solve()
        assert outcome.status is SolverStatus.OPTIMAL
        assert solver.get_variable_value(
            master.srm_model.variables["S6_UO1"]
        ) == pytest.approx(1.0)


class _StatusOverrideAdapter(GurobiAdapter):
    def __init__(self, override: SolverStatus):
        super().__init__(output_flag=False)
        self.override = override

    def solve(self, parameters=None):
        outcome = super().solve(parameters)
        overridden = replace(outcome, status=self.override)
        self._last_outcome = overridden
        return overridden


def test_nonoptimal_master_and_subproblem_abort_cleanly(
    toy_case_010_fixed_column_benders_data,
    toy_case_010_fixed_column_benders_columns_data,
):
    _require_gurobi()
    aborted_master = solve_fixed_column_benders(
        toy_case_010_fixed_column_benders_data,
        toy_case_010_fixed_column_benders_columns_data,
        _toy10_capacity(),
        _costs(),
        _config(),
        solver_factory=lambda: _StatusOverrideAdapter(SolverStatus.FEASIBLE),
    )
    assert aborted_master.status is BendersStatus.ABORTED
    assert aborted_master.lower_bound is None
    assert aborted_master.diagnostics["terminal_reason"].startswith("master_nonoptimal")

    calls = 0

    def factory():
        nonlocal calls
        calls += 1
        if calls == 3:
            return _StatusOverrideAdapter(SolverStatus.FEASIBLE)
        return GurobiAdapter(output_flag=False)

    aborted_subproblem = solve_fixed_column_benders(
        toy_case_010_fixed_column_benders_data,
        toy_case_010_fixed_column_benders_columns_data,
        _toy10_capacity(),
        _costs(),
        _config(),
        solver_factory=factory,
    )
    assert aborted_subproblem.status is BendersStatus.ABORTED
    assert "crm:feasible" in aborted_subproblem.diagnostics["terminal_reason"]


def test_max_iterations_is_not_reported_as_optimal(
    toy_case_010_fixed_column_benders_data,
    toy_case_010_fixed_column_benders_columns_data,
):
    _require_gurobi()
    config = _config().model_copy(update={"max_iterations": 1})
    result = solve_fixed_column_benders(
        toy_case_010_fixed_column_benders_data,
        toy_case_010_fixed_column_benders_columns_data,
        _toy10_capacity(),
        _costs(),
        config,
        solver_factory=lambda: GurobiAdapter(output_flag=False),
    )
    assert result.status is BendersStatus.NOT_CONVERGED
    assert result.objective_value is None
    assert result.diagnostics["terminal_reason"] == "max_iterations"


def test_result_is_json_serializable_and_bounds_are_monotone(
    toy_case_010_fixed_column_benders_data,
    toy_case_010_fixed_column_benders_columns_data,
):
    _require_gurobi()
    result = solve_fixed_column_benders(
        toy_case_010_fixed_column_benders_data,
        toy_case_010_fixed_column_benders_columns_data,
        _toy10_capacity(),
        _costs(),
        _config(),
        solver_factory=lambda: GurobiAdapter(output_flag=False),
    )
    assert result.status is BendersStatus.OPTIMAL
    assert result.objective_value == pytest.approx(220.0)
    lower_bounds = [item.lower_bound for item in result.iterations]
    assert lower_bounds == sorted(lower_bounds)
    upper_bounds = [
        item.incumbent_upper_bound
        for item in result.iterations
        if item.incumbent_upper_bound is not None
    ]
    assert upper_bounds == sorted(upper_bounds, reverse=True)
    assert result.iterations[-1].absolute_gap == pytest.approx(0.0)
    assert result.diagnostics["integrated_audit"]["all_constraints_satisfied"]
    json.dumps(result.to_dict())
