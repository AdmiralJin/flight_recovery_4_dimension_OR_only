from pathlib import Path

import pytest

from backend.config import (
    load_aircraft_string_column_generation_config,
    load_cost_config,
    load_flight_string_generation_config,
)
from backend.core import (
    AircraftRecoveryRequest,
    AircraftStringColumnGenerationStatus,
    audit_aircraft_string_column_generation_termination,
    generate_aircraft_strings,
    resolve_original_flight_option_ids,
    solve_aircraft_string_column_generation,
    solve_full_column_aircraft_string_lp,
)
from backend.schemas.columns import RecoveryColumns
from backend.schemas.scenario import Scenario
from backend.solver import GurobiAdapter, SolverStatus


ROOT = Path(__file__).parents[2]


@pytest.mark.parametrize(
    ("scenario_file", "columns_file", "required_ids", "expected_pool"),
    [
        (
            "toy_case_011_aircraft_string_column_generation.json",
            "toy_case_011_aircraft_string_column_generation_columns.json",
            ("S11_REQ1", "S11_REQ2"),
            4,
        ),
        (
            "phase1_benchmark_001.json",
            "phase1_benchmark_001_columns.json",
            None,
            77,
        ),
    ],
)
def test_full_column_lp_equals_column_generation(
    scenario_file, columns_file, required_ids, expected_pool
):
    scenario = Scenario.model_validate_json(
        (ROOT / "data/examples" / scenario_file).read_text(encoding="utf-8")
    )
    columns = RecoveryColumns.model_validate_json(
        (ROOT / "data/columns" / columns_file).read_text(encoding="utf-8")
    )
    costs = load_cost_config(ROOT / "data/costs/phase2_test_costs_v1.json")
    string_config = load_flight_string_generation_config(
        ROOT / "data/config/phase5_test_string_generation_v1.json"
    )
    cg_config = load_aircraft_string_column_generation_config(
        ROOT / "data/config/phase9_test_aircraft_string_cg_v1.json"
    )
    full_pool = generate_aircraft_strings(
        scenario, columns.flight_options, None, string_config
    )
    if required_ids is None:
        originals = resolve_original_flight_option_ids(
            scenario, columns.flight_options
        )
        required_ids = tuple(originals.values())
    request = AircraftRecoveryRequest.from_option_ids(
        scenario.scenario_id, required_ids
    )
    with GurobiAdapter(output_flag=False) as solver:
        full = solve_full_column_aircraft_string_lp(
            scenario,
            columns.flight_options,
            full_pool,
            request,
            costs,
            string_config,
            solver,
        )
    cg = solve_aircraft_string_column_generation(
        scenario,
        columns.flight_options,
        request,
        costs,
        string_config,
        cg_config,
        lambda: GurobiAdapter(output_flag=False),
    )
    assert len(full_pool) == expected_pool
    assert full.outcome.status is SolverStatus.OPTIMAL
    assert cg.status is AircraftStringColumnGenerationStatus.OPTIMAL
    assert cg.objective_value == pytest.approx(full.objective_value, abs=1e-7)
    assert {item.string_id for item in cg.columns} <= {
        item.string_id for item in full_pool
    }
    audit = audit_aircraft_string_column_generation_termination(
        scenario,
        columns.flight_options,
        full_pool,
        request,
        costs,
        string_config,
        cg_config,
        cg,
        lambda: GurobiAdapter(output_flag=False),
    )
    assert audit.passed
    assert audit.minimum_omitted_reduced_cost is None or (
        audit.minimum_omitted_reduced_cost >= -cg_config.pricing_epsilon
    )
