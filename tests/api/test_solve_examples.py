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


def test_validation_catalog_preserves_bundle_variants_and_metadata():
    response = client.get("/api/solve/examples")
    assert response.status_code == 200
    examples = {item["case_id"]: item for item in response.json()}

    low_cancel = examples["wb_v1_003_delay_vs_cancel_low_cancel"]
    assert low_cancel["type"] == "solve_bundle"
    assert low_cancel["solve_ready"] is True
    assert low_cancel["source"] == "workbench_validation"
    assert low_cancel["group"] == "validation"
    assert low_cancel["expected_status"] == "optimal"

    low_cancel_bundle = client.get(
        "/api/solve/example-bundle/wb_v1_003_delay_vs_cancel_low_cancel"
    )
    assert low_cancel_bundle.status_code == 200
    assert low_cancel_bundle.json()["cost_overrides"]["flight_cancellation"] == 20

    low_capacity_bundle = client.get(
        "/api/solve/example-bundle/wb_v1_006_passenger_connection_low_capacity"
    )
    assert low_capacity_bundle.status_code == 200
    capacity = low_capacity_bundle.json()["capacity_profile"]
    assert capacity["capacity_profile_id"] == "wb_v1_006_passenger_connection_low_f103_capacity"
    assert capacity["seat_capacity_by_option_id"]["WB6_F103_ORIG"] == 10


def test_validation_008g_is_input_ready_but_optimization_infeasible():
    response = client.get("/api/solve/examples")
    examples = {item["case_id"]: item for item in response.json()}
    boundary = examples["wb_v1_008g_valid_but_infeasible"]
    assert boundary["group"] == "boundary"
    assert boundary["expected_status"] == "infeasible"

    bundle_response = client.get(
        "/api/solve/example-bundle/wb_v1_008g_valid_but_infeasible"
    )
    assert bundle_response.status_code == 200
    bundle = bundle_response.json()

    readiness = client.post("/api/solve/precheck", json=bundle)
    assert readiness.status_code == 200
    assert readiness.json()["solve_ready"] is True

    solve_response = client.post("/api/solve", json=bundle)
    assert solve_response.status_code == 200
    assert solve_response.json()["status"] == "infeasible"
