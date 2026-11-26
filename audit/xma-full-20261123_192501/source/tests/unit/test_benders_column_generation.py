from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.config import (
    BendersColumnGenerationConfigError,
    load_aircraft_string_column_generation_config,
    load_benders_column_generation_config,
    load_cost_config,
    load_crew_pairing_column_generation_config,
    load_crew_pairing_generation_config,
    load_flight_string_generation_config,
    load_passenger_capacity_profile,
)
from backend.core import (
    BendersCgCut,
    BendersCgCutSource,
    BendersCgStatus,
    BendersColumnGenerationError,
    BendersCutType,
    BendersSubproblem,
    RecoveryScope,
    benders_cg_implicit_universe_fingerprint,
    solve_benders_with_column_generation,
)
from backend.schemas.columns import RecoveryColumns
from backend.schemas.scenario import Scenario
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


def _solve(data, columns_data):
    capacity, costs, strings, pairings, aircraft_cg, crew_cg, config = _profiles()
    return solve_benders_with_column_generation(
        data,
        columns_data,
        capacity,
        costs,
        strings,
        pairings,
        aircraft_cg,
        crew_cg,
        config,
        solver_factory=lambda: GurobiAdapter(output_flag=False),
    )


def test_phase11_config_is_strict_frozen_and_rejects_duplicate_keys(tmp_path):
    config = _profiles()[-1]
    assert config.require_full_scope is True
    with pytest.raises(ValidationError):
        config.max_benders_iterations = 1
    raw = config.model_dump(mode="json")
    raw["require_full_scope"] = False
    with pytest.raises(ValidationError):
        type(config).model_validate(raw)
    raw = config.model_dump(mode="json")
    raw["unexpected"] = 1
    with pytest.raises(ValidationError):
        type(config).model_validate(raw)

    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text(
        '{"schema_version":"1.0.0","schema_version":"1.0.0"}',
        encoding="utf-8",
    )
    with pytest.raises(BendersColumnGenerationConfigError, match="duplicate JSON key"):
        load_benders_column_generation_config(duplicate)


def test_cut_provenance_rejects_restricted_or_binary_sources():
    cut = BendersCgCut(
        BendersCutType.OPTIMALITY,
        BendersSubproblem.ARM,
        ("A",),
        10.0,
        10.0,
        BendersCgCutSource.AIRCRAFT_FULL_LP,
        "universe",
        "certificate",
    )
    assert cut.key == ("optimality", "arm", ("A",), "universe")
    assert cut.cut_id.startswith("BCG_O_ARM_")
    with pytest.raises(BendersColumnGenerationError, match="does not match"):
        BendersCgCut(
            BendersCutType.OPTIMALITY,
            BendersSubproblem.ARM,
            ("A",),
            10.0,
            10.0,
            BendersCgCutSource.CREW_FULL_LP,
            "universe",
            "certificate",
        )
    with pytest.raises(BendersColumnGenerationError, match="infeasibility"):
        BendersCgCut(
            BendersCutType.FEASIBILITY,
            None,
            ("A",),
            None,
            None,
            BendersCgCutSource.AIRCRAFT_FULL_LP,
            "universe",
            "certificate",
        )


def test_fingerprint_is_order_stable_and_excludes_dynamic_pool_ids(
    toy_case_013_benders_column_generation_data,
    toy_case_013_benders_column_generation_columns_data,
):
    scenario = Scenario.model_validate(toy_case_013_benders_column_generation_data)
    columns = RecoveryColumns.model_validate(
        toy_case_013_benders_column_generation_columns_data
    )
    capacity, costs, strings, pairings, aircraft_cg, crew_cg, config = _profiles()
    first = benders_cg_implicit_universe_fingerprint(
        scenario,
        columns,
        capacity,
        costs,
        strings,
        pairings,
        aircraft_cg,
        crew_cg,
        config,
    )
    reordered = columns.model_copy(
        update={
            "flight_options": list(reversed(columns.flight_options)),
            "passenger_itineraries": list(reversed(columns.passenger_itineraries)),
        }
    )
    assert first == benders_cg_implicit_universe_fingerprint(
        scenario,
        reordered,
        capacity,
        costs,
        strings,
        pairings,
        aircraft_cg,
        crew_cg,
        config,
    )


def test_scope_is_explicitly_rejected(
    toy_case_013_benders_column_generation_data,
    toy_case_013_benders_column_generation_columns_data,
):
    scope = RecoveryScope(
        direct_flight_ids=(),
        flight_ids=(),
        aircraft_ids=(),
        crew_ids=(),
        passenger_group_ids=(),
        flight_option_ids=(),
        aircraft_string_ids=(),
        crew_pairing_ids=(),
        passenger_itinerary_ids=(),
        propagation_reasons={},
        iteration_count=1,
    )
    capacity, costs, strings, pairings, aircraft_cg, crew_cg, config = _profiles()
    with pytest.raises(BendersColumnGenerationError, match="UNSUPPORTED_DYNAMIC_SCOPE"):
        solve_benders_with_column_generation(
            toy_case_013_benders_column_generation_data,
            toy_case_013_benders_column_generation_columns_data,
            capacity,
            costs,
            strings,
            pairings,
            aircraft_cg,
            crew_cg,
            config,
            solver_factory=lambda: GurobiAdapter(output_flag=False),
            scope=scope,
        )


def test_toy13_benders_cg_uses_certified_cuts_and_integer_incumbent(
    toy_case_013_benders_column_generation_data,
    toy_case_013_benders_column_generation_columns_data,
):
    result = _solve(
        toy_case_013_benders_column_generation_data,
        toy_case_013_benders_column_generation_columns_data,
    )
    assert result.status is BendersCgStatus.OPTIMAL
    assert result.objective_value == pytest.approx(220.0)
    assert result.lower_bound == pytest.approx(result.upper_bound)
    assert result.selected_flight_options == ("FO_T13_F1_D20",)
    assert len(result.iterations) >= 2
    assert result.iterations[0].aircraft_cg_status == "infeasible"
    assert result.diagnostics["cut_counts"]["feasibility"] >= 1
    assert result.diagnostics["cut_counts"]["aircraft_full_lp"] >= 1
    assert result.diagnostics["cut_counts"]["crew_full_lp"] >= 1
    assert result.diagnostics["cut_counts"]["passenger_exact_mip"] >= 1
    assert result.diagnostics["integrated_audit"]["all_constraints_satisfied"]
    assert all(
        item.source
        in {
            BendersCgCutSource.AIRCRAFT_FULL_LP,
            BendersCgCutSource.CREW_FULL_LP,
            BendersCgCutSource.PASSENGER_EXACT_MIP,
            BendersCgCutSource.AIRCRAFT_LP_INFEASIBILITY,
            BendersCgCutSource.CREW_LP_INFEASIBILITY,
            BendersCgCutSource.PASSENGER_MIP_INFEASIBILITY,
        }
        for item in result.cuts
    )
