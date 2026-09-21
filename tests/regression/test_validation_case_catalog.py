import pytest
from fastapi.testclient import TestClient

from backend.main import app


client = TestClient(app)


def test_validation_cases_match_scenario_readiness_and_optimization_oracles():
    catalog = client.get("/api/cases").json()
    for metadata in catalog["cases"]:
        payload = client.get(f"/api/cases/{metadata['case_id']}").json()
        expected = metadata["expected"]

        validation = client.post("/api/validate", json=payload["scenario"]).json()
        assert validation["valid"] is expected["scenario_valid"], metadata["case_id"]

        solve_input = payload["solve_bundle"] or {"scenario": payload["scenario"]}
        readiness = client.post("/api/solve/precheck", json=solve_input).json()
        assert readiness["solve_ready"] is expected["solve_ready"], metadata["case_id"]

        if not expected["solve_ready"]:
            continue
        result = client.post("/api/solve", json=payload["solve_bundle"])
        assert result.status_code == 200, metadata["case_id"]
        solved = result.json()
        assert solved["status"] == expected["optimization_status"], metadata["case_id"]
        if expected["objective_total"] is None:
            assert solved["objective"] is None
        else:
            assert solved["objective"]["total"] == pytest.approx(expected["objective_total"])

        selected_by_flight = {
            item["resolved"]["flight_id"]: item["resolved"]["selected_option_id"]
            for item in solved["resolved_flights"]
        }
        for flight_id, option_id in expected.get("required_flight_options", {}).items():
            assert selected_by_flight[flight_id] == option_id
        metrics = (solved.get("metrics") or {}).get("recovery", {})
        for key, value in expected.get("required_metrics", {}).items():
            assert metrics[key] == value
