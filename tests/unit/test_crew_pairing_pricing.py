from pathlib import Path

import pytest

from backend.config import (
    CostOverrideConfig,
    apply_cost_overrides,
    load_cost_config,
    load_crew_pairing_generation_config,
)
from backend.core import (
    CrewPairingMasterDuals,
    CrewPairingMasterPhase,
    CrewRecoveryRequest,
    build_crew_pairing_master,
    evaluate_crew_pairing_reduced_cost,
    generate_crew_pairings,
    make_generated_crew_pairing,
    pairing_semantic_key,
    price_crew_pairings,
    solve_crew_pairing_master,
)
from backend.schemas.crew import Crew
from backend.schemas.columns import RecoveryColumns
from backend.schemas.scenario import Scenario
from backend.solver import GurobiAdapter


ROOT = Path(__file__).parents[2]


def test_typed_dag_pricer_matches_exhaustive_minimum(
    toy_case_012_crew_pairing_column_generation_data,
    toy_case_012_crew_pairing_column_generation_columns_data,
):
    scenario = Scenario.model_validate(toy_case_012_crew_pairing_column_generation_data)
    columns = RecoveryColumns.model_validate(
        toy_case_012_crew_pairing_column_generation_columns_data
    )
    config = load_crew_pairing_generation_config(
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
    full_pool = generate_crew_pairings(scenario, columns.flight_options, None, config)
    expensive = tuple(
        item
        for item in full_pool
        if pairing_semantic_key(item)[1] != (("deadhead", "S12_Z_SHORT"),)
    )
    request = CrewRecoveryRequest.from_option_ids(
        scenario.scenario_id, ("S12_A_LONG", "S12_Z_SHORT")
    )
    with GurobiAdapter(output_flag=False) as solver:
        model = build_crew_pairing_master(
            scenario,
            columns.flight_options,
            expensive,
            request,
            costs,
            config,
            solver,
            phase=CrewPairingMasterPhase.PHASE_II,
        )
        master = solve_crew_pairing_master(model, solver)
    assert master.duals is not None
    existing = {pairing_semantic_key(item) for item in expensive}
    priced = price_crew_pairings(
        scenario,
        columns.flight_options,
        scenario.crew[2],
        request,
        costs,
        config,
        master.duals,
        existing,
        pricing_epsilon=1e-7,
    )
    options = {item.option_id: item for item in columns.flight_options}
    omitted = [
        item
        for item in full_pool
        if item.crew_id == "S12_C3" and pairing_semantic_key(item) not in existing
    ]
    exhaustive = min(
        evaluate_crew_pairing_reduced_cost(
            scenario, options, item, costs, master.duals
        ).reduced_cost
        for item in omitted
    )
    assert priced.minimum_reduced_cost == pytest.approx(exhaustive)
    assert priced.columns[0].reduced_cost == pytest.approx(-150.0)
    assert pairing_semantic_key(priced.columns[0].crew_pairing)[1] == (
        ("deadhead", "S12_Z_SHORT"),
    )


def test_phase_one_reduced_cost_ignores_true_deadhead_cost(
    toy_case_012_crew_pairing_column_generation_data,
    toy_case_012_crew_pairing_column_generation_columns_data,
):
    scenario = Scenario.model_validate(toy_case_012_crew_pairing_column_generation_data)
    columns = RecoveryColumns.model_validate(
        toy_case_012_crew_pairing_column_generation_columns_data
    )
    config = load_crew_pairing_generation_config(
        ROOT / "data/config/phase6_test_crew_pairing_generation_v1.json"
    )
    costs = load_cost_config(ROOT / "data/costs/phase2_test_costs_v1.json")
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
        master = solve_crew_pairing_master(model, solver)
    assert master.duals is not None
    priced = price_crew_pairings(
        scenario,
        columns.flight_options,
        scenario.crew[0],
        request,
        costs,
        config,
        master.duals,
        set(),
        pricing_epsilon=1e-7,
    )
    assert priced.columns
    assert all(item.primal_cost == 0.0 for item in priced.columns)


def test_idle_pairing_keeps_selection_and_terminal_reduced_cost():
    scenario = Scenario.model_validate_json(
        (ROOT / "data/examples/toy_case_008_crew_pairing_generator.json").read_text(
            encoding="utf-8"
        )
    )
    columns = RecoveryColumns.model_validate_json(
        (
            ROOT / "data/columns/toy_case_008_crew_pairing_generator_columns.json"
        ).read_text(encoding="utf-8")
    )
    config = load_crew_pairing_generation_config(
        ROOT / "data/config/phase6_test_crew_pairing_generation_v1.json"
    )
    costs = load_cost_config(ROOT / "data/costs/phase2_test_costs_v1.json")
    crew: Crew = scenario.crew[0]
    duals = CrewPairingMasterDuals(
        phase=CrewPairingMasterPhase.PHASE_II,
        selection_by_crew={crew.crew_id: 2.0},
        required_operate_coverage_by_option={},
        nonrequired_operate_by_option={
            item.option_id: 0.0 for item in columns.flight_options
        },
        nonrequired_deadhead_by_option={
            item.option_id: 0.0 for item in columns.flight_options
        },
        terminal_by_crew={crew.crew_id: 3.0},
    )
    request = CrewRecoveryRequest.from_option_ids(scenario.scenario_id, ())
    priced = price_crew_pairings(
        scenario,
        columns.flight_options,
        crew,
        request,
        costs,
        config,
        duals,
        set(),
        pricing_epsilon=1e-7,
    )
    assert pairing_semantic_key(priced.columns[0].crew_pairing)[1] == ()
    assert priced.columns[0].reduced_cost == pytest.approx(-5.0)
    assert make_generated_crew_pairing(crew, ()).pairing_id == (
        priced.columns[0].crew_pairing.pairing_id
    )
