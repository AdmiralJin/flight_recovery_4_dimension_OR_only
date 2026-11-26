from pathlib import Path

import pytest

from backend.config import (
    load_cost_config,
    load_flight_string_generation_config,
    load_passenger_capacity_profile,
)
from backend.core import (
    IntegratedRecoveryRequest,
    generate_aircraft_strings_with_metrics,
    solve_integrated_fixed_column_oracle,
)
from backend.schemas.columns import RecoveryColumns
from backend.schemas.scenario import Scenario
from backend.services.column_validator import validate_recovery_columns
from backend.solver import GurobiAdapter, SolverStatus


ROOT = Path(__file__).parents[2]


def test_generated_benchmark_strings_cover_manual_keys_and_preserve_objective(
    phase1_benchmark_001_data,
    phase1_columns_001_data,
):
    available, reason = GurobiAdapter.availability()
    assert available, reason or "Gurobi is required for Phase 5 regression"
    scenario = Scenario.model_validate(phase1_benchmark_001_data)
    manual_columns = RecoveryColumns.model_validate(phase1_columns_001_data)
    config = load_flight_string_generation_config(
        ROOT / "data" / "config" / "phase5_test_string_generation_v1.json"
    )
    generated = generate_aircraft_strings_with_metrics(
        scenario, manual_columns.flight_options, None, config
    )
    manual_keys = {
        (
            item.aircraft_id,
            tuple(item.leg_option_ids),
            item.start_station,
            item.end_station,
            item.maintenance_satisfied,
        )
        for item in manual_columns.aircraft_strings
    }
    generated_keys = {
        (
            item.aircraft_id,
            tuple(item.leg_option_ids),
            item.start_station,
            item.end_station,
            item.maintenance_satisfied,
        )
        for item in generated.strings
    }
    assert manual_keys <= generated_keys
    assert len(manual_keys) == 11
    assert len(generated_keys) == 77

    generated_columns_data = {
        **phase1_columns_001_data,
        "aircraft_strings": [
            item.model_dump(mode="json") for item in generated.strings
        ],
    }
    validated, issues = validate_recovery_columns(
        scenario, generated_columns_data
    )
    assert validated is not None
    assert issues == []

    costs = load_cost_config(
        ROOT / "data" / "costs" / "phase2_test_costs_v1.json"
    )
    capacity = load_passenger_capacity_profile(
        ROOT / "data" / "capacities" / "phase2_test_seat_capacity_v1.json"
    )
    request = IntegratedRecoveryRequest(
        scenario.scenario_id,
        costs.cost_profile_id,
        capacity.capacity_profile_id,
    )
    with GurobiAdapter(output_flag=False) as solver:
        result = solve_integrated_fixed_column_oracle(
            phase1_benchmark_001_data,
            generated_columns_data,
            request,
            capacity,
            costs,
            solver,
        )

    assert result.status is SolverStatus.OPTIMAL
    assert result.objective_value == pytest.approx(18080.0)
    assert result.diagnostics["all_constraints_satisfied"]
    assert result.diagnostics["cross_model_audit"]["all_constraints_satisfied"]
    assert generated.metrics["generated_string_count"] == 77
