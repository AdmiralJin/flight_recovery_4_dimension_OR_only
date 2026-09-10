import json
from pathlib import Path

from backend.core.incidence import build_recovery_incidence
from backend.core.indices import build_recovery_indices
from backend.services.column_validator import validate_recovery_columns
from backend.services.validator import validate_scenario


PROJECT_ROOT = Path(__file__).parents[2]


def _load(*parts: str) -> dict:
    return json.loads(PROJECT_ROOT.joinpath(*parts).read_text(encoding="utf-8"))


def test_phase2_benchmark_001_incidence_facts():
    scenario, scenario_issues = validate_scenario(
        _load("data", "examples", "phase1_benchmark_001.json")
    )
    assert scenario is not None and scenario_issues == []
    columns, column_issues = validate_recovery_columns(
        scenario,
        _load("data", "columns", "phase1_benchmark_001_columns.json"),
    )
    assert columns is not None and column_issues == []

    indices = build_recovery_indices(scenario, columns)
    incidence = build_recovery_incidence(scenario, columns, indices)

    assert incidence.base_flight_to_options.columns_for_row("F2") == tuple(
        option.option_id
        for option in columns.flight_options
        if option.base_flight_id == "F2"
    )
    assert all(
        "FO_FERRY_CA_1140"
        not in incidence.base_flight_to_options.columns_for_row(flight_id)
        for flight_id in indices.flights.ids
    )

    assert incidence.option_to_aircraft_strings.rows_for_column(
        "AS_AC1_SWAP_F10"
    ) == ("FO_F1_ORIG", "FO_F2_D50", "FO_F10_D20")
    assert set(
        incidence.option_to_aircraft_strings.rows_for_column(
            "AS_AC4_SWAP_F3_ORIG"
        )
    ) == {"FO_F3_ORIG", "FO_F11_D10", "FO_F12_ORIG"}

    assert incidence.option_to_operating_pairings.rows_for_column(
        "CP_C1_RECOVERY"
    ) == ("FO_F1_ORIG", "FO_F2_D50", "FO_F10_D20")
    assert incidence.option_to_operating_pairings.rows_for_column(
        "CP_C4_F3_ORIG_F11_D10"
    ) == ("FO_F3_ORIG", "FO_F11_D10")
    assert all(
        incidence.option_to_deadhead_pairings.columns_for_row(option_id) == ()
        for option_id in indices.flight_options.ids
    )

    assert incidence.option_to_passenger_itineraries.rows_for_column(
        "PI_P4_REACCOM_F8"
    ) == ("FO_F8_ORIG",)

    b_interval = next(
        key for key in indices.capacity_intervals.ids if key.airport == "B"
    )
    assert incidence.departure_capacity_to_options.contains(
        b_interval, "FO_F5_ORIG"
    )
    assert incidence.departure_capacity_to_options.contains(
        b_interval, "FO_F8_ORIG"
    )
    assert not incidence.departure_capacity_to_options.contains(
        b_interval, "FO_F2_D50"
    )

    assert indices.maintenance_aircraft.ids == ("AC4",)
    assert incidence.maintenance_to_strings.contains(
        "AC4", "AS_AC4_SWAP_F3_ORIG"
    )
