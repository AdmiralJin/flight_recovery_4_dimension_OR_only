from pathlib import Path

import pytest

from backend.config import (
    load_cost_config,
    load_crew_pairing_generation_config,
    load_flight_string_generation_config,
    load_passenger_capacity_profile,
    load_passenger_itinerary_generation_config,
)
from backend.core import (
    IntegratedRecoveryRequest,
    PassengerRecoveryRequest,
    build_recovery_scope,
    generate_aircraft_strings,
    generate_crew_pairings,
    generate_passenger_itineraries_with_metrics,
    itinerary_semantic_key,
    replace_passenger_itineraries,
    scope_metrics,
    solve_fixed_column_prm,
    solve_integrated_fixed_column_oracle,
    validate_recovery_scope,
)
from backend.schemas.columns import RecoveryColumns
from backend.schemas.scenario import Scenario
from backend.services.column_validator import validate_recovery_columns
from backend.solver import GurobiAdapter, SolverStatus


ROOT = Path(__file__).parents[2]


def test_generated_benchmark_itineraries_cover_manual_and_preserve_oracles(
    phase1_benchmark_001_data,
    phase1_columns_001_data,
    phase1_expected_001_data,
):
    available, reason = GurobiAdapter.availability()
    assert available, reason or "Gurobi is required for Phase 7 regression"
    scenario = Scenario.model_validate(phase1_benchmark_001_data)
    manual_columns = RecoveryColumns.model_validate(phase1_columns_001_data)

    string_config = load_flight_string_generation_config(
        ROOT / "data" / "config" / "phase5_test_string_generation_v1.json"
    )
    generated_strings = generate_aircraft_strings(
        scenario, manual_columns.flight_options, None, string_config
    )
    phase5_columns = RecoveryColumns.model_validate(
        {
            **phase1_columns_001_data,
            "aircraft_strings": [
                item.model_dump(mode="json") for item in generated_strings
            ],
        }
    )
    scope_after_strings = build_recovery_scope(scenario, phase5_columns)

    pairing_config = load_crew_pairing_generation_config(
        ROOT / "data" / "config" / "phase6_test_crew_pairing_generation_v1.json"
    )
    generated_pairings = generate_crew_pairings(
        scenario,
        phase5_columns.flight_options,
        scope_after_strings,
        pairing_config,
    )
    phase6_columns = RecoveryColumns.model_validate(
        {
            **phase5_columns.model_dump(mode="json"),
            "crew_pairings": [
                item.model_dump(mode="json") for item in generated_pairings
            ],
        }
    )
    scope_before = build_recovery_scope(scenario, phase6_columns)

    itinerary_config = load_passenger_itinerary_generation_config(
        ROOT / "data" / "config" / "phase7_test_itinerary_generation_v1.json"
    )
    generated = generate_passenger_itineraries_with_metrics(
        scenario,
        phase6_columns.flight_options,
        scope_before,
        itinerary_config,
    )
    manual_keys = {
        itinerary_semantic_key(item) for item in manual_columns.passenger_itineraries
    }
    generated_keys = {itinerary_semantic_key(item) for item in generated.itineraries}
    assert manual_keys <= generated_keys
    assert len(manual_keys) == 17
    assert len(generated_keys) == 55
    assert generated.metrics["generated_transported_count"] == 47
    assert generated.metrics["generated_unserved_count"] == 8
    assert all(
        status == "legal"
        for status in generated.metrics["original_itinerary_status_by_group"].values()
    )

    phase7_columns = replace_passenger_itineraries(
        phase6_columns, generated.itineraries
    )
    phase7_data = phase7_columns.model_dump(mode="json")
    validated, issues = validate_recovery_columns(scenario, phase7_data)
    assert validated is not None
    assert issues == []
    scope_after = build_recovery_scope(scenario, phase7_columns)
    validate_recovery_scope(scenario, phase7_columns, scope_after)
    before_metrics = scope_metrics(scenario, phase6_columns, scope_before)
    after_metrics = scope_metrics(scenario, phase7_columns, scope_after)
    assert before_metrics["total_candidates"]["w"] == 17
    assert after_metrics["total_candidates"]["w"] == 55
    assert after_metrics["free_candidates"]["w"] == 55
    assert after_metrics["total_binary_candidates"] == 527
    assert after_metrics["free_binary_candidates"] == 527

    costs = load_cost_config(ROOT / "data" / "costs" / "phase2_test_costs_v1.json")
    capacity = load_passenger_capacity_profile(
        ROOT / "data" / "capacities" / "phase2_test_seat_capacity_v1.json"
    )
    reference = phase1_expected_001_data["reference_solution"]
    required = tuple(reference["selected_flight_option_by_flight"].values())
    prm_request = PassengerRecoveryRequest(
        scenario.scenario_id,
        required,
        capacity.capacity_profile_id,
    )
    with GurobiAdapter(output_flag=False) as solver:
        prm_result = solve_fixed_column_prm(
            phase1_benchmark_001_data,
            phase7_data,
            prm_request,
            capacity,
            costs,
            solver,
        )
    assert prm_result.status is SolverStatus.OPTIMAL
    assert prm_result.objective_value == pytest.approx(18000.0)
    assert prm_result.diagnostics["all_constraints_satisfied"]
    assert prm_result.diagnostics["capacity_violations"] == []

    integrated_request = IntegratedRecoveryRequest(
        scenario.scenario_id,
        costs.cost_profile_id,
        capacity.capacity_profile_id,
    )
    with GurobiAdapter(output_flag=False) as solver:
        previous_result = solve_integrated_fixed_column_oracle(
            phase1_benchmark_001_data,
            phase6_columns.model_dump(mode="json"),
            integrated_request,
            capacity,
            costs,
            solver,
        )
    with GurobiAdapter(output_flag=False) as solver:
        full_result = solve_integrated_fixed_column_oracle(
            phase1_benchmark_001_data,
            phase7_data,
            integrated_request,
            capacity,
            costs,
            solver,
        )
    with GurobiAdapter(output_flag=False) as solver:
        scoped_result = solve_integrated_fixed_column_oracle(
            phase1_benchmark_001_data,
            phase7_data,
            integrated_request,
            capacity,
            costs,
            solver,
            scope=scope_after,
        )

    assert previous_result.status is SolverStatus.OPTIMAL
    assert full_result.status is SolverStatus.OPTIMAL
    assert scoped_result.status is SolverStatus.OPTIMAL
    assert previous_result.objective_value == pytest.approx(18080.0)
    assert full_result.objective_value == pytest.approx(previous_result.objective_value)
    assert scoped_result.objective_value == pytest.approx(full_result.objective_value)
    assert full_result.diagnostics["all_constraints_satisfied"]
    assert full_result.diagnostics["cross_model_audit"]["all_constraints_satisfied"]
    assert scoped_result.diagnostics["all_constraints_satisfied"]
    assert scoped_result.diagnostics["cross_model_audit"]["all_constraints_satisfied"]
    assert scoped_result.diagnostics["scope_fix_audit"]["all_constraints_satisfied"]
