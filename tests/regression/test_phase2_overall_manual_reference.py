from pathlib import Path

import pytest

from backend.config import load_cost_config, load_passenger_capacity_profile
from backend.core import (
    AircraftRecoveryRequest,
    CrewRecoveryRequest,
    PassengerRecoveryRequest,
    solve_fixed_column_arm,
    solve_fixed_column_crm,
    solve_fixed_column_prm,
)
from backend.solver import GurobiAdapter, SolverStatus


ROOT = Path(__file__).parents[2]


def test_phase2_manual_reference_passes_three_independent_resource_models(
    phase1_benchmark_001_data,
    phase1_columns_001_data,
    phase1_expected_001_data,
):
    available, reason = GurobiAdapter.availability()
    assert available, reason or "Gurobi is required for the Phase 2 final smoke test"
    costs = load_cost_config(
        ROOT / "data" / "costs" / "phase2_test_costs_v1.json"
    )
    capacity = load_passenger_capacity_profile(
        ROOT / "data" / "capacities" / "phase2_test_seat_capacity_v1.json"
    )
    reference = phase1_expected_001_data["reference_solution"]
    required = tuple(reference["selected_flight_option_by_flight"].values())

    with GurobiAdapter(output_flag=False) as solver:
        arm_result = solve_fixed_column_arm(
            phase1_benchmark_001_data,
            phase1_columns_001_data,
            AircraftRecoveryRequest(
                phase1_benchmark_001_data["scenario_id"], required
            ),
            costs,
            solver,
        )
    with GurobiAdapter(output_flag=False) as solver:
        crm_result = solve_fixed_column_crm(
            phase1_benchmark_001_data,
            phase1_columns_001_data,
            CrewRecoveryRequest(
                phase1_benchmark_001_data["scenario_id"], required
            ),
            costs,
            solver,
        )
    with GurobiAdapter(output_flag=False) as solver:
        prm_result = solve_fixed_column_prm(
            phase1_benchmark_001_data,
            phase1_columns_001_data,
            PassengerRecoveryRequest(
                phase1_benchmark_001_data["scenario_id"],
                required,
                capacity.capacity_profile_id,
            ),
            capacity,
            costs,
            solver,
        )

    results = (arm_result, crm_result, prm_result)
    assert all(result.status is SolverStatus.OPTIMAL for result in results)
    assert all(result.solver_name == "Gurobi" for result in results)
    assert all(result.diagnostics["single_model_only"] for result in results)
    assert all(result.diagnostics["all_constraints_satisfied"] for result in results)
    assert arm_result.objective_value == pytest.approx(0.0)
    assert crm_result.objective_value == pytest.approx(0.0)
    assert prm_result.objective_value == pytest.approx(18000.0)

    # Deliberately no objective sum: these are three independent Phase 2 solves,
    # not an integrated model or integrated objective.
