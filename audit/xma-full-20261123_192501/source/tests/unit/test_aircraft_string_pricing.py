from pathlib import Path

import pytest

from backend.config import load_cost_config, load_flight_string_generation_config
from backend.core import (
    AircraftRecoveryRequest,
    AircraftStringMasterPhase,
    aircraft_string_semantic_key,
    build_aircraft_string_master,
    evaluate_aircraft_string_reduced_cost,
    generate_aircraft_strings,
    price_aircraft_strings,
    solve_aircraft_string_master,
)
from backend.schemas.columns import RecoveryColumns
from backend.schemas.scenario import Scenario
from backend.solver import GurobiAdapter


ROOT = Path(__file__).parents[2]


def test_dag_pricer_matches_exhaustive_full_pool_scan(
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
    config = load_flight_string_generation_config(
        ROOT / "data/config/phase5_test_string_generation_v1.json"
    )
    full_pool = generate_aircraft_strings(
        scenario, columns.flight_options, None, config
    )
    expensive = tuple(
        item for item in full_pool if len(item.leg_option_ids) == 3
    )
    request = AircraftRecoveryRequest.from_option_ids(
        scenario.scenario_id, ("S11_REQ1", "S11_REQ2")
    )
    with GurobiAdapter(output_flag=False) as solver:
        model = build_aircraft_string_master(
            scenario,
            columns.flight_options,
            expensive,
            request,
            costs,
            config,
            solver,
            phase=AircraftStringMasterPhase.PHASE_II,
        )
        master = solve_aircraft_string_master(model, solver)
    assert master.duals is not None
    existing = {
        aircraft_string_semantic_key(item.aircraft_id, item.leg_option_ids)
        for item in expensive
    }
    priced = price_aircraft_strings(
        scenario,
        columns.flight_options,
        scenario.aircraft[0],
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
        if item.aircraft_id == scenario.aircraft[0].tail_id
        and aircraft_string_semantic_key(item.aircraft_id, item.leg_option_ids)
        not in existing
    ]
    exhaustive_minimum = min(
        evaluate_aircraft_string_reduced_cost(
            scenario, options, item, costs, master.duals
        ).reduced_cost
        for item in omitted
    )
    assert priced.minimum_reduced_cost == pytest.approx(exhaustive_minimum)
    assert priced.columns[0].reduced_cost == pytest.approx(-150.0)
    assert priced.columns[0].aircraft_string.leg_option_ids == ["S11_REQ1"]
