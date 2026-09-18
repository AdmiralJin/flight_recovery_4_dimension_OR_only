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


def test_workbench_v1_case004_spare_aircraft_recovery_exact_solve():
    bundle = _load_json("bundles", "wb_v1_004_aircraft_swap_bundle.json")
    expected = _load_json("expected", "wb_v1_004_aircraft_swap_expected.json")

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

    resolved = {
        item["resolved"]["flight_id"]: item["resolved"]
        for item in result["resolved_flights"]
    }
    assert set(resolved) == set(strong["per_flight_aircraft"])
    for flight_id, aircraft_id in strong["per_flight_aircraft"].items():
        assert resolved[flight_id]["status"] == "operated"
        assert resolved[flight_id]["aircraft_id"] == aircraft_id
    for flight_id, delay in strong["per_flight_departure_delay_minutes"].items():
        assert resolved[flight_id]["departure_delay_minutes"] == delay

    cancelled = {
        flight_id
        for flight_id, item in resolved.items()
        if item["status"] == "cancelled"
    }
    assert cancelled == set(strong["cancelled_base_flights"])

    recovery_metrics = result["metrics"]["recovery"]
    assert recovery_metrics["delayed_flights"] == strong["delayed_flights"]
    assert recovery_metrics["cancelled_flights"] == strong["cancelled_flights"]
    assert recovery_metrics["total_flight_departure_delay_minutes"] == strong[
        "total_departure_delay_minutes"
    ]
    assert recovery_metrics["aircraft_reassignments"] == strong[
        "aircraft_reassignment_count_total"
    ]
    assert recovery_metrics["crew_reassignments"] == strong[
        "crew_reassignment_count_total"
    ]
    assert result["metrics"]["max_departure_delay_minutes"] == strong[
        "max_departure_delay_minutes"
    ]

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

    aircraft_outcomes = {
        item["aircraft_id"]: item for item in result["aircraft_outcomes"]
    }
    assert aircraft_outcomes["WB4_AC1"]["final_station"] == "A"
    assert aircraft_outcomes["WB4_AC2"]["final_station"] == "B"

    assert result["passenger_outcomes"] == []
    assert len(result["recovery_actions"]) == strong["recovery_actions_count"]
    assert result["diagnostics"]["integrated_audit_pass"] is strong[
        "integrated_audit_pass"
    ]
    assert result["diagnostics"]["formal_full_enumerators_used"] is False
