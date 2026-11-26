from pathlib import Path

import pytest

from backend.config import (
    CostOverrideConfig,
    apply_cost_overrides,
    load_aircraft_string_column_generation_config,
    load_benders_column_generation_config,
    load_branch_and_price_config,
    load_cost_config,
    load_crew_pairing_column_generation_config,
    load_crew_pairing_generation_config,
    load_flight_string_generation_config,
    load_passenger_capacity_profile,
)
from backend.core import (
    BendersBranchAndPriceStatus,
    BendersCgStatus,
    IntegratedRecoveryRequest,
    generate_aircraft_strings,
    generate_crew_pairings,
    solve_benders_with_branch_and_price,
    solve_benders_with_column_generation,
    solve_integrated_fixed_column_oracle,
)
from backend.schemas.columns import RecoveryColumns
from backend.schemas.scenario import Scenario
from backend.solver import GurobiAdapter, SolverStatus


ROOT = Path(__file__).parents[2]


def _profiles():
    base_costs = load_cost_config(ROOT / "data/costs/phase2_test_costs_v1.json")
    costs = apply_cost_overrides(
        base_costs,
        CostOverrideConfig(
            base_cost_profile_id=base_costs.cost_profile_id,
            overrides={"crew_reassignment": 100.0, "deadhead_per_minute": 1.0},
        ),
    )
    return (
        costs,
        load_passenger_capacity_profile(
            ROOT / "data/capacities/toy_case_016_benders_branch_and_price_capacity.json"
        ),
        load_flight_string_generation_config(
            ROOT / "data/config/phase5_test_string_generation_v1.json"
        ),
        load_crew_pairing_generation_config(
            ROOT / "data/config/phase6_test_crew_pairing_generation_v1.json"
        ),
        load_aircraft_string_column_generation_config(
            ROOT / "data/config/phase9_test_aircraft_string_cg_v1.json"
        ),
        load_crew_pairing_column_generation_config(
            ROOT / "data/config/phase10_test_crew_pairing_cg_v1.json"
        ),
        load_benders_column_generation_config(
            ROOT / "data/config/phase11_test_benders_cg_v1.json"
        ),
        load_branch_and_price_config(
            ROOT / "data/config/phase12_test_branch_and_price_v1.json"
        ),
    )


def _solve_phase12(scenario, columns):
    costs, capacity, strings, pairings, aircraft_cg, crew_cg, benders, branch = (
        _profiles()
    )
    return solve_benders_with_branch_and_price(
        scenario,
        columns,
        capacity,
        costs,
        strings,
        pairings,
        aircraft_cg,
        crew_cg,
        benders,
        branch,
        solver_factory=lambda: GurobiAdapter(output_flag=False),
    )


def test_phase11_integrality_boundary_is_closed_exactly_by_phase12(
    toy_case_016_benders_branch_and_price_data,
    toy_case_016_benders_branch_and_price_columns_data,
):
    scenario = Scenario.model_validate(toy_case_016_benders_branch_and_price_data)
    columns = RecoveryColumns.model_validate(
        toy_case_016_benders_branch_and_price_columns_data
    )
    costs, capacity, strings, pairings, aircraft_cg, crew_cg, benders, _ = _profiles()
    phase11 = solve_benders_with_column_generation(
        scenario,
        columns,
        capacity,
        costs,
        strings,
        pairings,
        aircraft_cg,
        crew_cg,
        benders,
        solver_factory=lambda: GurobiAdapter(output_flag=False),
    )
    phase12 = _solve_phase12(scenario, columns)
    full = columns.model_copy(
        update={
            "aircraft_strings": generate_aircraft_strings(
                scenario, columns.flight_options, None, strings
            ),
            "crew_pairings": generate_crew_pairings(
                scenario, columns.flight_options, None, pairings
            ),
        }
    )
    request = IntegratedRecoveryRequest(
        scenario.scenario_id, costs.cost_profile_id, capacity.capacity_profile_id
    )
    with GurobiAdapter(output_flag=False) as solver:
        oracle = solve_integrated_fixed_column_oracle(
            scenario, full, request, capacity, costs, solver
        )
    assert phase11.status is BendersCgStatus.INTEGRALITY_REQUIRED
    assert phase11.lower_bound == pytest.approx(95195.0)
    assert phase12.status is BendersBranchAndPriceStatus.OPTIMAL
    assert phase12.objective_value == pytest.approx(95200.0)
    assert phase12.lower_bound == pytest.approx(phase12.upper_bound)
    assert oracle.status is SolverStatus.OPTIMAL
    assert phase12.objective_value == pytest.approx(oracle.objective_value)
    assert phase12.diagnostics["integrated_audit"]["all_constraints_satisfied"]
    metrics = phase12.diagnostics["metrics"]
    assert metrics["schedules_requiring_aircraft_branch_and_price"] == 0
    assert metrics["schedules_requiring_crew_branch_and_price"] == 1
    assert metrics["crew_branch_and_price_nodes"] == 9
    assert metrics["exact_integer_cuts"] == 2


def test_phase12_formal_solver_does_not_call_full_enumerators(
    monkeypatch,
    toy_case_016_benders_branch_and_price_data,
    toy_case_016_benders_branch_and_price_columns_data,
):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("formal Phase 12 solver called a full enumerator")

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
    result = _solve_phase12(
        toy_case_016_benders_branch_and_price_data,
        toy_case_016_benders_branch_and_price_columns_data,
    )
    assert result.status is BendersBranchAndPriceStatus.OPTIMAL
    assert result.objective_value == pytest.approx(95200.0)
    assert result.diagnostics["formal_full_enumerators_used"] is False
