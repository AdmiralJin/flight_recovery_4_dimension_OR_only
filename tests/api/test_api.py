from fastapi.testclient import TestClient

from backend.main import app


client = TestClient(app)


def test_health_and_frontend_are_served():
    health = client.get("/api/health")
    page = client.get("/")
    table_script = client.get("/static/js/tables.js")

    assert health.status_code == 200
    assert health.json() == {"status": "ok", "phase": "2.5-workbench"}
    assert page.status_code == 200
    assert "Load Example" in page.text
    assert "Import Scenario" in page.text
    assert "Costs" in page.text
    assert "Constraints" in page.text
    assert table_script.status_code == 200
    assert "Airport Capacity" in table_script.text


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


def test_solve_guard_blocks_invalid_and_defers_valid_data(toy_case):
    toy_case["flights"][0]["origin"] = "NO_SUCH_AIRPORT"
    invalid = client.post("/api/solve", json=toy_case)
    assert invalid.status_code == 422
    assert "blocked" in invalid.json()["message"]

    toy_case["flights"][0]["origin"] = "A"
    valid = client.post("/api/solve", json=toy_case)
    assert valid.status_code == 501
    assert valid.json()["status"] == "not_implemented"
