from pathlib import Path

import pytest

from backend.config import (
    CostOverrideConfig,
    apply_cost_overrides,
    load_cost_config,
    load_crew_pairing_column_generation_config,
    load_crew_pairing_generation_config,
)
from backend.core import (
    CrewPairingColumnGenerationStatus,
    CrewRecoveryRequest,
    RecoveryScope,
    audit_crew_pairing_column_generation_termination,
    generate_crew_pairings,
    resolve_original_flight_option_ids,
    solve_crew_pairing_column_generation,
    solve_full_column_crew_pairing_lp,
)
from backend.schemas.columns import RecoveryColumns
from backend.schemas.scenario import Scenario
from backend.solver import GurobiAdapter, SolverStatus


ROOT = Path(__file__).parents[2]


def _profiles():
    pairing = load_crew_pairing_generation_config(
        ROOT / "data/config/phase6_test_crew_pairing_generation_v1.json"
    )
    cg = load_crew_pairing_column_generation_config(
        ROOT / "data/config/phase10_test_crew_pairing_cg_v1.json"
    )
    return pairing, cg


@pytest.mark.parametrize(
    ("scenario_file", "columns_file", "toy"),
    [
        (
            "toy_case_012_crew_pairing_column_generation.json",
            "toy_case_012_crew_pairing_column_generation_columns.json",
            True,
        ),
        ("phase1_benchmark_001.json", "phase1_benchmark_001_columns.json", False),
    ],
)
def test_all_pairings_lp_equals_crew_cg(scenario_file, columns_file, toy):
    scenario = Scenario.model_validate_json(
        (ROOT / "data/examples" / scenario_file).read_text(encoding="utf-8")
    )
    columns = RecoveryColumns.model_validate_json(
        (ROOT / "data/columns" / columns_file).read_text(encoding="utf-8")
    )
    pairing_config, cg_config = _profiles()
    base_costs = load_cost_config(ROOT / "data/costs/phase2_test_costs_v1.json")
    costs = (
        apply_cost_overrides(
            base_costs,
            CostOverrideConfig(
                base_cost_profile_id=base_costs.cost_profile_id,
                overrides={"crew_reassignment": 100.0},
            ),
        )
        if toy
        else base_costs
    )
    full_pool = generate_crew_pairings(
        scenario, columns.flight_options, None, pairing_config
    )
    required = (
        ("S12_A_LONG", "S12_Z_SHORT")
        if toy
        else tuple(
            resolve_original_flight_option_ids(
                scenario, columns.flight_options
            ).values()
        )
    )
    request = CrewRecoveryRequest.from_option_ids(scenario.scenario_id, required)
    with GurobiAdapter(output_flag=False) as solver:
        full = solve_full_column_crew_pairing_lp(
            scenario,
            columns.flight_options,
            full_pool,
            request,
            costs,
            pairing_config,
            solver,
        )
    cg = solve_crew_pairing_column_generation(
        scenario,
        columns.flight_options,
        request,
        costs,
        pairing_config,
        cg_config,
        lambda: GurobiAdapter(output_flag=False),
    )
    audit = audit_crew_pairing_column_generation_termination(
        scenario,
        columns.flight_options,
        full_pool,
        request,
        costs,
        pairing_config,
        cg_config,
        cg,
        lambda: GurobiAdapter(output_flag=False),
    )
    assert len(full_pool) == (12 if toy else 374)
    assert full.outcome.status is SolverStatus.OPTIMAL
    assert cg.status is CrewPairingColumnGenerationStatus.OPTIMAL
    assert cg.objective_value == pytest.approx(full.objective_value, abs=1e-7)
    assert {item.pairing_id for item in cg.columns} <= {
        item.pairing_id for item in full_pool
    }
    assert audit.passed
    assert audit.minimum_omitted_reduced_cost is None or (
        audit.minimum_omitted_reduced_cost >= -cg_config.pricing_epsilon
    )


def test_dedicated_scope_all_pairings_lp_equals_scope_cg(
    toy_case_012_crew_pairing_column_generation_data,
    toy_case_012_crew_pairing_column_generation_columns_data,
):
    scenario = Scenario.model_validate(toy_case_012_crew_pairing_column_generation_data)
    columns = RecoveryColumns.model_validate(
        toy_case_012_crew_pairing_column_generation_columns_data
    )
    pairing_config, cg_config = _profiles()
    base_costs = load_cost_config(ROOT / "data/costs/phase2_test_costs_v1.json")
    costs = apply_cost_overrides(
        base_costs,
        CostOverrideConfig(
            base_cost_profile_id=base_costs.cost_profile_id,
            overrides={"crew_reassignment": 100.0},
        ),
    )
    request = CrewRecoveryRequest.from_option_ids(
        scenario.scenario_id, ("S12_A_LONG", "S12_Z_SHORT")
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
    full_pool = generate_crew_pairings(
        scenario, columns.flight_options, None, pairing_config
    )
    with GurobiAdapter(output_flag=False) as solver:
        full = solve_full_column_crew_pairing_lp(
            scenario,
            columns.flight_options,
            full_pool,
            request,
            costs,
            pairing_config,
            solver,
            scope=scope,
        )
    cg = solve_crew_pairing_column_generation(
        scenario,
        columns.flight_options,
        request,
        costs,
        pairing_config,
        cg_config,
        lambda: GurobiAdapter(output_flag=False),
        scope=scope,
    )
    assert full.objective_value == pytest.approx(150.0)
    assert cg.objective_value == pytest.approx(full.objective_value)
