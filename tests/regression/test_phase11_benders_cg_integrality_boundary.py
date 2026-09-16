from pathlib import Path

import pytest

import backend.core.benders_column_generation as phase11_module
from backend.config import (
    load_aircraft_string_column_generation_config,
    load_benders_column_generation_config,
    load_cost_config,
    load_crew_pairing_column_generation_config,
    load_crew_pairing_generation_config,
    load_flight_string_generation_config,
    load_passenger_capacity_profile,
)
from backend.core import BendersCgCutSource, BendersCgStatus
from backend.solver import GurobiAdapter


ROOT = Path(__file__).parents[2]


def test_binary_recourse_is_only_an_upper_bound_and_exposes_phase12_boundary(
    monkeypatch,
    toy_case_013_benders_column_generation_data,
    toy_case_013_benders_column_generation_columns_data,
):
    real_solve = phase11_module.solve_fixed_column_arm

    def solve_with_artificial_integer_gap(*args, **kwargs):
        result = real_solve(*args, **kwargs)
        assert result.objective_value is not None
        return result.model_copy(
            update={"objective_value": result.objective_value + 1.0}
        )

    monkeypatch.setattr(
        phase11_module, "solve_fixed_column_arm", solve_with_artificial_integer_gap
    )
    capacity = load_passenger_capacity_profile(
        ROOT / "data/capacities/toy_case_013_benders_column_generation_capacity.json"
    )
    costs = load_cost_config(ROOT / "data/costs/phase2_test_costs_v1.json")
    result = phase11_module.solve_benders_with_column_generation(
        toy_case_013_benders_column_generation_data,
        toy_case_013_benders_column_generation_columns_data,
        capacity,
        costs,
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
        solver_factory=lambda: GurobiAdapter(output_flag=False),
    )
    assert result.status is BendersCgStatus.INTEGRALITY_REQUIRED
    assert result.lower_bound == pytest.approx(220.0)
    assert result.upper_bound == pytest.approx(221.0)
    assert result.diagnostics["terminal_reason"] == (
        "lp_integer_gap_requires_branching"
    )
    aircraft_cuts = [
        item
        for item in result.cuts
        if item.source is BendersCgCutSource.AIRCRAFT_FULL_LP
    ]
    assert aircraft_cuts
    assert all(
        item.recourse_lower_bound == pytest.approx(0.0) for item in aircraft_cuts
    )
    assert any(
        item.aircraft_binary_objective == pytest.approx(1.0)
        and item.aircraft_lp_objective == pytest.approx(0.0)
        for item in result.certificates
    )
