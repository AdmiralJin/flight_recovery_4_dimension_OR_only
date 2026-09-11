import copy
from pathlib import Path

import pytest

from backend.config import (
    FixedColumnCostConfig,
    crew_pairing_cost,
    load_cost_config,
)
from backend.core import (
    CrmBuildError,
    CrewRecoveryRequest,
    build_crew_recovery_incidence,
    build_fixed_column_crm,
    recompute_crm_diagnostics,
    solve_fixed_column_crm,
)
from backend.schemas.columns import RecoveryColumns
from backend.schemas.scenario import Scenario
from backend.solver import GurobiAdapter, SolverStatus


@pytest.fixture
def adapter():
    available, reason = GurobiAdapter.availability()
    if not available:
        pytest.skip(reason or "Gurobi is unavailable")
    with GurobiAdapter(output_flag=False) as instance:
        yield instance


@pytest.fixture
def costs():
    return load_cost_config(
        Path(__file__).parents[2] / "data" / "costs" / "phase2_test_costs_v1.json"
    )


def _pairing(pairing_id, crew_id, segment_type, option_id):
    return {
        "pairing_id": pairing_id,
        "crew_id": crew_id,
        "duties": [
            {
                "duty_id": f"D_{pairing_id}",
                "segments": [
                    {
                        "segment_type": segment_type,
                        "flight_option_id": option_id,
                        "origin": None,
                        "destination": None,
                        "start_time": None,
                        "end_time": None,
                        "notes": "",
                    }
                ],
            }
        ],
        "start_station": "A",
        "end_station": "B",
        "cost_components": {},
        "notes": "",
    }


def _crm_case(crew_ids=("C1",), pairings=None):
    scenario = {
        "scenario_id": "crm_unit_case",
        "recovery_window": {
            "start_time": "2026-01-15T08:00:00Z",
            "end_time": "2026-01-15T12:00:00Z",
        },
        "airports": [
            {"airport_id": "A", "name": "Alpha"},
            {"airport_id": "B", "name": "Bravo"},
        ],
        "flights": [
            {
                "flight_id": "F1",
                "origin": "A",
                "destination": "B",
                "sched_dep": "2026-01-15T09:00:00Z",
                "sched_arr": "2026-01-15T10:00:00Z",
                "duration": 60,
                "original_aircraft": "AC1",
                "original_equipment": "E1",
                "original_crew": "C1",
                "strategic_flag": False,
                "market_flag": False,
                "min_seats": 0,
                "max_delay": 60,
            }
        ],
        "aircraft": [
            {
                "tail_id": "AC1",
                "equipment_type": "E1",
                "initial_station_at_t": "A",
                "required_station_at_T_end": "B",
                "maintenance_required": False,
                "maintenance_stations": ["B"],
                "original_rotation": ["F1"],
            }
        ],
        "crew": [
            {
                "crew_id": crew_id,
                "rating": "E1",
                "start_station_at_t": "A",
                "required_station_at_T_end": "B",
                "original_duties": [["F1"]] if crew_id == "C1" else [],
                "original_pairing": ["F1"] if crew_id == "C1" else [],
            }
            for crew_id in crew_ids
        ],
        "passengers": [],
        "airport_intervals": [
            {
                "airport": airport,
                "start_time": "2026-01-15T08:00:00Z",
                "end_time": "2026-01-15T12:00:00Z",
                "arr_capacity": 10,
                "dep_capacity": 10,
                "gate_capacity": 10,
                "curfew_flag": False,
                "weather_restrictions": [],
            }
            for airport in ("A", "B")
        ],
        "disruptions": [],
    }
    columns = {
        "schema_version": "1.0.0",
        "scenario_id": scenario["scenario_id"],
        "time_unit": "minute",
        "notes": [],
        "flight_options": [
            {
                "option_id": "FO_F1_ORIG",
                "base_flight_id": "F1",
                "operation_type": "operate",
                "change_types": ["unchanged"],
                "origin": "A",
                "destination": "B",
                "dep_time": "2026-01-15T09:00:00Z",
                "arr_time": "2026-01-15T10:00:00Z",
                "block_minutes": 60,
                "departure_delay_minutes": 0,
                "arrival_delay_minutes": 0,
                "notes": "",
            },
            {
                "option_id": "FO_F1_D30",
                "base_flight_id": "F1",
                "operation_type": "operate",
                "change_types": ["delay"],
                "origin": "A",
                "destination": "B",
                "dep_time": "2026-01-15T09:30:00Z",
                "arr_time": "2026-01-15T10:30:00Z",
                "block_minutes": 60,
                "departure_delay_minutes": 30,
                "arrival_delay_minutes": 30,
                "notes": "",
            },
            {
                "option_id": "FO_F1_CANCEL",
                "base_flight_id": "F1",
                "operation_type": "cancel",
                "change_types": ["cancel"],
                "origin": None,
                "destination": None,
                "dep_time": None,
                "arr_time": None,
                "block_minutes": None,
                "departure_delay_minutes": None,
                "arrival_delay_minutes": None,
                "notes": "",
            },
            {
                "option_id": "FO_FERRY_AB",
                "base_flight_id": None,
                "operation_type": "ferry",
                "change_types": ["positioning"],
                "origin": "A",
                "destination": "B",
                "dep_time": "2026-01-15T11:00:00Z",
                "arr_time": "2026-01-15T12:00:00Z",
                "block_minutes": 60,
                "departure_delay_minutes": None,
                "arrival_delay_minutes": None,
                "notes": "",
            },
        ],
        "aircraft_strings": [],
        "crew_pairings": (
            pairings
            if pairings is not None
            else [_pairing("CP_C1_OPERATE", "C1", "operate", "FO_F1_ORIG")]
        ),
        "passenger_itineraries": [],
    }
    return scenario, columns


def _request(option_ids=("FO_F1_ORIG",)):
    return CrewRecoveryRequest("crm_unit_case", option_ids)


def _solve(adapter, costs, scenario, columns, option_ids=("FO_F1_ORIG",)):
    return solve_fixed_column_crm(
        scenario,
        columns,
        _request(option_ids),
        costs,
        adapter,
        solver_parameters={"DualReductions": 0},
    )


def _costs(costs, *, reassignment=0, deadhead=0):
    data = costs.model_dump(mode="json")
    data["coefficients"]["crew_reassignment"]["value"] = reassignment
    data["coefficients"]["deadhead_per_minute"]["value"] = deadhead
    return FixedColumnCostConfig.model_validate(data)


def test_crm_c01_selects_exactly_one_of_two_pairings(adapter, costs):
    pairings = [
        _pairing("CP_ONE", "C1", "operate", "FO_F1_ORIG"),
        _pairing("CP_TWO", "C1", "operate", "FO_F1_ORIG"),
    ]
    scenario, columns = _crm_case(pairings=pairings)

    result = _solve(adapter, costs, scenario, columns)

    assert result.status is SolverStatus.OPTIMAL
    assert len(result.selected_variables) == 1
    assert result.diagnostics["pairing_selection_constraints"][0]["lhs"] == 1
    assert result.diagnostics["covered_required_options"] == ["FO_F1_ORIG"]


def test_crm_deadhead_does_not_satisfy_operating_coverage(adapter, costs):
    scenario, columns = _crm_case(
        pairings=[_pairing("CP_DH", "C1", "deadhead", "FO_F1_ORIG")]
    )

    result = _solve(adapter, costs, scenario, columns)

    assert result.status is SolverStatus.INFEASIBLE
    assert result.diagnostics["fixed_column_analysis"][
        "required_options_without_eligible_operating_pairing"
    ] == ["FO_F1_ORIG"]


def test_crm_duplicate_operating_coverage_is_infeasible(adapter, costs):
    scenario, columns = _crm_case(
        crew_ids=("C1", "C2"),
        pairings=[
            _pairing("CP_C1_OP", "C1", "operate", "FO_F1_ORIG"),
            _pairing("CP_C2_OP", "C2", "operate", "FO_F1_ORIG"),
        ],
    )

    result = _solve(adapter, costs, scenario, columns)

    assert result.status is SolverStatus.INFEASIBLE


def test_crm_nonrequired_operating_alternate_is_prohibited(adapter, costs):
    scenario, columns = _crm_case(
        pairings=[
            _pairing("CP_ORIG", "C1", "operate", "FO_F1_ORIG"),
            _pairing("CP_DELAY", "C1", "operate", "FO_F1_D30"),
        ]
    )

    result = _solve(adapter, costs, scenario, columns)

    assert result.status is SolverStatus.OPTIMAL
    assert result.diagnostics["selected_pairing_by_crew"] == {"C1": "CP_ORIG"}
    assert result.diagnostics["unexpected_operating_options"] == []


def test_crm_deadhead_on_unselected_option_is_prohibited(adapter, costs):
    scenario, columns = _crm_case(
        crew_ids=("C1", "C2"),
        pairings=[
            _pairing("CP_C1_OP", "C1", "operate", "FO_F1_ORIG"),
            _pairing("CP_C2_DH_ORIG", "C2", "deadhead", "FO_F1_ORIG"),
            _pairing("CP_C2_DH_DELAY", "C2", "deadhead", "FO_F1_D30"),
        ],
    )

    result = _solve(adapter, costs, scenario, columns)

    assert result.status is SolverStatus.OPTIMAL
    assert result.diagnostics["selected_pairing_by_crew"]["C2"] == "CP_C2_DH_ORIG"
    assert result.diagnostics["unexpected_deadhead_options"] == []
    assert [item["option_id"] for item in result.diagnostics["deadhead_legs"]] == [
        "FO_F1_ORIG"
    ]


def test_crm_reassignment_and_deadhead_costs_are_nonzero_and_audited(adapter, costs):
    scenario, columns = _crm_case(
        crew_ids=("C1", "C2"),
        pairings=[
            _pairing("CP_C1_DH", "C1", "deadhead", "FO_F1_ORIG"),
            _pairing("CP_C2_OP", "C2", "operate", "FO_F1_ORIG"),
        ],
    )
    nonzero_costs = _costs(costs, reassignment=100, deadhead=2)

    result = _solve(adapter, nonzero_costs, scenario, columns)

    assert result.status is SolverStatus.OPTIMAL
    assert result.diagnostics["crew_reassignment_count"] == 1
    assert result.diagnostics["deadhead_minutes"] == 60
    assert result.diagnostics["objective_breakdown"] == {
        "crew_reassignment": 100.0,
        "deadhead": 120.0,
        "total": 220.0,
    }
    assert result.objective_value == pytest.approx(220.0)

    parsed_scenario = Scenario.model_validate(scenario)
    parsed_columns = RecoveryColumns.model_validate(columns)
    breakdown = crew_pairing_cost(
        parsed_scenario,
        {item.option_id: item for item in parsed_columns.flight_options},
        parsed_columns.crew_pairings[1],
        nonzero_costs,
    )
    assert breakdown.crew_reassignment_count == 1
    assert breakdown.total == pytest.approx(100.0)


@pytest.mark.parametrize(
    ("option_ids", "message"),
    [
        (("UNKNOWN",), "unknown required operated option"),
        (("FO_F1_CANCEL",), "not a revenue operate option"),
        (("FO_FERRY_AB",), "not a revenue operate option"),
        (("FO_F1_ORIG", "FO_F1_D30"), "conflicting schedule options"),
    ],
)
def test_crm_rejects_unknown_or_non_operated_request(
    adapter, costs, option_ids, message
):
    scenario, columns = _crm_case()
    with pytest.raises(CrmBuildError, match=message):
        _solve(adapter, costs, scenario, columns, option_ids=option_ids)


def test_crm_request_rejects_duplicate_ids():
    with pytest.raises(ValueError, match="must be unique"):
        CrewRecoveryRequest("crm_unit_case", ("FO_F1_ORIG", "FO_F1_ORIG"))


@pytest.mark.parametrize(
    ("mutation", "error_code"),
    [
        ("duplicate_pairing", "duplicate_id"),
        ("unknown_crew", "unknown_crew"),
        ("unknown_leg", "unknown_flight_option"),
        ("cancel_leg", "cancel_option_in_crew_pairing"),
        ("illegal_terminal", "end_station_mismatch"),
    ],
)
def test_crm_entry_point_reuses_pairing_semantic_validation(
    adapter, costs, mutation, error_code
):
    scenario, columns = _crm_case()
    if mutation == "duplicate_pairing":
        columns["crew_pairings"].append(copy.deepcopy(columns["crew_pairings"][0]))
    elif mutation == "unknown_crew":
        columns["crew_pairings"][0]["crew_id"] = "UNKNOWN"
    elif mutation == "unknown_leg":
        columns["crew_pairings"][0]["duties"][0]["segments"][0][
            "flight_option_id"
        ] = "UNKNOWN"
    elif mutation == "cancel_leg":
        columns["crew_pairings"][0]["duties"][0]["segments"][0][
            "flight_option_id"
        ] = "FO_F1_CANCEL"
    else:
        columns["crew_pairings"][0]["end_station"] = "A"

    with pytest.raises(CrmBuildError, match=error_code):
        _solve(adapter, costs, scenario, columns)


def test_crm_rejects_crew_without_explicit_pairing(adapter, costs):
    scenario, columns = _crm_case(pairings=[])

    with pytest.raises(CrmBuildError, match="has no explicit candidate pairing"):
        _solve(adapter, costs, scenario, columns)


def test_crm_rejects_ferry_as_pairing_flight_transport(adapter, costs):
    scenario, columns = _crm_case(
        pairings=[_pairing("CP_FERRY", "C1", "deadhead", "FO_FERRY_AB")]
    )

    with pytest.raises(CrmBuildError, match="must reference a revenue operate option"):
        _solve(adapter, costs, scenario, columns)


def test_crew_incidence_is_deterministic_and_immutable():
    pairings = [
        _pairing("CP_OP", "C1", "operate", "FO_F1_ORIG"),
        _pairing("CP_DH", "C1", "deadhead", "FO_F1_D30"),
    ]
    scenario_data, columns_data = _crm_case(pairings=pairings)
    scenario = Scenario.model_validate(scenario_data)
    columns = RecoveryColumns.model_validate(columns_data)

    incidence = build_crew_recovery_incidence(scenario, columns)

    assert incidence.crew_to_pairings.columns_for_row("C1") == (
        "CP_OP",
        "CP_DH",
    )
    assert incidence.pairing_to_operated_options["CP_OP"] == ("FO_F1_ORIG",)
    assert incidence.pairing_to_deadhead_options["CP_DH"] == ("FO_F1_D30",)
    with pytest.raises(TypeError):
        incidence.pairing_to_operated_options["CP_OP"] = ()


def test_crm_audit_rejects_unknown_pairing_id(adapter, costs):
    scenario_data, columns_data = _crm_case()
    scenario = Scenario.model_validate(scenario_data)
    columns = RecoveryColumns.model_validate(columns_data)
    model = build_fixed_column_crm(scenario, columns, _request(), costs, adapter)

    with pytest.raises(CrmBuildError, match=r"unknown=\['UNKNOWN'\]"):
        recompute_crm_diagnostics(model, {"UNKNOWN": 1.0}, costs)
