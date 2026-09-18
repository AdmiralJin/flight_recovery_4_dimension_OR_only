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


@pytest.mark.parametrize(
    ("variant_name", "bundle_name"),
    [
        ("default_costs", "wb_v1_003_delay_vs_cancel_bundle.json"),
        ("low_cancellation_cost", "wb_v1_003_delay_vs_cancel_low_cancel_bundle.json"),
    ],
)
def test_workbench_v1_case003_cost_override_flips_recovery(
    variant_name: str,
    bundle_name: str,
):
    bundle = _load_json("bundles", bundle_name)
    expected = _load_json("expected", "wb_v1_003_delay_vs_cancel_expected.json")
    variant = expected["variants"][variant_name]

    assert bundle["cost_overrides"] == variant["cost_overrides"]

    precheck = client.post("/api/solve/precheck", json=bundle)
    assert precheck.status_code == 200
    readiness = precheck.json()
    assert readiness["solve_ready"] is True
    assert readiness["missing_inputs"] == []
    assert readiness["invalid_profiles"] == []

    response = client.post("/api/solve", json=bundle)
    assert response.status_code == 200
    result = response.json()

    assert result["status"] == variant["expected_status"]
    assert result["scenario_id"] == expected["case_id"]

    objective = result["objective"]
    assert objective is not None
    for key, value in variant["expected_objective"].items():
        assert objective[key] == pytest.approx(value)

    strong = variant["strong_assertions"]
    assert set(result["selected"]["flight_options"]) == set(
        strong["selected_flight_options"]
    )

    resolved = {
        item["resolved"]["flight_id"]: item["resolved"]
        for item in result["resolved_flights"]
    }
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
    assert result["metrics"]["max_departure_delay_minutes"] == strong[
        "max_departure_delay_minutes"
    ]

    assert sum(
        item["reassignment_count"] for item in result["aircraft_outcomes"]
    ) == 0
    assert sum(
        len(item["ferry_legs"]) for item in result["aircraft_outcomes"]
    ) == 0
    assert sum(
        item["reassignment_count"] for item in result["crew_outcomes"]
    ) == 0
    assert sum(
        len(item["deadhead_flights"]) for item in result["crew_outcomes"]
    ) == 0
    assert result["passenger_outcomes"] == []

    assert len(result["recovery_actions"]) == strong["recovery_actions_count"]
    assert result["diagnostics"]["integrated_audit_pass"] is strong[
        "integrated_audit_pass"
    ]
    assert result["diagnostics"]["formal_full_enumerators_used"] is False


def test_workbench_v1_case003_bundles_differ_only_by_cost_override():
    default = _load_json("bundles", "wb_v1_003_delay_vs_cancel_bundle.json")
    low_cancel = _load_json(
        "bundles", "wb_v1_003_delay_vs_cancel_low_cancel_bundle.json"
    )

    default_without_override = dict(default)
    low_cancel_without_override = dict(low_cancel)
    default_without_override.pop("cost_overrides")
    low_cancel_without_override.pop("cost_overrides")

    assert default_without_override == low_cancel_without_override
    assert default["cost_overrides"] == {}
    assert low_cancel["cost_overrides"] == {"flight_cancellation": 20.0}
