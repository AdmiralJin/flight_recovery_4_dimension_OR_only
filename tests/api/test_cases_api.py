from fastapi.testclient import TestClient

from backend.main import app


client = TestClient(app)


def test_case_catalog_groups_and_loads_every_case():
    response = client.get("/api/cases")
    assert response.status_code == 200
    catalog = response.json()
    assert catalog["default_case_id"] == "benchmark-disruption-recovery"
    assert {item["category"] for item in catalog["cases"]} == {
        "核心示例",
        "可检验 Case",
        "边界 Case",
        "Scenario-only Case",
    }
    assert len(catalog["cases"]) == 8

    for metadata in catalog["cases"]:
        loaded = client.get(f"/api/cases/{metadata['case_id']}")
        assert loaded.status_code == 200
        payload = loaded.json()
        assert payload["case"] == metadata
        assert payload["scenario"]["scenario_id"]
        if metadata["mode"] == "solve_bundle":
            bundle = payload["solve_bundle"]
            assert bundle["scenario"] == payload["scenario"]
            assert bundle["recovery_columns"]["scenario_id"] == payload["scenario"]["scenario_id"]
            assert bundle["capacity_profile"]["scenario_id"] == payload["scenario"]["scenario_id"]
            assert bundle["recovery_columns"]["aircraft_strings"] == []
            assert bundle["recovery_columns"]["crew_pairings"] == []
        else:
            assert payload["solve_bundle"] is None


def test_case_variants_change_only_declared_capacity_or_cost_input():
    constrained = client.get("/api/cases/passenger-capacity-constrained").json()["solve_bundle"]
    relaxed = client.get("/api/cases/passenger-capacity-relaxed").json()["solve_bundle"]
    cost_variant = client.get("/api/cases/delay-cost-cancellation-tradeoff").json()["solve_bundle"]

    assert constrained["scenario"] == relaxed["scenario"] == cost_variant["scenario"]
    assert constrained["recovery_columns"] == relaxed["recovery_columns"] == cost_variant["recovery_columns"]
    assert constrained["cost_overrides"] == relaxed["cost_overrides"] == {}
    assert constrained["capacity_profile"]["seat_capacity_by_option_id"]["FO_T5_F1_ORIG"] == 0
    assert relaxed["capacity_profile"]["seat_capacity_by_option_id"]["FO_T5_F1_ORIG"] == 10
    assert cost_variant["capacity_profile"] == constrained["capacity_profile"]
    assert cost_variant["cost_overrides"] == {"flight_delay_per_minute": 3000.0}


def test_unknown_case_is_not_found():
    assert client.get("/api/cases/not-a-case").status_code == 404
