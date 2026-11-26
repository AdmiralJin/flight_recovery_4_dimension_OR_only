from pathlib import Path

import pytest

from backend.config import (
    CostOverrideConfig,
    apply_cost_overrides,
    load_branch_and_price_config,
    load_cost_config,
    load_crew_pairing_column_generation_config,
    load_crew_pairing_generation_config,
)
from backend.core import (
    BranchAndPriceStatus,
    CrewRecoveryRequest,
    generate_crew_pairings,
    solve_crew_pairing_branch_and_price,
    solve_fixed_column_crm,
    solve_full_column_crew_pairing_lp,
)
from backend.schemas.columns import RecoveryColumns
from backend.schemas.scenario import Scenario
from backend.solver import GurobiAdapter, SolverStatus


ROOT = Path(__file__).parents[2]


def test_natural_crew_gap_is_closed_by_typed_follow_on_branching(
    toy_case_015_crew_integrality_data,
    toy_case_015_crew_integrality_columns_data,
):
    scenario = Scenario.model_validate(toy_case_015_crew_integrality_data)
    columns = RecoveryColumns.model_validate(toy_case_015_crew_integrality_columns_data)
    pairing_config = load_crew_pairing_generation_config(
        ROOT / "data/config/phase6_test_crew_pairing_generation_v1.json"
    )
    base_costs = load_cost_config(ROOT / "data/costs/phase2_test_costs_v1.json")
    costs = apply_cost_overrides(
        base_costs,
        CostOverrideConfig(
            base_cost_profile_id=base_costs.cost_profile_id,
            overrides={"crew_reassignment": 100.0, "deadhead_per_minute": 1.0},
        ),
    )
    request = CrewRecoveryRequest.from_option_ids(
        scenario.scenario_id, ("T15_O1", "T15_O2", "T15_O3")
    )
    full_pool = generate_crew_pairings(
        scenario, columns.flight_options, None, pairing_config
    )
    with GurobiAdapter(output_flag=False) as solver:
        lp = solve_full_column_crew_pairing_lp(
            scenario,
            columns.flight_options,
            full_pool,
            request,
            costs,
            pairing_config,
            solver,
        )
    with GurobiAdapter(output_flag=False) as solver:
        mip = solve_fixed_column_crm(
            scenario,
            columns.model_copy(update={"crew_pairings": full_pool}),
            request,
            costs,
            solver,
        )
    result = solve_crew_pairing_branch_and_price(
        scenario,
        columns.flight_options,
        request,
        costs,
        pairing_config,
        load_crew_pairing_column_generation_config(
            ROOT / "data/config/phase10_test_crew_pairing_cg_v1.json"
        ),
        load_branch_and_price_config(
            ROOT / "data/config/phase12_test_branch_and_price_v1.json"
        ),
        lambda: GurobiAdapter(output_flag=False),
    )
    repeated = solve_crew_pairing_branch_and_price(
        scenario,
        columns.flight_options,
        request,
        costs,
        pairing_config,
        load_crew_pairing_column_generation_config(
            ROOT / "data/config/phase10_test_crew_pairing_cg_v1.json"
        ),
        load_branch_and_price_config(
            ROOT / "data/config/phase12_test_branch_and_price_v1.json"
        ),
        lambda: GurobiAdapter(output_flag=False),
    )
    assert lp.outcome.status is SolverStatus.OPTIMAL
    assert lp.objective_value == pytest.approx(195.0)
    assert mip.status is SolverStatus.OPTIMAL
    assert mip.objective_value == pytest.approx(200.0)
    assert result.status is BranchAndPriceStatus.OPTIMAL
    assert result.root_lp_objective == pytest.approx(lp.objective_value)
    assert result.objective_value == pytest.approx(mip.objective_value)
    assert result.nodes_solved == 9
    assert result.max_depth == 4
    assert any("branch:follow_on" in item.branch_decision for item in result.nodes)
    assert result.reused_parent_columns > 0
    assert [item.branch_decision for item in repeated.nodes] == [
        item.branch_decision for item in result.nodes
    ]
    assert repeated.objective_value == pytest.approx(result.objective_value)
