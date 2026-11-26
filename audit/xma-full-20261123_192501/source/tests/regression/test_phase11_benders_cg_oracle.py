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
)
from backend.core import (
    BendersCgStatus,
    IntegratedRecoveryRequest,
    generate_aircraft_strings,
    generate_crew_pairings,
    solve_benders_with_column_generation,
    solve_integrated_fixed_column_oracle,
)
from backend.schemas.columns import RecoveryColumns
from backend.schemas.scenario import Scenario
from backend.solver import GurobiAdapter, SolverStatus


ROOT = Path(__file__).parents[2]


def _profiles():
    costs = load_cost_config(ROOT / "data/costs/phase2_test_costs_v1.json")
    capacity = load_passenger_capacity_profile(
        ROOT / "data/capacities/toy_case_013_benders_column_generation_capacity.json"
    )
    string_config = load_flight_string_generation_config(
        ROOT / "data/config/phase5_test_string_generation_v1.json"
    )
    pairing_config = load_crew_pairing_generation_config(
        ROOT / "data/config/phase6_test_crew_pairing_generation_v1.json"
    )
    aircraft_cg = load_aircraft_string_column_generation_config(
        ROOT / "data/config/phase9_test_aircraft_string_cg_v1.json"
    )
    crew_cg = load_crew_pairing_column_generation_config(
        ROOT / "data/config/phase10_test_crew_pairing_cg_v1.json"
    )
    phase11 = load_benders_column_generation_config(
        ROOT / "data/config/phase11_test_benders_cg_v1.json"
    )
    return (
        costs,
        capacity,
        string_config,
        pairing_config,
        aircraft_cg,
        crew_cg,
        phase11,
    )


def _full_columns(scenario, base, string_config, pairing_config):
    strings = generate_aircraft_strings(
        scenario, base.flight_options, None, string_config
    )
    pairings = generate_crew_pairings(
        scenario, base.flight_options, None, pairing_config
    )
    return RecoveryColumns.model_validate(
        {
            **base.model_dump(mode="json"),
            "aircraft_strings": [item.model_dump(mode="json") for item in strings],
            "crew_pairings": [item.model_dump(mode="json") for item in pairings],
        }
    )


def test_toy13_matches_full_explicit_integrated_oracle(
    toy_case_013_benders_column_generation_data,
    toy_case_013_benders_column_generation_columns_data,
):
    available, reason = GurobiAdapter.availability()
    assert available, reason or "Gurobi is required for Phase 11 regression"
    scenario = Scenario.model_validate(toy_case_013_benders_column_generation_data)
    base = RecoveryColumns.model_validate(
        toy_case_013_benders_column_generation_columns_data
    )
    (
        costs,
        capacity,
        string_config,
        pairing_config,
        aircraft_cg,
        crew_cg,
        phase11,
    ) = _profiles()
    full = _full_columns(scenario, base, string_config, pairing_config)
    request = IntegratedRecoveryRequest(
        scenario.scenario_id, costs.cost_profile_id, capacity.capacity_profile_id
    )
    with GurobiAdapter(output_flag=False) as solver:
        oracle = solve_integrated_fixed_column_oracle(
            scenario, full, request, capacity, costs, solver
        )
    result = solve_benders_with_column_generation(
        scenario,
        base,
        capacity,
        costs,
        string_config,
        pairing_config,
        aircraft_cg,
        crew_cg,
        phase11,
        solver_factory=lambda: GurobiAdapter(output_flag=False),
    )
    assert len(full.aircraft_strings) == 2
    assert len(full.crew_pairings) >= 3
    assert oracle.status is SolverStatus.OPTIMAL
    assert result.status is BendersCgStatus.OPTIMAL
    assert result.objective_value == pytest.approx(220.0)
    assert result.objective_value == pytest.approx(oracle.objective_value)
    assert result.diagnostics["integrated_audit"]["all_constraints_satisfied"]


def test_formal_solver_is_independent_of_full_enumerators(
    monkeypatch,
    toy_case_013_benders_column_generation_data,
    toy_case_013_benders_column_generation_columns_data,
):
    def forbidden(*args, **kwargs):
        raise AssertionError("formal Phase 11 solver called a full enumerator")

    monkeypatch.setattr(
        "backend.core.string_generator.generate_aircraft_strings", forbidden
    )
    monkeypatch.setattr(
        "backend.core.string_generator.brute_force_legal_aircraft_strings", forbidden
    )
    monkeypatch.setattr(
        "backend.core.pairing_generator.generate_crew_pairings", forbidden
    )
    monkeypatch.setattr(
        "backend.core.pairing_generator.brute_force_legal_crew_pairings", forbidden
    )
    costs, capacity, strings, pairings, aircraft_cg, crew_cg, phase11 = _profiles()
    result = solve_benders_with_column_generation(
        toy_case_013_benders_column_generation_data,
        toy_case_013_benders_column_generation_columns_data,
        capacity,
        costs,
        strings,
        pairings,
        aircraft_cg,
        crew_cg,
        phase11,
        solver_factory=lambda: GurobiAdapter(output_flag=False),
    )
    assert result.status is BendersCgStatus.OPTIMAL
    assert result.objective_value == pytest.approx(220.0)
    assert result.diagnostics["formal_full_enumerators_used"] is False
