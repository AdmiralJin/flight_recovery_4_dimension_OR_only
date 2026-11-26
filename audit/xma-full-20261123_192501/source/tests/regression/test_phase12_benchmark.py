from pathlib import Path

import pytest

from backend.config import (
    load_aircraft_string_column_generation_config,
    load_benders_column_generation_config,
    load_branch_and_price_config,
    load_cost_config,
    load_crew_pairing_column_generation_config,
    load_crew_pairing_generation_config,
    load_flight_string_generation_config,
    load_passenger_capacity_profile,
    load_passenger_itinerary_generation_config,
)
from backend.core import (
    BendersBranchAndPriceStatus,
    build_recovery_scope,
    generate_aircraft_strings,
    generate_crew_pairings,
    generate_passenger_itineraries,
    replace_passenger_itineraries,
    solve_benders_with_branch_and_price,
)
from backend.schemas.columns import RecoveryColumns
from backend.schemas.scenario import Scenario
from backend.solver import GurobiAdapter


ROOT = Path(__file__).parents[2]


def test_phase1_benchmark_remains_18080(
    phase1_benchmark_001_data, phase1_columns_001_data
):
    scenario = Scenario.model_validate(phase1_benchmark_001_data)
    manual = RecoveryColumns.model_validate(phase1_columns_001_data)
    string_config = load_flight_string_generation_config(
        ROOT / "data/config/phase5_test_string_generation_v1.json"
    )
    pairing_config = load_crew_pairing_generation_config(
        ROOT / "data/config/phase6_test_crew_pairing_generation_v1.json"
    )
    strings = generate_aircraft_strings(
        scenario, manual.flight_options, None, string_config
    )
    phase5 = manual.model_copy(update={"aircraft_strings": list(strings)})
    pairings = generate_crew_pairings(
        scenario,
        phase5.flight_options,
        build_recovery_scope(scenario, phase5),
        pairing_config,
    )
    phase6 = phase5.model_copy(update={"crew_pairings": list(pairings)})
    itineraries = generate_passenger_itineraries(
        scenario,
        phase6.flight_options,
        build_recovery_scope(scenario, phase6),
        load_passenger_itinerary_generation_config(
            ROOT / "data/config/phase7_test_itinerary_generation_v1.json"
        ),
    )
    full = replace_passenger_itineraries(phase6, itineraries)
    formal = full.model_copy(update={"aircraft_strings": [], "crew_pairings": []})
    result = solve_benders_with_branch_and_price(
        scenario,
        formal,
        load_passenger_capacity_profile(
            ROOT / "data/capacities/phase2_test_seat_capacity_v1.json"
        ),
        load_cost_config(ROOT / "data/costs/phase2_test_costs_v1.json"),
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
        load_branch_and_price_config(
            ROOT / "data/config/phase12_test_branch_and_price_v1.json"
        ),
        solver_factory=lambda: GurobiAdapter(output_flag=False),
    )
    assert len(full.aircraft_strings) == 77
    assert len(full.crew_pairings) == 374
    assert len(full.passenger_itineraries) == 55
    assert result.status is BendersBranchAndPriceStatus.OPTIMAL
    assert result.objective_value == pytest.approx(18080.0)
    assert result.lower_bound == pytest.approx(result.upper_bound)
    assert result.diagnostics["formal_full_enumerators_used"] is False
