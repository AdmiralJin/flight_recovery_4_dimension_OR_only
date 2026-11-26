from pathlib import Path

import pytest

from backend.config import (
    AircraftStringColumnGenerationConfigError,
    load_aircraft_string_column_generation_config,
    load_cost_config,
    load_flight_string_generation_config,
)
from backend.core import (
    AircraftRecoveryRequest,
    AircraftStringColumnGenerationStatus,
    RecoveryScope,
    solve_aircraft_string_column_generation,
)
from backend.schemas.columns import RecoveryColumns
from backend.schemas.scenario import Scenario
from backend.solver import GurobiAdapter


ROOT = Path(__file__).parents[2]


def _inputs(scenario_data, columns_data):
    return (
        Scenario.model_validate(scenario_data),
        RecoveryColumns.model_validate(columns_data),
        load_cost_config(ROOT / "data/costs/phase2_test_costs_v1.json"),
        load_flight_string_generation_config(
            ROOT / "data/config/phase5_test_string_generation_v1.json"
        ),
        load_aircraft_string_column_generation_config(
            ROOT / "data/config/phase9_test_aircraft_string_cg_v1.json"
        ),
    )


def test_two_phase_column_generation_adds_phase_two_improving_columns(
    toy_case_011_aircraft_string_column_generation_data,
    toy_case_011_aircraft_string_column_generation_columns_data,
):
    scenario, columns, costs, strings, config = _inputs(
        toy_case_011_aircraft_string_column_generation_data,
        toy_case_011_aircraft_string_column_generation_columns_data,
    )
    request = AircraftRecoveryRequest.from_option_ids(
        scenario.scenario_id, ("S11_REQ1", "S11_REQ2")
    )
    result = solve_aircraft_string_column_generation(
        scenario,
        columns.flight_options,
        request,
        costs,
        strings,
        config,
        lambda: GurobiAdapter(output_flag=False),
    )
    assert result.status is AircraftStringColumnGenerationStatus.OPTIMAL
    assert result.objective_value == pytest.approx(0.0)
    assert result.phase_one_iterations == 2
    assert result.phase_two_iterations == 2
    assert len(result.columns) == 4
    improving = [
        item for item in result.iterations if item.minimum_reduced_cost == -150.0
    ]
    assert len(improving) == 1
    assert improving[0].new_columns_added == 2
    assert result.maximum_reduced_cost_audit_error <= 1e-8
    assert len(result.input_fingerprint) == 64


def test_formal_solver_does_not_call_full_string_enumerator(
    monkeypatch,
    toy_case_011_aircraft_string_column_generation_data,
    toy_case_011_aircraft_string_column_generation_columns_data,
):
    scenario, columns, costs, strings, config = _inputs(
        toy_case_011_aircraft_string_column_generation_data,
        toy_case_011_aircraft_string_column_generation_columns_data,
    )
    request = AircraftRecoveryRequest.from_option_ids(
        scenario.scenario_id, ("S11_REQ1", "S11_REQ2")
    )

    def forbidden(*_args, **_kwargs):
        raise AssertionError("formal CG must not call full enumeration")

    monkeypatch.setattr(
        "backend.core.string_generator.generate_aircraft_strings", forbidden
    )
    result = solve_aircraft_string_column_generation(
        scenario,
        columns.flight_options,
        request,
        costs,
        strings,
        config,
        lambda: GurobiAdapter(output_flag=False),
    )
    assert result.status is AircraftStringColumnGenerationStatus.OPTIMAL


def test_iteration_limit_returns_not_converged(
    toy_case_011_aircraft_string_column_generation_data,
    toy_case_011_aircraft_string_column_generation_columns_data,
):
    scenario, columns, costs, strings, config = _inputs(
        toy_case_011_aircraft_string_column_generation_data,
        toy_case_011_aircraft_string_column_generation_columns_data,
    )
    request = AircraftRecoveryRequest.from_option_ids(
        scenario.scenario_id, ("S11_REQ1", "S11_REQ2")
    )
    limited = config.model_copy(update={"max_iterations": 1})
    result = solve_aircraft_string_column_generation(
        scenario,
        columns.flight_options,
        request,
        costs,
        strings,
        limited,
        lambda: GurobiAdapter(output_flag=False),
    )
    assert result.status is AircraftStringColumnGenerationStatus.NOT_CONVERGED
    assert result.termination_reason == "maximum_iterations_reached"
    assert result.objective_value is None


def test_scope_prices_only_in_scope_and_fixes_out_of_scope_original(
    toy_case_011_aircraft_string_column_generation_data,
    toy_case_011_aircraft_string_column_generation_columns_data,
):
    scenario, columns, costs, strings, config = _inputs(
        toy_case_011_aircraft_string_column_generation_data,
        toy_case_011_aircraft_string_column_generation_columns_data,
    )
    request = AircraftRecoveryRequest.from_option_ids(
        scenario.scenario_id, ("S11_REQ1", "S11_REQ2")
    )
    scope = RecoveryScope(
        direct_flight_ids=(),
        flight_ids=("S11_F1",),
        aircraft_ids=("S11_AC1",),
        crew_ids=(),
        passenger_group_ids=(),
        flight_option_ids=("S11_REQ1",),
        aircraft_string_ids=(),
        crew_pairing_ids=(),
        passenger_itinerary_ids=(),
        propagation_reasons={},
        iteration_count=1,
    )
    result = solve_aircraft_string_column_generation(
        scenario,
        columns.flight_options,
        request,
        costs,
        strings,
        config,
        lambda: GurobiAdapter(output_flag=False),
        scope=scope,
    )
    ac2_columns = [item for item in result.columns if item.aircraft_id == "S11_AC2"]
    assert result.status is AircraftStringColumnGenerationStatus.OPTIMAL
    assert len(ac2_columns) == 1
    assert ac2_columns[0].leg_option_ids == ["S11_REQ2"]
    assert all(
        item.priced_aircraft_count in {0, 1} for item in result.iterations
    )


def test_phase_one_proves_infeasible_fixed_schedule(
    toy_case_007_string_generator_data,
    toy_case_007_string_generator_columns_data,
):
    scenario, columns, costs, strings, config = _inputs(
        toy_case_007_string_generator_data,
        toy_case_007_string_generator_columns_data,
    )
    request = AircraftRecoveryRequest.from_option_ids(
        scenario.scenario_id, ("S7_O1", "S7_O3", "S7_O4", "S7_UO1")
    )
    result = solve_aircraft_string_column_generation(
        scenario,
        columns.flight_options,
        request,
        costs,
        strings,
        config,
        lambda: GurobiAdapter(output_flag=False),
    )
    assert result.status is AircraftStringColumnGenerationStatus.INFEASIBLE
    assert result.objective_value is None
    assert "positive_artificial_objective" in result.termination_reason


def test_config_rejects_duplicate_json_keys(tmp_path):
    path = tmp_path / "duplicate.json"
    path.write_text(
        '{"schema_version":"1.0.0","schema_version":"1.0.0"}',
        encoding="utf-8",
    )
    with pytest.raises(AircraftStringColumnGenerationConfigError):
        load_aircraft_string_column_generation_config(path)
