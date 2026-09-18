import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.main import app


client = TestClient(app)
ROOT = Path(__file__).parents[2]
CASE_ROOT = ROOT / "data" / "workbench_validation"


def _load_json(*parts: str) -> dict:
    return json.loads(CASE_ROOT.joinpath(*parts).read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("subcase", "filename"),
    [
        ("008A", "wb_v1_008a_duplicate_flight_id.json"),
        ("008B", "wb_v1_008b_invalid_flight_time.json"),
        ("008C", "wb_v1_008c_invalid_duration.json"),
        ("008D", "wb_v1_008d_invalid_market_min_seats.json"),
        ("008E", "wb_v1_008e_invalid_disruption_interval.json"),
    ],
)
def test_workbench_v1_case008_invalid_scenarios_are_rejected(
    subcase: str,
    filename: str,
):
    expected = _load_json(
        "expected", "wb_v1_008_negative_cases_expected.json"
    )["subcases"][subcase]
    scenario = _load_json("negative", filename)

    response = client.post("/api/validate", json=scenario)
    assert response.status_code == expected["expected_http_status"]
    payload = response.json()
    assert payload["valid"] is expected["expected_valid"]
    assert payload["errors"]

    if "expected_error_code" in expected:
        assert expected["expected_error_code"] in {
            item["code"] for item in payload["errors"]
        }
    if "expected_message_contains" in expected:
        assert any(
            expected["expected_message_contains"] in item["message"]
            for item in payload["errors"]
        )


def test_workbench_v1_case008f_valid_scenario_is_not_solve_ready_without_bundle():
    expected = _load_json(
        "expected", "wb_v1_008_negative_cases_expected.json"
    )["subcases"]["008F"]
    scenario = _load_json(
        "negative", "wb_v1_008f_scenario_only_missing_solve_inputs.json"
    )

    validation = client.post("/api/validate", json=scenario)
    assert validation.status_code == expected["validate_expected_http_status"]
    assert validation.json()["valid"] is expected["validate_expected_valid"]

    incomplete_request = {
        "schema_version": "1.0.0",
        "scenario": scenario,
        "cost_profile_id": "phase2_test_v1",
        "cost_overrides": {},
        "algorithm": "benders_branch_and_price_v1",
    }
    precheck = client.post("/api/solve/precheck", json=incomplete_request)
    assert precheck.status_code == 200
    readiness = precheck.json()
    assert readiness["solve_ready"] is expected["precheck_expected_solve_ready"]
    assert set(readiness["missing_inputs"]) == set(
        expected["expected_missing_inputs"]
    )
    assert readiness["semantics"] == "INPUT_READINESS_NOT_OPTIMIZATION_FEASIBILITY"

    solve = client.post("/api/solve", json=incomplete_request)
    assert solve.status_code == expected["solve_expected_http_status"]
    detail = solve.json()["detail"]
    assert detail["status"] == expected["solve_expected_status"]
    assert set(expected["expected_missing_inputs"]).issubset(set(detail["codes"]))


def test_workbench_v1_case008g_precheck_ready_but_optimization_infeasible():
    expected = _load_json(
        "expected", "wb_v1_008_negative_cases_expected.json"
    )["subcases"]["008G"]
    bundle = _load_json(
        "bundles", "wb_v1_008g_valid_but_infeasible_bundle.json"
    )

    validation = client.post("/api/validate", json=bundle["scenario"])
    assert validation.status_code == expected["validate_expected_http_status"]
    assert validation.json()["valid"] is expected["validate_expected_valid"]

    precheck = client.post("/api/solve/precheck", json=bundle)
    assert precheck.status_code == 200
    readiness = precheck.json()
    assert readiness["solve_ready"] is expected["precheck_expected_solve_ready"]
    assert readiness["missing_inputs"] == []
    assert readiness["invalid_profiles"] == []
    assert readiness["semantics"] == "INPUT_READINESS_NOT_OPTIMIZATION_FEASIBILITY"

    response = client.post("/api/solve", json=bundle)
    assert response.status_code == expected["solve_expected_http_status"]
    result = response.json()
    assert result["status"] == expected["expected_status"]
    assert result["objective"] is expected["expected_objective"]

    assert result["selected"]["flight_options"] == []
    assert result["selected"]["aircraft_strings"] == []
    assert result["selected"]["crew_pairings"] == []
    assert result["selected"]["passenger_itineraries"] == []

    assert result["resolved_flights"] == []
    assert result["aircraft_outcomes"] == []
    assert result["crew_outcomes"] == []
    assert result["passenger_outcomes"] == []
    assert result["recovery_actions"] == []
    assert result["metrics"] is None

    assert result["diagnostics"]["integrated_audit_pass"] is None
    assert result["diagnostics"]["formal_full_enumerators_used"] is False
    assert result["diagnostics"]["terminal_reason"]
