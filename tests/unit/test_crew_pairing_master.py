from pathlib import Path

import pytest

from backend.config import (
    CostOverrideConfig,
    apply_cost_overrides,
    load_cost_config,
    load_crew_pairing_generation_config,
)
from backend.core import (
    CrewPairingMasterPhase,
    CrewRecoveryRequest,
    build_crew_pairing_master,
    generate_crew_pairings,
    pairing_semantic_key,
    solve_crew_pairing_master,
    solve_full_column_crew_pairing_lp,
)
from backend.schemas.columns import RecoveryColumns
from backend.schemas.scenario import Scenario
from backend.solver import GurobiAdapter, SolverStatus


ROOT = Path(__file__).parents[2]


def _inputs(scenario_data, columns_data):
    scenario = Scenario.model_validate(scenario_data)
    columns = RecoveryColumns.model_validate(columns_data)
    pairing_config = load_crew_pairing_generation_config(
        ROOT / "data/config/phase6_test_crew_pairing_generation_v1.json"
    )
    base_costs = load_cost_config(ROOT / "data/costs/phase2_test_costs_v1.json")
    costs = apply_cost_overrides(
        base_costs,
        CostOverrideConfig(
            base_cost_profile_id=base_costs.cost_profile_id,
            overrides={"crew_reassignment": 100.0},
        ),
    )
    return scenario, columns, pairing_config, costs


def test_all_pairings_lp_and_reduced_cost_contract(
    toy_case_012_crew_pairing_column_generation_data,
    toy_case_012_crew_pairing_column_generation_columns_data,
):
    scenario, columns, config, costs = _inputs(
        toy_case_012_crew_pairing_column_generation_data,
        toy_case_012_crew_pairing_column_generation_columns_data,
    )
    pairings = generate_crew_pairings(scenario, columns.flight_options, None, config)
    request = CrewRecoveryRequest.from_option_ids(
        scenario.scenario_id, ("S12_A_LONG", "S12_Z_SHORT")
    )
    with GurobiAdapter(output_flag=False) as solver:
        result = solve_full_column_crew_pairing_lp(
            scenario,
            columns.flight_options,
            pairings,
            request,
            costs,
            config,
            solver,
        )
    assert result.outcome.status is SolverStatus.OPTIMAL
    assert result.objective_value == pytest.approx(150.0)
    assert result.maximum_reduced_cost_error == pytest.approx(0.0, abs=1e-8)
    assert sum(result.pairing_values.values()) == pytest.approx(3.0)


def test_master_rows_distinguish_operate_and_deadhead(
    toy_case_012_crew_pairing_column_generation_data,
    toy_case_012_crew_pairing_column_generation_columns_data,
):
    scenario, columns, config, costs = _inputs(
        toy_case_012_crew_pairing_column_generation_data,
        toy_case_012_crew_pairing_column_generation_columns_data,
    )
    pairings = generate_crew_pairings(scenario, columns.flight_options, None, config)
    request = CrewRecoveryRequest.from_option_ids(scenario.scenario_id, ("S12_A_LONG",))
    operate = next(
        item
        for item in pairings
        if item.crew_id == "S12_C1"
        and pairing_semantic_key(item)[1] == (("operate", "S12_Z_SHORT"),)
    )
    deadhead = next(
        item
        for item in pairings
        if item.crew_id == "S12_C2"
        and pairing_semantic_key(item)[1] == (("deadhead", "S12_Z_SHORT"),)
    )
    with GurobiAdapter(output_flag=False) as solver:
        model = build_crew_pairing_master(
            scenario,
            columns.flight_options,
            (operate, deadhead),
            request,
            costs,
            config,
            solver,
            phase=CrewPairingMasterPhase.PHASE_I,
        )
    assert model.row_coefficients["nonrequired_operate"]["S12_Z_SHORT"] == {
        operate.pairing_id: 1.0
    }
    assert model.row_coefficients["nonrequired_deadhead"]["S12_Z_SHORT"] == {
        deadhead.pairing_id: 1.0
    }
    assert model.row_coefficients["required_operate"]["S12_A_LONG"] == {}


def test_phase_one_empty_pool_uses_selection_coverage_terminal_artificials(
    toy_case_012_crew_pairing_column_generation_data,
    toy_case_012_crew_pairing_column_generation_columns_data,
):
    scenario, columns, config, costs = _inputs(
        toy_case_012_crew_pairing_column_generation_data,
        toy_case_012_crew_pairing_column_generation_columns_data,
    )
    request = CrewRecoveryRequest.from_option_ids(
        scenario.scenario_id, ("S12_A_LONG", "S12_Z_SHORT")
    )
    with GurobiAdapter(output_flag=False) as solver:
        model = build_crew_pairing_master(
            scenario,
            columns.flight_options,
            (),
            request,
            costs,
            config,
            solver,
            phase=CrewPairingMasterPhase.PHASE_I,
        )
        result = solve_crew_pairing_master(model, solver)
    assert result.outcome.status is SolverStatus.OPTIMAL
    assert result.artificial_objective == pytest.approx(8.0)
    assert len(result.artificial_values) == 8
    assert result.duals is not None
    assert result.duals.count == 8
