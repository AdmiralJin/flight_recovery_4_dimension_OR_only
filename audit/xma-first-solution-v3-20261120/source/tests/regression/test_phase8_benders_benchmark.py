from pathlib import Path

import pytest

from backend.config import (
    load_cost_config,
    load_crew_pairing_generation_config,
    load_fixed_column_benders_config,
    load_flight_string_generation_config,
    load_passenger_capacity_profile,
    load_passenger_itinerary_generation_config,
)
from backend.core import (
    BendersStatus,
    IntegratedRecoveryRequest,
    build_recovery_scope,
    generate_aircraft_strings,
    generate_crew_pairings,
    generate_passenger_itineraries,
    replace_passenger_itineraries,
    solve_fixed_column_benders,
    solve_integrated_fixed_column_oracle,
)
from backend.schemas.columns import FlightOperationType, RecoveryColumns
from backend.schemas.scenario import Scenario
from backend.solver import GurobiAdapter, SolverStatus


ROOT = Path(__file__).parents[2]


def _phase7_columns(scenario, manual_columns):
    strings = generate_aircraft_strings(
        scenario,
        manual_columns.flight_options,
        None,
        load_flight_string_generation_config(
            ROOT / "data" / "config" / "phase5_test_string_generation_v1.json"
        ),
    )
    phase5 = RecoveryColumns.model_validate(
        {
            **manual_columns.model_dump(mode="json"),
            "aircraft_strings": [item.model_dump(mode="json") for item in strings],
        }
    )
    pairings = generate_crew_pairings(
        scenario,
        phase5.flight_options,
        build_recovery_scope(scenario, phase5),
        load_crew_pairing_generation_config(
            ROOT / "data" / "config" / "phase6_test_crew_pairing_generation_v1.json"
        ),
    )
    phase6 = RecoveryColumns.model_validate(
        {
            **phase5.model_dump(mode="json"),
            "crew_pairings": [item.model_dump(mode="json") for item in pairings],
        }
    )
    itineraries = generate_passenger_itineraries(
        scenario,
        phase6.flight_options,
        build_recovery_scope(scenario, phase6),
        load_passenger_itinerary_generation_config(
            ROOT / "data" / "config" / "phase7_test_itinerary_generation_v1.json"
        ),
    )
    return replace_passenger_itineraries(phase6, itineraries)


def test_phase7_candidate_universe_benders_matches_integrated_oracle(
    phase1_benchmark_001_data, phase1_columns_001_data
):
    available, reason = GurobiAdapter.availability()
    assert available, reason or "Gurobi is required for Phase 8 benchmark"
    scenario = Scenario.model_validate(phase1_benchmark_001_data)
    manual = RecoveryColumns.model_validate(phase1_columns_001_data)
    columns = _phase7_columns(scenario, manual)
    schedule_count = sum(
        item.operation_type in {FlightOperationType.OPERATE, FlightOperationType.CANCEL}
        for item in columns.flight_options
    )
    assert schedule_count == 21
    assert len(columns.aircraft_strings) == 77
    assert len(columns.crew_pairings) == 374
    assert len(columns.passenger_itineraries) == 55

    costs = load_cost_config(ROOT / "data" / "costs" / "phase2_test_costs_v1.json")
    capacity = load_passenger_capacity_profile(
        ROOT / "data" / "capacities" / "phase2_test_seat_capacity_v1.json"
    )
    config = load_fixed_column_benders_config(
        ROOT / "data" / "config" / "phase8_test_benders_v1.json"
    )
    benders = solve_fixed_column_benders(
        scenario,
        columns,
        capacity,
        costs,
        config,
        solver_factory=lambda: GurobiAdapter(output_flag=False),
    )
    request = IntegratedRecoveryRequest(
        scenario.scenario_id, costs.cost_profile_id, capacity.capacity_profile_id
    )
    with GurobiAdapter(output_flag=False) as solver:
        integrated = solve_integrated_fixed_column_oracle(
            scenario, columns, request, capacity, costs, solver
        )

    assert benders.status is BendersStatus.OPTIMAL
    assert integrated.status is SolverStatus.OPTIMAL
    assert benders.objective_value == pytest.approx(18080.0)
    assert benders.objective_value == pytest.approx(integrated.objective_value)
    assert len(benders.iterations) > 1
    assert benders.diagnostics["visited_schedule_count"] > 1
    assert benders.diagnostics["cut_counts"]["feasibility"] >= 1
    assert benders.diagnostics["cut_counts"]["arm_optimality"] >= 1
    assert benders.diagnostics["cut_counts"]["crm_optimality"] >= 1
    assert benders.diagnostics["cut_counts"]["prm_optimality"] >= 1
    assert benders.iterations[-1].lower_bound == pytest.approx(18080.0)
    assert benders.iterations[-1].incumbent_upper_bound == pytest.approx(18080.0)
    assert benders.iterations[-1].absolute_gap == pytest.approx(0.0)
    audit = benders.diagnostics["integrated_audit"]
    assert audit["all_constraints_satisfied"]
    assert audit["objective_breakdown"]["srm_total"] == pytest.approx(80.0)
    assert audit["objective_breakdown"]["arm_total"] == pytest.approx(0.0)
    assert audit["objective_breakdown"]["crm_total"] == pytest.approx(0.0)
    assert audit["objective_breakdown"]["prm_total"] == pytest.approx(18000.0)
