from pathlib import Path

import pytest

from backend.config import (
    load_aircraft_string_column_generation_config,
    load_benders_column_generation_config,
    load_cost_config,
    load_crew_pairing_column_generation_config,
    load_crew_pairing_generation_config,
    load_flight_string_generation_config,
    load_passenger_capacity_profile,
    load_passenger_itinerary_generation_config,
)
from backend.core import (
    BendersCgStatus,
    IntegratedRecoveryRequest,
    build_recovery_scope,
    generate_aircraft_strings,
    generate_crew_pairings,
    generate_passenger_itineraries,
    replace_passenger_itineraries,
    solve_benders_with_column_generation,
    solve_integrated_fixed_column_oracle,
)
from backend.schemas.columns import RecoveryColumns
from backend.schemas.scenario import Scenario
from backend.solver import GurobiAdapter, SolverStatus


ROOT = Path(__file__).parents[2]


def _phase7_universe(scenario, manual, string_config, pairing_config):
    strings = generate_aircraft_strings(
        scenario, manual.flight_options, None, string_config
    )
    phase5 = RecoveryColumns.model_validate(
        {
            **manual.model_dump(mode="json"),
            "aircraft_strings": [item.model_dump(mode="json") for item in strings],
        }
    )
    pairings = generate_crew_pairings(
        scenario,
        phase5.flight_options,
        build_recovery_scope(scenario, phase5),
        pairing_config,
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
            ROOT / "data/config/phase7_test_itinerary_generation_v1.json"
        ),
    )
    return replace_passenger_itineraries(phase6, itineraries)


def test_phase1_benchmark_matches_full_explicit_integrated_oracle(
    phase1_benchmark_001_data, phase1_columns_001_data
):
    available, reason = GurobiAdapter.availability()
    assert available, reason or "Gurobi is required for Phase 11 benchmark"
    scenario = Scenario.model_validate(phase1_benchmark_001_data)
    manual = RecoveryColumns.model_validate(phase1_columns_001_data)
    costs = load_cost_config(ROOT / "data/costs/phase2_test_costs_v1.json")
    capacity = load_passenger_capacity_profile(
        ROOT / "data/capacities/phase2_test_seat_capacity_v1.json"
    )
    string_config = load_flight_string_generation_config(
        ROOT / "data/config/phase5_test_string_generation_v1.json"
    )
    pairing_config = load_crew_pairing_generation_config(
        ROOT / "data/config/phase6_test_crew_pairing_generation_v1.json"
    )
    full = _phase7_universe(scenario, manual, string_config, pairing_config)
    formal = RecoveryColumns.model_validate(
        {
            **full.model_dump(mode="json"),
            "aircraft_strings": [],
            "crew_pairings": [],
        }
    )
    request = IntegratedRecoveryRequest(
        scenario.scenario_id, costs.cost_profile_id, capacity.capacity_profile_id
    )
    with GurobiAdapter(output_flag=False) as solver:
        oracle = solve_integrated_fixed_column_oracle(
            scenario, full, request, capacity, costs, solver
        )
    result = solve_benders_with_column_generation(
        scenario,
        formal,
        capacity,
        costs,
        string_config,
        pairing_config,
        load_aircraft_string_column_generation_config(
            ROOT / "data/config/phase9_test_aircraft_string_cg_v1.json"
        ),
        load_crew_pairing_column_generation_config(
            ROOT / "data/config/phase10_test_crew_pairing_cg_v1.json"
        ),
        load_benders_column_generation_config(
            ROOT / "data/config/phase11_test_benders_cg_v1.json"
        ),
        solver_factory=lambda: GurobiAdapter(output_flag=False),
    )
    assert len(full.aircraft_strings) == 77
    assert len(full.crew_pairings) == 374
    assert len(full.passenger_itineraries) == 55
    assert formal.aircraft_strings == []
    assert formal.crew_pairings == []
    assert oracle.status is SolverStatus.OPTIMAL
    assert result.status is BendersCgStatus.OPTIMAL
    assert result.objective_value == pytest.approx(18080.0)
    assert result.objective_value == pytest.approx(oracle.objective_value)
    assert result.lower_bound == pytest.approx(result.upper_bound)
    assert result.diagnostics["integrated_audit"]["all_constraints_satisfied"]
    assert result.diagnostics["metrics"]["aircraft_cg_calls"] >= 1
    assert result.diagnostics["metrics"]["crew_cg_calls"] >= 1
