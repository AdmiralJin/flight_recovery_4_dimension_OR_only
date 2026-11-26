from pathlib import Path

import pytest

from backend.config import (
    CostOverrideConfig,
    CrewPairingColumnGenerationConfigError,
    apply_cost_overrides,
    load_cost_config,
    load_crew_pairing_column_generation_config,
    load_crew_pairing_generation_config,
)
from backend.core import (
    CrewPairingColumnGenerationStatus,
    CrewRecoveryRequest,
    RecoveryScope,
    pairing_semantic_key,
    solve_crew_pairing_column_generation,
)
from backend.schemas.columns import RecoveryColumns
from backend.schemas.scenario import Scenario
from backend.solver import GurobiAdapter


ROOT = Path(__file__).parents[2]


def _inputs(scenario_data, columns_data):
    scenario = Scenario.model_validate(scenario_data)
    columns = RecoveryColumns.model_validate(columns_data)
    pairing_config = load_crew_pairing_generation_config(
        ROOT / "data/config/phase6_test_crew_pairing_generation_v1.json"
    )
    cg_config = load_crew_pairing_column_generation_config(
        ROOT / "data/config/phase10_test_crew_pairing_cg_v1.json"
    )
    base_costs = load_cost_config(ROOT / "data/costs/phase2_test_costs_v1.json")
    costs = apply_cost_overrides(
        base_costs,
        CostOverrideConfig(
            base_cost_profile_id=base_costs.cost_profile_id,
            overrides={"crew_reassignment": 100.0},
        ),
    )
    return scenario, columns, pairing_config, cg_config, costs


def _request(scenario):
    return CrewRecoveryRequest.from_option_ids(
        scenario.scenario_id, ("S12_A_LONG", "S12_Z_SHORT")
    )


def test_two_phase_crew_cg_improves_expensive_deadhead_pool(
    toy_case_012_crew_pairing_column_generation_data,
    toy_case_012_crew_pairing_column_generation_columns_data,
):
    scenario, columns, pairing_config, cg_config, costs = _inputs(
        toy_case_012_crew_pairing_column_generation_data,
        toy_case_012_crew_pairing_column_generation_columns_data,
    )
    result = solve_crew_pairing_column_generation(
        scenario,
        columns.flight_options,
        _request(scenario),
        costs,
        pairing_config,
        cg_config,
        lambda: GurobiAdapter(output_flag=False),
    )
    assert result.status is CrewPairingColumnGenerationStatus.OPTIMAL
    assert result.objective_value == pytest.approx(150.0)
    assert result.phase_one_iterations == 4
    assert result.phase_two_iterations == 2
    improving = [
        item for item in result.iterations if item.minimum_reduced_cost == -150.0
    ]
    assert len(improving) == 1
    assert improving[0].restricted_master_objective == pytest.approx(300.0)
    assert improving[0].new_columns_added == 3
    assert result.maximum_reduced_cost_audit_error <= 1e-8
    assert len(result.input_fingerprint) == 64


def test_scope_prices_one_crew_and_retains_other_originals(
    toy_case_012_crew_pairing_column_generation_data,
    toy_case_012_crew_pairing_column_generation_columns_data,
):
    scenario, columns, pairing_config, cg_config, costs = _inputs(
        toy_case_012_crew_pairing_column_generation_data,
        toy_case_012_crew_pairing_column_generation_columns_data,
    )
    scope = RecoveryScope(
        direct_flight_ids=(),
        flight_ids=(),
        aircraft_ids=(),
        crew_ids=("S12_C3",),
        passenger_group_ids=(),
        flight_option_ids=(),
        aircraft_string_ids=(),
        crew_pairing_ids=(),
        passenger_itinerary_ids=(),
        propagation_reasons={},
        iteration_count=1,
    )
    result = solve_crew_pairing_column_generation(
        scenario,
        columns.flight_options,
        _request(scenario),
        costs,
        pairing_config,
        cg_config,
        lambda: GurobiAdapter(output_flag=False),
        scope=scope,
    )
    assert result.status is CrewPairingColumnGenerationStatus.OPTIMAL
    assert result.objective_value == pytest.approx(150.0)
    c1 = [item for item in result.columns if item.crew_id == "S12_C1"]
    c2 = [item for item in result.columns if item.crew_id == "S12_C2"]
    assert len(c1) == len(c2) == 1
    assert pairing_semantic_key(c1[0])[1] == (("operate", "S12_A_LONG"),)
    assert pairing_semantic_key(c2[0])[1] == (("operate", "S12_Z_SHORT"),)
    assert all(item.priced_crew_count in {0, 1} for item in result.iterations)


def test_true_infeasible_schedule_is_proved_by_phase_one(
    toy_case_012_crew_pairing_column_generation_data,
    toy_case_012_crew_pairing_column_generation_columns_data,
):
    scenario, columns, pairing_config, cg_config, costs = _inputs(
        toy_case_012_crew_pairing_column_generation_data,
        toy_case_012_crew_pairing_column_generation_columns_data,
    )
    scenario = scenario.model_copy(
        update={
            "crew": [
                crew.model_copy(update={"rating": "UNQUALIFIED"})
                for crew in scenario.crew
            ]
        }
    )
    result = solve_crew_pairing_column_generation(
        scenario,
        columns.flight_options,
        _request(scenario),
        costs,
        pairing_config,
        cg_config,
        lambda: GurobiAdapter(output_flag=False),
    )
    assert result.status is CrewPairingColumnGenerationStatus.INFEASIBLE
    assert result.objective_value is None
    assert "positive_artificial_objective" in result.termination_reason


def test_formal_cg_does_not_call_full_pairing_enumerators(
    monkeypatch,
    toy_case_012_crew_pairing_column_generation_data,
    toy_case_012_crew_pairing_column_generation_columns_data,
):
    scenario, columns, pairing_config, cg_config, costs = _inputs(
        toy_case_012_crew_pairing_column_generation_data,
        toy_case_012_crew_pairing_column_generation_columns_data,
    )

    def forbidden(*_args, **_kwargs):
        raise AssertionError("formal Crew CG must not call full enumeration")

    monkeypatch.setattr(
        "backend.core.pairing_generator.generate_crew_pairings", forbidden
    )
    monkeypatch.setattr(
        "backend.core.pairing_generator.brute_force_legal_crew_pairings", forbidden
    )
    result = solve_crew_pairing_column_generation(
        scenario,
        columns.flight_options,
        _request(scenario),
        costs,
        pairing_config,
        cg_config,
        lambda: GurobiAdapter(output_flag=False),
    )
    assert result.status is CrewPairingColumnGenerationStatus.OPTIMAL


def test_iteration_limit_and_duplicate_config_key(
    tmp_path,
    toy_case_012_crew_pairing_column_generation_data,
    toy_case_012_crew_pairing_column_generation_columns_data,
):
    scenario, columns, pairing_config, cg_config, costs = _inputs(
        toy_case_012_crew_pairing_column_generation_data,
        toy_case_012_crew_pairing_column_generation_columns_data,
    )
    limited = cg_config.model_copy(update={"max_iterations": 1})
    result = solve_crew_pairing_column_generation(
        scenario,
        columns.flight_options,
        _request(scenario),
        costs,
        pairing_config,
        limited,
        lambda: GurobiAdapter(output_flag=False),
    )
    assert result.status is CrewPairingColumnGenerationStatus.NOT_CONVERGED
    path = tmp_path / "duplicate.json"
    path.write_text(
        '{"schema_version":"1.0.0","schema_version":"1.0.0"}',
        encoding="utf-8",
    )
    with pytest.raises(CrewPairingColumnGenerationConfigError):
        load_crew_pairing_column_generation_config(path)


def test_column_generation_is_deterministic(
    toy_case_012_crew_pairing_column_generation_data,
    toy_case_012_crew_pairing_column_generation_columns_data,
):
    scenario, columns, pairing_config, cg_config, costs = _inputs(
        toy_case_012_crew_pairing_column_generation_data,
        toy_case_012_crew_pairing_column_generation_columns_data,
    )
    args = (
        scenario,
        columns.flight_options,
        _request(scenario),
        costs,
        pairing_config,
        cg_config,
    )
    first = solve_crew_pairing_column_generation(
        *args, lambda: GurobiAdapter(output_flag=False)
    )
    second = solve_crew_pairing_column_generation(
        *args, lambda: GurobiAdapter(output_flag=False)
    )
    assert [pairing_semantic_key(item) for item in first.columns] == [
        pairing_semantic_key(item) for item in second.columns
    ]
    assert [
        (item.phase, item.minimum_reduced_cost, item.new_columns_added)
        for item in first.iterations
    ] == [
        (item.phase, item.minimum_reduced_cost, item.new_columns_added)
        for item in second.iterations
    ]
