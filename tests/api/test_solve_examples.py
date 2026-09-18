from fastapi.testclient import TestClient

from backend.main import app


client = TestClient(app)


def test_catalog_promotes_repository_fixture_case_to_solve_ready():
    response = client.get("/api/solve/examples")
    assert response.status_code == 200
    examples = {item["case_id"]: item for item in response.json()}

    toy003 = examples["toy_case_003"]
    assert toy003["type"] == "solve_bundle"
    assert toy003["solve_ready"] is True

    bundle_response = client.get("/api/solve/example-bundle/toy_case_003")
    assert bundle_response.status_code == 200
    bundle = bundle_response.json()
    readiness = client.post("/api/solve/precheck", json=bundle)
    assert readiness.status_code == 200
    assert readiness.json()["solve_ready"] is True


def test_raw_scenario_remains_scenario_only_for_solve_precheck():
    scenario_response = client.get("/api/examples/toy_case_003")
    assert scenario_response.status_code == 200
    scenario = scenario_response.json()

    readiness = client.post("/api/solve/precheck", json=scenario)
    assert readiness.status_code == 200
    payload = readiness.json()
    assert payload["solve_ready"] is False
    assert "missing_flight_options" in payload["missing_inputs"]
    assert "missing_capacity_profile" in payload["missing_inputs"]


def test_unmatched_scenario_is_not_solve_ready():
    scenario_response = client.get("/api/examples/toy_case_001")
    assert scenario_response.status_code == 200
    readiness = client.post("/api/solve/precheck", json=scenario_response.json())
    assert readiness.status_code == 200
    assert readiness.json()["solve_ready"] is False
