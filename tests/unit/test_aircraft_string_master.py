from pathlib import Path

import pytest

from backend.config import (
    load_cost_config,
    load_flight_string_generation_config,
)
from backend.core import (
    AircraftRecoveryRequest,
    AircraftStringMasterPhase,
    build_aircraft_string_master,
    generate_aircraft_strings,
    solve_aircraft_string_master,
    solve_full_column_aircraft_string_lp,
)
from backend.schemas.columns import RecoveryColumns
from backend.schemas.scenario import Scenario
from backend.solver import GurobiAdapter, SolverStatus


ROOT = Path(__file__).parents[2]


def _inputs(scenario_data, columns_data):
    return (
        Scenario.model_validate(scenario_data),
        RecoveryColumns.model_validate(columns_data),
        load_cost_config(ROOT / "data/costs/phase2_test_costs_v1.json"),
        load_flight_string_generation_config(
            ROOT / "data/config/phase5_test_string_generation_v1.json"
        ),
    )


def test_full_column_lp_and_reduced_cost_contract(
    toy_case_011_aircraft_string_column_generation_data,
    toy_case_011_aircraft_string_column_generation_columns_data,
):
    scenario, columns, costs, string_config = _inputs(
        toy_case_011_aircraft_string_column_generation_data,
        toy_case_011_aircraft_string_column_generation_columns_data,
    )
    strings = generate_aircraft_strings(
        scenario, columns.flight_options, None, string_config
    )
    request = AircraftRecoveryRequest.from_option_ids(
        scenario.scenario_id, ("S11_REQ1", "S11_REQ2")
    )
    with GurobiAdapter(output_flag=False) as solver:
        result = solve_full_column_aircraft_string_lp(
            scenario,
            columns.flight_options,
            strings,
            request,
            costs,
            string_config,
            solver,
        )
    assert result.outcome.status is SolverStatus.OPTIMAL
    assert result.objective_value == pytest.approx(0.0)
    assert result.maximum_reduced_cost_error == pytest.approx(0.0, abs=1e-8)
    assert sum(result.string_values.values()) == pytest.approx(2.0)


def test_phase_one_master_is_feasible_from_empty_pool(
    toy_case_011_aircraft_string_column_generation_data,
    toy_case_011_aircraft_string_column_generation_columns_data,
):
    scenario, columns, costs, string_config = _inputs(
        toy_case_011_aircraft_string_column_generation_data,
        toy_case_011_aircraft_string_column_generation_columns_data,
    )
    request = AircraftRecoveryRequest.from_option_ids(
        scenario.scenario_id, ("S11_REQ1", "S11_REQ2")
    )
    with GurobiAdapter(output_flag=False) as solver:
        model = build_aircraft_string_master(
            scenario,
            columns.flight_options,
            (),
            request,
            costs,
            string_config,
            solver,
            phase=AircraftStringMasterPhase.PHASE_I,
        )
        result = solve_aircraft_string_master(model, solver)
    assert result.outcome.status is SolverStatus.OPTIMAL
    assert result.artificial_objective == pytest.approx(6.0)
    assert result.duals is not None
    assert result.duals.count == 6
