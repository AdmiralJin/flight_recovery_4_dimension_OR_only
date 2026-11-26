from pathlib import Path

import pytest

from backend.config import (
    load_cost_config,
    load_crew_pairing_generation_config,
    load_flight_string_generation_config,
    load_passenger_capacity_profile,
)
from backend.core import (
    IntegratedRecoveryRequest,
    build_recovery_scope,
    generate_aircraft_strings,
    generate_crew_pairings_with_metrics,
    solve_integrated_fixed_column_oracle,
)
from backend.schemas.columns import RecoveryColumns
from backend.schemas.scenario import Scenario
from backend.services.column_validator import validate_recovery_columns
from backend.solver import GurobiAdapter, SolverStatus


ROOT = Path(__file__).parents[2]


def _semantic_key(pairing):
    return (
        pairing.crew_id,
        tuple(
            (segment.segment_type.value, segment.flight_option_id)
            for duty in pairing.duties
            for segment in duty.segments
        ),
        pairing.start_station,
        pairing.end_station,
    )


def test_generated_benchmark_pairings_cover_manual_and_preserve_objective(
    phase1_benchmark_001_data,
    phase1_columns_001_data,
):
    available, reason = GurobiAdapter.availability()
    assert available, reason or "Gurobi is required for Phase 6 regression"
    scenario = Scenario.model_validate(phase1_benchmark_001_data)
    manual_columns = RecoveryColumns.model_validate(phase1_columns_001_data)

    string_config = load_flight_string_generation_config(
        ROOT / "data" / "config" / "phase5_test_string_generation_v1.json"
    )
    generated_strings = generate_aircraft_strings(
        scenario, manual_columns.flight_options, None, string_config
    )
    phase5_data = {
        **phase1_columns_001_data,
        "aircraft_strings": [
            item.model_dump(mode="json") for item in generated_strings
        ],
    }
    phase5_columns = RecoveryColumns.model_validate(phase5_data)
    scope_before = build_recovery_scope(scenario, phase5_columns)

    pairing_config = load_crew_pairing_generation_config(
        ROOT / "data" / "config" / "phase6_test_crew_pairing_generation_v1.json"
    )
    generated = generate_crew_pairings_with_metrics(
        scenario, phase5_columns.flight_options, scope_before, pairing_config
    )
    manual_keys = {_semantic_key(item) for item in manual_columns.crew_pairings}
    generated_keys = {_semantic_key(item) for item in generated.pairings}
    assert manual_keys <= generated_keys
    assert len(manual_keys) == 10
    assert len(generated_keys) == 374
    assert generated.metrics["deadhead_leg_count"] > 0

    phase6_data = {
        **phase5_data,
        "crew_pairings": [item.model_dump(mode="json") for item in generated.pairings],
    }
    phase6_columns = RecoveryColumns.model_validate(phase6_data)
    scope_after = build_recovery_scope(scenario, phase6_columns)
    assert scope_before.crew_ids == scope_after.crew_ids
    assert len(scope_after.crew_pairing_ids) == 374

    validated, issues = validate_recovery_columns(scenario, phase6_data)
    assert validated is not None
    assert issues == []

    costs = load_cost_config(ROOT / "data" / "costs" / "phase2_test_costs_v1.json")
    capacity = load_passenger_capacity_profile(
        ROOT / "data" / "capacities" / "phase2_test_seat_capacity_v1.json"
    )
    request = IntegratedRecoveryRequest(
        scenario.scenario_id,
        costs.cost_profile_id,
        capacity.capacity_profile_id,
    )
    with GurobiAdapter(output_flag=False) as solver:
        full_result = solve_integrated_fixed_column_oracle(
            phase1_benchmark_001_data,
            phase6_data,
            request,
            capacity,
            costs,
            solver,
        )
    with GurobiAdapter(output_flag=False) as solver:
        scoped_result = solve_integrated_fixed_column_oracle(
            phase1_benchmark_001_data,
            phase6_data,
            request,
            capacity,
            costs,
            solver,
            scope=scope_after,
        )

    assert full_result.status is SolverStatus.OPTIMAL
    assert scoped_result.status is SolverStatus.OPTIMAL
    assert full_result.objective_value == pytest.approx(18080.0)
    assert scoped_result.objective_value == pytest.approx(
        full_result.objective_value, abs=1e-6
    )
    assert full_result.diagnostics["all_constraints_satisfied"]
    assert full_result.diagnostics["cross_model_audit"]["all_constraints_satisfied"]
    assert scoped_result.diagnostics["all_constraints_satisfied"]
    assert scoped_result.diagnostics["cross_model_audit"]["all_constraints_satisfied"]
    assert scoped_result.diagnostics["scope_fix_audit"]["all_constraints_satisfied"]
