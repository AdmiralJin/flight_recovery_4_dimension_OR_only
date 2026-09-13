from copy import deepcopy

from fastapi.testclient import TestClient

from backend.main import app


client = TestClient(app)


def test_cost_api_returns_canonical_profile_and_validates_override():
    baseline = client.get("/api/config/costs")
    assert baseline.status_code == 200
    profile = baseline.json()
    assert profile["cost_profile_id"] == "phase2_test_v1"

    response = client.post(
        "/api/config/costs/validate-overrides",
        json={
            "base_cost_profile_id": profile["cost_profile_id"],
            "overrides": {"flight_delay_per_minute": 9.25},
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["effective_profile"]["coefficients"]["flight_delay_per_minute"]["value"] == 9.25
    assert profile["coefficients"]["flight_delay_per_minute"]["value"] != 9.25
    for key in ("owner", "unit", "source", "source_reference"):
        assert payload["effective_profile"]["coefficients"]["flight_delay_per_minute"][key] == profile["coefficients"]["flight_delay_per_minute"][key]


def test_cost_api_rejects_unknown_and_invalid_override_values():
    base = {"base_cost_profile_id": "phase2_test_v1"}
    unknown = client.post(
        "/api/config/costs/validate-overrides",
        json={**base, "overrides": {"unknown": 1}},
    )
    negative = client.post(
        "/api/config/costs/validate-overrides",
        json={**base, "overrides": {"flight_delay_per_minute": -1}},
    )
    not_finite = client.post(
        "/api/config/costs/validate-overrides",
        json={**base, "overrides": {"flight_delay_per_minute": "Infinity"}},
    )

    assert unknown.status_code == 422
    assert negative.status_code == 422
    assert not_finite.status_code == 422


def test_constraint_api_returns_registry_and_read_only_test_capacity():
    response = client.get("/api/model/constraints")

    assert response.status_code == 200
    payload = response.json()
    assert payload["precheck_semantics"] == "DETERMINISTIC_PRECHECK_NOT_MIP_FEASIBILITY"
    assert len(payload["constraints"]) == 20
    assert {item["model"] for item in payload["constraints"]} == {"SRM", "ARM", "CRM", "PRM"}
    assert payload["capacity_profile_summary"]["display_label"] == "TEST / RESIDUAL CAPACITY"
    assert payload["capacity_profile_summary"]["not_physical_aircraft_capacity"] is True


def test_constraint_precheck_api_does_not_claim_solver_feasibility(toy_case):
    response = client.post(
        "/api/model/constraints/precheck",
        json={"scenario": deepcopy(toy_case)},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["precheck_semantics"] == "DETERMINISTIC_PRECHECK_NOT_MIP_FEASIBILITY"
    assert payload["overall_status"] == "warning"
    assert len(payload["results"]) == 20
