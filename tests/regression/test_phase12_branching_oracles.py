from pathlib import Path

import pytest

from backend.config import (
    CostOverrideConfig,
    apply_cost_overrides,
    load_aircraft_string_column_generation_config,
    load_cost_config,
    load_crew_pairing_column_generation_config,
    load_crew_pairing_generation_config,
    load_flight_string_generation_config,
)
from backend.core import (
    AircraftBranchRestrictions,
    AircraftRecoveryRequest,
    CrewBranchRestrictions,
    CrewRecoveryRequest,
    generate_aircraft_strings,
    generate_crew_pairings,
    solve_aircraft_string_column_generation,
    solve_crew_pairing_column_generation,
    solve_full_column_aircraft_string_lp,
    solve_full_column_crew_pairing_lp,
)
from backend.schemas.columns import RecoveryColumns
from backend.schemas.scenario import Scenario
from backend.solver import GurobiAdapter


ROOT = Path(__file__).parents[2]


def test_aircraft_restricted_node_cg_matches_filtered_full_pool(
    toy_case_011_aircraft_string_column_generation_data,
    toy_case_011_aircraft_string_column_generation_columns_data,
):
    scenario = Scenario.model_validate(
        toy_case_011_aircraft_string_column_generation_data
    )
    columns = RecoveryColumns.model_validate(
        toy_case_011_aircraft_string_column_generation_columns_data
    )
    costs = load_cost_config(ROOT / "data/costs/phase2_test_costs_v1.json")
    string_config = load_flight_string_generation_config(
        ROOT / "data/config/phase5_test_string_generation_v1.json"
    )
    restrictions = AircraftBranchRestrictions(
        required_options_by_aircraft={"S11_AC1": ("S11_REQ1",)}
    )
    request = AircraftRecoveryRequest.from_option_ids(
        scenario.scenario_id, ("S11_REQ1", "S11_REQ2")
    )
    full_pool = tuple(
        item
        for item in generate_aircraft_strings(
            scenario, columns.flight_options, None, string_config
        )
        if restrictions.allows(item)
    )
    with GurobiAdapter(output_flag=False) as solver:
        oracle = solve_full_column_aircraft_string_lp(
            scenario,
            columns.flight_options,
            full_pool,
            request,
            costs,
            string_config,
            solver,
        )
    result = solve_aircraft_string_column_generation(
        scenario,
        columns.flight_options,
        request,
        costs,
        string_config,
        load_aircraft_string_column_generation_config(
            ROOT / "data/config/phase9_test_aircraft_string_cg_v1.json"
        ),
        lambda: GurobiAdapter(output_flag=False),
        branch_restrictions=restrictions,
    )
    assert result.objective_value == pytest.approx(oracle.objective_value)
    assert all(restrictions.allows(item) for item in result.columns)


def test_crew_restricted_node_cg_matches_filtered_full_pool(
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
    follow_on = (("deadhead", "T15_O2"), ("operate", "T15_O3"))
    restrictions = CrewBranchRestrictions(
        forbidden_follow_ons_by_crew={"T15_C1": (follow_on,)}
    )
    request = CrewRecoveryRequest.from_option_ids(
        scenario.scenario_id, ("T15_O1", "T15_O2", "T15_O3")
    )
    full_pool = tuple(
        item
        for item in generate_crew_pairings(
            scenario, columns.flight_options, None, pairing_config
        )
        if restrictions.allows(item)
    )
    with GurobiAdapter(output_flag=False) as solver:
        oracle = solve_full_column_crew_pairing_lp(
            scenario,
            columns.flight_options,
            full_pool,
            request,
            costs,
            pairing_config,
            solver,
        )
    result = solve_crew_pairing_column_generation(
        scenario,
        columns.flight_options,
        request,
        costs,
        pairing_config,
        load_crew_pairing_column_generation_config(
            ROOT / "data/config/phase10_test_crew_pairing_cg_v1.json"
        ),
        lambda: GurobiAdapter(output_flag=False),
        branch_restrictions=restrictions,
    )
    assert result.objective_value == pytest.approx(oracle.objective_value)
    assert all(restrictions.allows(item) for item in result.columns)
