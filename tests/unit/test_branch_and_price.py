from pathlib import Path

import pytest

from backend.config import (
    BranchAndPriceConfigError,
    CostOverrideConfig,
    apply_cost_overrides,
    load_aircraft_string_column_generation_config,
    load_branch_and_price_config,
    load_cost_config,
    load_crew_pairing_column_generation_config,
    load_crew_pairing_generation_config,
    load_flight_string_generation_config,
)
from backend.core import (
    AircraftBranchRestrictions,
    AircraftRecoveryRequest,
    BranchAndPriceStatus,
    BranchRestrictionError,
    CrewBranchRestrictions,
    CrewPairingColumnGenerationStatus,
    CrewRecoveryRequest,
    branch_restriction_fingerprint,
    solve_crew_pairing_column_generation,
    solve_aircraft_string_branch_and_price,
    solve_crew_pairing_branch_and_price,
)
from backend.schemas.columns import RecoveryColumns
from backend.schemas.scenario import Scenario
from backend.solver import GurobiAdapter


ROOT = Path(__file__).parents[2]


def _solver_factory():
    return GurobiAdapter(output_flag=False)


def test_branch_config_is_strict_and_rejects_duplicate_keys(tmp_path):
    config = load_branch_and_price_config(
        ROOT / "data/config/phase12_test_branch_and_price_v1.json"
    )
    assert config.node_selection == "best_bound"
    path = tmp_path / "duplicate.json"
    path.write_text(
        '{"schema_version":"1.0.0","schema_version":"1.0.0"}',
        encoding="utf-8",
    )
    with pytest.raises(BranchAndPriceConfigError):
        load_branch_and_price_config(path)


def test_branch_restrictions_reject_contradictions_and_fingerprint_stably():
    with pytest.raises(BranchRestrictionError):
        AircraftBranchRestrictions(
            required_options_by_aircraft={"AC": ("O1",)},
            forbidden_options_by_aircraft={"AC": ("O1",)},
        )
    follow_on = (("operate", "O1"), ("deadhead", "O2"))
    with pytest.raises(BranchRestrictionError):
        CrewBranchRestrictions(
            required_follow_ons_by_crew={"C": (follow_on,)},
            forbidden_follow_ons_by_crew={"C": (follow_on,)},
        )
    first = AircraftBranchRestrictions(
        required_options_by_aircraft={"AC": ("O2", "O1")}
    )
    second = AircraftBranchRestrictions(
        required_options_by_aircraft={"AC": ("O1", "O2")}
    )
    assert branch_restriction_fingerprint(first) == branch_restriction_fingerprint(
        second
    )


def test_aircraft_branch_and_price_root_is_exact_without_natural_gap(
    toy_case_011_aircraft_string_column_generation_data,
    toy_case_011_aircraft_string_column_generation_columns_data,
):
    scenario = Scenario.model_validate(
        toy_case_011_aircraft_string_column_generation_data
    )
    columns = RecoveryColumns.model_validate(
        toy_case_011_aircraft_string_column_generation_columns_data
    )
    result = solve_aircraft_string_branch_and_price(
        scenario,
        columns.flight_options,
        AircraftRecoveryRequest.from_option_ids(
            scenario.scenario_id, ("S11_REQ1", "S11_REQ2")
        ),
        load_cost_config(ROOT / "data/costs/phase2_test_costs_v1.json"),
        load_flight_string_generation_config(
            ROOT / "data/config/phase5_test_string_generation_v1.json"
        ),
        load_aircraft_string_column_generation_config(
            ROOT / "data/config/phase9_test_aircraft_string_cg_v1.json"
        ),
        load_branch_and_price_config(
            ROOT / "data/config/phase12_test_branch_and_price_v1.json"
        ),
        _solver_factory,
    )
    assert result.status is BranchAndPriceStatus.OPTIMAL
    assert result.objective_value == pytest.approx(0.0)
    assert result.root_lp_objective == pytest.approx(result.objective_value)
    assert result.nodes_solved == 1
    assert result.nodes[0].integral


def test_crew_branch_and_price_limit_is_not_converged(
    toy_case_015_crew_integrality_data,
    toy_case_015_crew_integrality_columns_data,
):
    scenario = Scenario.model_validate(toy_case_015_crew_integrality_data)
    columns = RecoveryColumns.model_validate(toy_case_015_crew_integrality_columns_data)
    base_costs = load_cost_config(ROOT / "data/costs/phase2_test_costs_v1.json")
    costs = apply_cost_overrides(
        base_costs,
        CostOverrideConfig(
            base_cost_profile_id=base_costs.cost_profile_id,
            overrides={"crew_reassignment": 100.0, "deadhead_per_minute": 1.0},
        ),
    )
    branch = load_branch_and_price_config(
        ROOT / "data/config/phase12_test_branch_and_price_v1.json"
    ).model_copy(update={"max_nodes": 1})
    result = solve_crew_pairing_branch_and_price(
        scenario,
        columns.flight_options,
        CrewRecoveryRequest.from_option_ids(
            scenario.scenario_id, ("T15_O1", "T15_O2", "T15_O3")
        ),
        costs,
        load_crew_pairing_generation_config(
            ROOT / "data/config/phase6_test_crew_pairing_generation_v1.json"
        ),
        load_crew_pairing_column_generation_config(
            ROOT / "data/config/phase10_test_crew_pairing_cg_v1.json"
        ),
        branch,
        _solver_factory,
    )
    assert result.status is BranchAndPriceStatus.NOT_CONVERGED
    assert result.root_lp_objective == pytest.approx(195.0)
    assert result.termination_reason == "maximum_nodes_reached"


def test_impossible_required_crew_follow_on_is_infeasible(
    toy_case_015_crew_integrality_data,
    toy_case_015_crew_integrality_columns_data,
):
    scenario = Scenario.model_validate(toy_case_015_crew_integrality_data)
    columns = RecoveryColumns.model_validate(toy_case_015_crew_integrality_columns_data)
    base_costs = load_cost_config(ROOT / "data/costs/phase2_test_costs_v1.json")
    costs = apply_cost_overrides(
        base_costs,
        CostOverrideConfig(
            base_cost_profile_id=base_costs.cost_profile_id,
            overrides={"crew_reassignment": 100.0, "deadhead_per_minute": 1.0},
        ),
    )
    restrictions = CrewBranchRestrictions(
        required_follow_ons_by_crew={
            "T15_C1": ((("operate", "T15_O3"), ("operate", "T15_O1")),)
        }
    )
    result = solve_crew_pairing_column_generation(
        scenario,
        columns.flight_options,
        CrewRecoveryRequest.from_option_ids(
            scenario.scenario_id, ("T15_O1", "T15_O2", "T15_O3")
        ),
        costs,
        load_crew_pairing_generation_config(
            ROOT / "data/config/phase6_test_crew_pairing_generation_v1.json"
        ),
        load_crew_pairing_column_generation_config(
            ROOT / "data/config/phase10_test_crew_pairing_cg_v1.json"
        ),
        _solver_factory,
        branch_restrictions=restrictions,
    )
    assert result.status is CrewPairingColumnGenerationStatus.INFEASIBLE
