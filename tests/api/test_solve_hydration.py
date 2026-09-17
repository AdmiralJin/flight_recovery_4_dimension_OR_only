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


def test_imported_known_scenario_can_be_hydrated_without_replacing_scenario():
    scenario_response = client.get("/api/examples/toy_case_003")
    assert scenario_response.status_code == 200
    scenario = scenario_response.json()
    scenario["scenario_id"] = "toy_case_003"

    response = client.post("/api/solve/hydrate", json=scenario)
    assert response.status_code == 200
    bundle = response.json()
    assert bundle["scenario"] == scenario
    assert bundle["recovery_columns"]["flight_options"]
    assert bundle["capacity_profile"]["seat_capacity_by_option_id"]
    assert bundle["profile_ids"]
    assert client.post("/api/solve/precheck", json=bundle).json()["solve_ready"] is True


def test_unmatched_scenario_stays_scenario_only():
    scenario_response = client.get("/api/examples/toy_case_001")
    assert scenario_response.status_code == 200
    response = client.post("/api/solve/hydrate", json=scenario_response.json())
    assert response.status_code == 422
    assert response.json()["detail"]["status"] == "not_solve_ready"
