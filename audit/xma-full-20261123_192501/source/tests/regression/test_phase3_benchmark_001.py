from pathlib import Path

import pytest

from backend.config import load_cost_config, load_passenger_capacity_profile
from backend.core import (
    IntegratedRecoveryRequest,
    audit_integrated_candidate,
    build_integrated_fixed_column_oracle,
    solve_integrated_fixed_column_oracle,
)
from backend.schemas.columns import RecoveryColumns
from backend.schemas.scenario import Scenario
from backend.solver import GurobiAdapter, SolverStatus


ROOT = Path(__file__).parents[2]


def test_phase3_benchmark_is_jointly_optimal_and_bounded_by_manual_reference(
    phase1_benchmark_001_data,
    phase1_columns_001_data,
    phase1_expected_001_data,
):
    available, reason = GurobiAdapter.availability()
    assert available, reason or "Gurobi is required for Phase 3 benchmark"
    costs = load_cost_config(ROOT / "data" / "costs" / "phase2_test_costs_v1.json")
    capacity = load_passenger_capacity_profile(
        ROOT / "data" / "capacities" / "phase2_test_seat_capacity_v1.json"
    )
    request = IntegratedRecoveryRequest(
        "phase1_benchmark_001", costs.cost_profile_id, capacity.capacity_profile_id
    )
    scenario = Scenario.model_validate(phase1_benchmark_001_data)
    columns = RecoveryColumns.model_validate(phase1_columns_001_data)
    reference = phase1_expected_001_data["reference_solution"]

    with GurobiAdapter(output_flag=False) as solver:
        audit_model = build_integrated_fixed_column_oracle(
            scenario, columns, request, capacity, costs, solver
        )
        manual_audit = audit_integrated_candidate(
            audit_model,
            selected_option_by_flight=reference["selected_flight_option_by_flight"],
            selected_string_by_aircraft=reference["selected_aircraft_string_by_aircraft"],
            selected_pairing_by_crew=reference["selected_crew_pairing_by_crew"],
            selected_itinerary_by_group=reference["selected_passenger_itinerary_by_group"],
        )
    with GurobiAdapter(output_flag=False) as solver:
        result = solve_integrated_fixed_column_oracle(
            phase1_benchmark_001_data,
            phase1_columns_001_data,
            request,
            capacity,
            costs,
            solver,
        )

    assert manual_audit["all_constraints_satisfied"]
    manual_objective = manual_audit["objective_breakdown"]["grand_total"]
    assert manual_objective == pytest.approx(18080.0)
    assert result.status is SolverStatus.OPTIMAL
    assert result.solver_name == "Gurobi"
    assert result.objective_value <= manual_objective + 1e-6
    assert result.objective_value == pytest.approx(18080.0)
    diagnostics = result.diagnostics
    assert diagnostics["model"] == "INTEGRATED"
    assert diagnostics["single_model_only"] is False
    assert diagnostics["all_constraints_satisfied"]
    assert diagnostics["constraint_violation_count"] == 0
    assert diagnostics["cross_model_audit"]["all_constraints_satisfied"]
    assert diagnostics["objective_breakdown"] == {
        "srm": {"flight_delay": 80.0, "flight_cancellation": 0.0, "origin_change": 0.0, "destination_change": 0.0, "total": 80.0},
        "arm": {"aircraft_reassignment": 0.0, "ferry": 0.0, "total": 0.0},
        "crm": {"crew_reassignment": 0.0, "deadhead": 0.0, "total": 0.0},
        "prm": {"passenger_delay": 18000.0, "unserved_passenger": 0.0, "total": 18000.0},
        "srm_total": 80.0,
        "arm_total": 0.0,
        "crm_total": 0.0,
        "prm_total": 18000.0,
        "grand_total": 18080.0,
    }
