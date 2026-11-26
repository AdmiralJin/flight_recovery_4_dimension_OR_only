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
    BendersCgCutSource,
    BendersCgStatus,
    BendersColumnGenerationError,
    BendersCutType,
    solve_benders_with_column_generation,
)
from backend.solver import GurobiAdapter


ROOT = Path(__file__).parents[2]


def _profiles():
    return (
        load_passenger_capacity_profile(
            ROOT
            / "data/capacities/toy_case_013_benders_column_generation_capacity.json"
        ),
        load_cost_config(ROOT / "data/costs/phase2_test_costs_v1.json"),
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
    )


def _solve(data, columns, *, aircraft_cg=None):
    capacity, costs, strings, pairings, default_aircraft_cg, crew_cg, phase11 = (
        _profiles()
    )
    return solve_benders_with_column_generation(
        data,
        columns,
        capacity,
        costs,
        strings,
        pairings,
        aircraft_cg or default_aircraft_cg,
        crew_cg,
        phase11,
        solver_factory=lambda: GurobiAdapter(output_flag=False),
    )


def test_only_certified_full_recourse_values_create_permanent_cuts(
    toy_case_013_benders_column_generation_data,
    toy_case_013_benders_column_generation_columns_data,
):
    result = _solve(
        toy_case_013_benders_column_generation_data,
        toy_case_013_benders_column_generation_columns_data,
    )
    feasibility_schedules = [
        item.schedule_signature
        for item in result.cuts
        if item.cut_type is BendersCutType.FEASIBILITY
    ]
    assert len(feasibility_schedules) == len(set(feasibility_schedules))
    for cut in result.cuts:
        if cut.cut_type is BendersCutType.FEASIBILITY:
            assert cut.source in {
                BendersCgCutSource.AIRCRAFT_LP_INFEASIBILITY,
                BendersCgCutSource.CREW_LP_INFEASIBILITY,
                BendersCgCutSource.PASSENGER_MIP_INFEASIBILITY,
            }
            continue
        assert cut.source in {
            BendersCgCutSource.AIRCRAFT_FULL_LP,
            BendersCgCutSource.CREW_FULL_LP,
            BendersCgCutSource.PASSENGER_EXACT_MIP,
        }
        assert cut.conditional_m == pytest.approx(cut.recourse_lower_bound)
        certificate = next(
            item
            for item in result.certificates
            if item.certificate_id == cut.certificate_id
        )
        if cut.source is BendersCgCutSource.AIRCRAFT_FULL_LP:
            assert cut.recourse_lower_bound == pytest.approx(
                certificate.aircraft_lp_objective
            )
        elif cut.source is BendersCgCutSource.CREW_FULL_LP:
            assert cut.recourse_lower_bound == pytest.approx(
                certificate.crew_lp_objective
            )
        else:
            assert cut.recourse_lower_bound == pytest.approx(certificate.prm_objective)


def test_cg_nonconvergence_returns_without_an_uncertified_cut(
    toy_case_013_benders_column_generation_data,
    toy_case_013_benders_column_generation_columns_data,
):
    aircraft_cg = _profiles()[4].model_copy(update={"max_iterations": 1})
    result = _solve(
        toy_case_013_benders_column_generation_data,
        toy_case_013_benders_column_generation_columns_data,
        aircraft_cg=aircraft_cg,
    )
    assert result.status is BendersCgStatus.NOT_CONVERGED
    assert result.diagnostics["terminal_reason"] == "aircraft_cg_not_converged"
    assert all(item.schedule_signature != ("FO_T13_F1_D10",) for item in result.cuts)


def test_formal_input_rejects_pre_generated_dynamic_columns(
    toy_case_013_benders_column_generation_data,
    toy_case_013_benders_column_generation_columns_data,
):
    columns = dict(toy_case_013_benders_column_generation_columns_data)
    columns["aircraft_strings"] = [
        {
            "string_id": "PREGENERATED",
            "aircraft_id": "T13_AC1",
            "leg_option_ids": ["FO_T13_F1_D10"],
            "start_station": "A",
            "end_station": "B",
            "maintenance_satisfied": True,
            "cost_components": {},
            "notes": "must not enter the formal Phase 11 input",
        }
    ]
    with pytest.raises(BendersColumnGenerationError, match="must not contain"):
        _solve(toy_case_013_benders_column_generation_data, columns)
