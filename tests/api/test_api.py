from fastapi.testclient import TestClient

from backend.main import app


client = TestClient(app)


def test_health_and_frontend_are_served():
    health = client.get("/api/health")
    page = client.get("/")
    table_script = client.get("/static/js/tables.js")

    assert health.status_code == 200
    assert health.json() == {
        "status": "ok",
        "solver_enabled": True,
        "solver_reason": None,
        "algorithm": "benders_branch_and_price_v1",
        "scope_mode": "full_only",
        "flight_option_generation": False,
        "production_ready": False,
    }
    assert page.status_code == 200
    if 'id="root"' in page.text:
        assert "AIR Recovery Workbench" in page.text
        assert 'src="/workbench-v2/assets/' in page.text
    else:
        assert "加载 Case" in page.text
        assert "当前 Case" in page.text
    assert page.headers["cache-control"] == "no-store, max-age=0"
    legacy = client.get("/legacy")
    assert legacy.status_code == 200
    assert "recovery-network-ui-20260920-1" in legacy.text
    assert table_script.status_code == 200
    assert table_script.headers["cache-control"] == "no-store, max-age=0"
    assert "机场容量" in table_script.text


def test_example_endpoint_is_stable(toy_case):
    response = client.get("/api/examples/toy_case_001")
    assert response.status_code == 200
    assert response.json() == toy_case


def test_validate_returns_normalized_data(toy_case):
    response = client.post("/api/validate", json=toy_case)
    payload = response.json()

    assert response.status_code == 200
    assert payload["valid"] is True
    assert payload["errors"] == []
    assert payload["normalized_data"] == toy_case


def test_validate_returns_actionable_location(toy_case):
    toy_case["flights"][0]["origin"] = "NO_SUCH_AIRPORT"
    response = client.post("/api/validate", json=toy_case)

    assert response.status_code == 422
    assert response.json()["valid"] is False
    assert {
        "location": "flights[0].origin",
        "code": "unknown_airport",
        "message": "airport 'NO_SUCH_AIRPORT' does not exist",
    } in response.json()["errors"]


def test_scenario_only_solve_is_rejected(toy_case):
    result = client.post("/api/solve/precheck", json={"scenario": toy_case})
    assert result.status_code == 200
    assert result.json()["solve_ready"] is False
    assert "missing_flight_options" in result.json()["missing_inputs"]
