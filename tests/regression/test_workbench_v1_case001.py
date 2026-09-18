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


def test_workbench_v1_case001_baseline_exact_solve():
    bundle = _load_json("bundles", "wb_v1_001_baseline_bundle.json")
    expected = _load_json("expected", "wb_v1_001_baseline_expected.json")

    precheck = client.post("/api/solve/precheck", json=bundle)
    assert precheck.status_code == 200
    readiness = precheck.json()
    assert readiness["solve_ready"] is True
    assert readiness["missing_inputs"] == []
    assert readiness["invalid_profiles"] == []

    response = client.post("/api/solve", json=bundle)
    assert response.status_code == 200
    result = response.json()

    assert result["status"] == expected["expected_status"]
    assert result["scenario_id"] == expected["case_id"]

    objective = result["objective"]
    assert objective is not None
    for key, value in expected["expected_objective"].items():
        assert objective[key] == pytest.approx(value)

    strong = expected["strong_assertions"]
    assert set(result["selected"]["flight_options"]) == set(
        strong["selected_flight_options"]
    )
    assert len(result["resolved_flights"]) == len(bundle["scenario"]["flights"])

    assert sum(
        item["reassignment_count"] for item in result["aircraft_outcomes"]
    ) == strong["aircraft_reassignment_count_total"]
    assert sum(
        len(item["ferry_legs"]) for item in result["aircraft_outcomes"]
    ) == strong["aircraft_ferry_legs_total"]

    assert sum(
        item["reassignment_count"] for item in result["crew_outcomes"]
    ) == strong["crew_reassignment_count_total"]
    assert sum(
        len(item["deadhead_flights"]) for item in result["crew_outcomes"]
    ) == strong["crew_deadhead_legs_total"]

    assert len(result["passenger_outcomes"]) == strong["passenger_outcomes_count"]
    assert len(result["recovery_actions"]) == strong["recovery_actions_count"]
    assert result["diagnostics"]["integrated_audit_pass"] is strong[
        "integrated_audit_pass"
    ]
    assert result["diagnostics"]["formal_full_enumerators_used"] is False

    assert result["metrics"]["mean_departure_delay_minutes"] == pytest.approx(0.0)
    assert result["metrics"]["max_departure_delay_minutes"] == 0
