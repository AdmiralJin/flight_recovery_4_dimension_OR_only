from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from backend.main import app


client = TestClient(app)


def bundle(case_id: str) -> dict:
    response = client.get(f"/api/solve/example-bundle/{case_id}")
    assert response.status_code == 200
    return response.json()


@pytest.mark.parametrize(
    ("case_id", "objective"),
    [
        ("phase1_benchmark_001", 18080.0),
        ("toy_case_016_benders_branch_and_price", 95200.0),
    ],
)
def test_exact_solve_api(case_id, objective):
    data = bundle(case_id)
    assert data["recovery_columns"]["aircraft_strings"] == []
    assert data["recovery_columns"]["crew_pairings"] == []
    assert client.post("/api/solve/precheck", json=data).json()["solve_ready"]
    response = client.post("/api/solve", json=data)
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "optimal"
    assert result["objective"]["total"] == pytest.approx(objective)
    assert result["objective"]["total"] == pytest.approx(
        sum(
            result["objective"][key]
            for key in ("schedule", "aircraft", "crew", "passenger")
        )
    )
    assert result["diagnostics"]["integrated_audit_pass"] is True
    assert result["diagnostics"]["formal_full_enumerators_used"] is False
    assert len(result["resolved_flights"]) == len(data["scenario"]["flights"])
    assert len(result["aircraft_outcomes"]) == len(data["scenario"]["aircraft"])
    assert len(result["crew_outcomes"]) == len(data["scenario"]["crew"])
    assert len(result["passenger_outcomes"]) == len(data["scenario"]["passengers"])


def test_invalid_and_scenario_only_bundle():
    data = bundle("phase1_benchmark_001")
    raw_scenario = client.post("/api/solve", json=data["scenario"])
    assert raw_scenario.status_code == 422
    assert "missing_flight_options" in raw_scenario.json()["detail"]["codes"]
    data["recovery_columns"] = None
    precheck = client.post("/api/solve/precheck", json=data)
    assert precheck.status_code == 200
    assert "missing_flight_options" in precheck.json()["missing_inputs"]
    response = client.post("/api/solve", json=data)
    assert response.status_code == 422
    assert "missing_flight_options" in response.json()["detail"]["codes"]
    data["scenario"]["flights"][0]["origin"] = "NO_SUCH_AIRPORT"
    response = client.post("/api/solve", json=data)
    assert response.status_code == 422


def test_unknown_cost_override_is_an_input_error():
    data = bundle("phase1_benchmark_001")
    data["cost_overrides"] = {"not_a_cost_term": 1.0}
    precheck = client.post("/api/solve/precheck", json=data)
    assert precheck.status_code == 200
    assert "cost_overrides" in precheck.json()["invalid_profiles"]
    response = client.post("/api/solve", json=data)
    assert response.status_code == 422
    assert "cost_overrides" in response.json()["detail"]["codes"]


def test_missing_explicit_passenger_itineraries_is_not_solve_ready():
    data = bundle("phase1_benchmark_001")
    data["recovery_columns"]["passenger_itineraries"] = []
    response = client.post("/api/solve", json=data)
    assert response.status_code == 422
    assert "missing_passenger_itineraries" in response.json()["detail"]["codes"]


def test_valid_but_infeasible_bundle_returns_http_200():
    data = bundle("toy_case_016_benders_branch_and_price")
    keep = {
        "T16_O1",
        "T16_F2_ORIG",
        "T16_F3_ORIG",
        "T16_D1_ORIG",
        "T16_D2_ORIG",
        "T16_D3_ORIG",
    }
    data["recovery_columns"]["flight_options"] = [
        item
        for item in data["recovery_columns"]["flight_options"]
        if item["option_id"] in keep
    ]
    data["capacity_profile"]["seat_capacity_by_option_id"] = {
        key: value
        for key, value in data["capacity_profile"]["seat_capacity_by_option_id"].items()
        if key in keep
    }
    response = client.post("/api/solve", json=data)
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "infeasible"
    assert result["objective"] is None
    assert result["resolved_flights"] == []


def test_branch_node_limit_returns_not_converged():
    data = bundle("toy_case_016_benders_branch_and_price")
    data["profile_ids"]["branch_and_price"] = "phase13-limited-branch-and-price-v1"
    response = client.post("/api/solve", json=data)
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "not_converged"
    assert result["resolved_flights"] == []
    assert result["objective"] is None


def test_repeated_request_is_structurally_deterministic():
    data = bundle("toy_case_016_benders_branch_and_price")
    first = client.post("/api/solve", json=data).json()
    second = client.post("/api/solve", json=data).json()
    for key in (
        "objective",
        "selected",
        "resolved_flights",
        "aircraft_outcomes",
        "crew_outcomes",
        "passenger_outcomes",
        "recovery_actions",
        "metrics",
    ):
        assert first[key] == second[key]
