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
)
from backend.core import (
    BendersBranchAndPriceError,
    RecoveryScope,
    solve_benders_with_branch_and_price,
)
from backend.solver import GurobiAdapter


ROOT = Path(__file__).parents[2]


def test_integrated_phase12_rejects_dynamic_scope(
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
    with pytest.raises(BendersBranchAndPriceError, match="UNSUPPORTED_DYNAMIC_SCOPE"):
        solve_benders_with_branch_and_price(
            toy_case_013_benders_column_generation_data,
            toy_case_013_benders_column_generation_columns_data,
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
            load_branch_and_price_config(
                ROOT / "data/config/phase12_test_branch_and_price_v1.json"
            ),
            solver_factory=lambda: GurobiAdapter(output_flag=False),
            scope=scope,
        )
