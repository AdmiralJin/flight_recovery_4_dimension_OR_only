import json
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.main import app


client = TestClient(app)
ROOT = Path(__file__).parents[2]
CASE_ROOT = ROOT / "data" / "workbench_validation"


def _load_json(*parts: str) -> dict:
    return json.loads(CASE_ROOT.joinpath(*parts).read_text(encoding="utf-8"))


def _selected_departure_count(
    bundle: dict,
    selected_option_ids: list[str],
    *,
    airport: str,
    start: str,
    end: str,
) -> int:
    start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
    end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
    options = {
        item["option_id"]: item
        for item in bundle["recovery_columns"]["flight_options"]
    }
    count = 0
    for option_id in selected_option_ids:
        option = options[option_id]
        if option["operation_type"] != "operate" or option["origin"] != airport:
            continue
        dep = datetime.fromisoformat(option["dep_time"].replace("Z", "+00:00"))
        if start_dt <= dep < end_dt:
            count += 1
    return count


@pytest.mark.parametrize(
    ("variant_name", "bundle_name"),
    [
        ("baseline_capacity", "wb_v1_007_capacity_baseline_bundle.json"),
        ("bottleneck_capacity", "wb_v1_007_capacity_bottleneck_bundle.json"),
    ],
)
def test_workbench_v1_case007_airport_capacity_exact_solve(
    variant_name: str,
    bundle_name: str,
):
    bundle = _load_json("bundles", bundle_name)
    expected = _load_json(
        "expected", "wb_v1_007_capacity_bottleneck_expected.json"
    )
    variant = expected["variants"][variant_name]

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
    selected = result["selected"]["flight_options"]
    assert set(selected) == set(strong["selected_flight_options"])

    resolved = {
        item["resolved"]["flight_id"]: item["resolved"]
        for item in result["resolved_flights"]
    }
    assert set(resolved) == set(strong["per_flight_departure_delay_minutes"])
    for flight_id, delay in strong["per_flight_departure_delay_minutes"].items():
        assert resolved[flight_id]["status"] == "operated"
        assert resolved[flight_id]["departure_delay_minutes"] == delay

    constrained_load = _selected_departure_count(
        bundle,
        selected,
        airport="B",
        start="2026-01-15T09:00:00Z",
        end="2026-01-15T10:00:00Z",
    )
    next_load = _selected_departure_count(
        bundle,
        selected,
        airport="B",
        start="2026-01-15T10:00:00Z",
        end="2026-01-15T12:30:00Z",
    )
    assert constrained_load == strong[
        "constrained_interval_selected_departure_count"
    ]
    assert constrained_load <= strong["constrained_interval_departure_capacity"]
    assert next_load == strong["next_interval_selected_departure_count"]

    recovery_metrics = result["metrics"]["recovery"]
    assert recovery_metrics["delayed_flights"] == strong["delayed_flights"]
    assert recovery_metrics["total_flight_departure_delay_minutes"] == strong[
        "total_departure_delay_minutes"
    ]
    assert recovery_metrics["aircraft_reassignments"] == strong[
        "aircraft_reassignment_count_total"
    ]
    assert recovery_metrics["crew_reassignments"] == strong[
        "crew_reassignment_count_total"
    ]
    assert recovery_metrics["cancelled_flights"] == 0
    assert recovery_metrics["unserved_passengers"] == 0

    assert result["passenger_outcomes"] == []
    assert len(result["recovery_actions"]) == strong["recovery_actions_count"]
    assert result["diagnostics"]["integrated_audit_pass"] is strong[
        "integrated_audit_pass"
    ]
    assert result["diagnostics"]["formal_full_enumerators_used"] is False


def test_workbench_v1_case007_variants_isolate_airport_capacity_change():
    baseline = _load_json(
        "bundles", "wb_v1_007_capacity_baseline_bundle.json"
    )
    bottleneck = _load_json(
        "bundles", "wb_v1_007_capacity_bottleneck_bundle.json"
    )

    assert baseline["recovery_columns"] == bottleneck["recovery_columns"]
    assert baseline["capacity_profile"] == bottleneck["capacity_profile"]
    assert baseline["cost_profile_id"] == bottleneck["cost_profile_id"]
    assert baseline["cost_overrides"] == bottleneck["cost_overrides"]
    assert baseline["algorithm"] == bottleneck["algorithm"]
    assert baseline["profile_ids"] == bottleneck["profile_ids"]

    baseline_scenario = baseline["scenario"]
    bottleneck_scenario = bottleneck["scenario"]
    for key in (
        "scenario_id",
        "recovery_window",
        "airports",
        "flights",
        "aircraft",
        "crew",
        "passengers",
    ):
        assert baseline_scenario[key] == bottleneck_scenario[key]

    def target_interval(scenario: dict) -> dict:
        return next(
            interval
            for interval in scenario["airport_intervals"]
            if interval["airport"] == "B"
            and interval["start_time"] == "2026-01-15T09:00:00Z"
            and interval["end_time"] == "2026-01-15T10:00:00Z"
        )

    baseline_target = target_interval(baseline_scenario)
    bottleneck_target = target_interval(bottleneck_scenario)

    assert baseline_target["dep_capacity"] == 4
    assert bottleneck_target["dep_capacity"] == 2
    assert baseline_target["arr_capacity"] == bottleneck_target["arr_capacity"]
    assert baseline_target["gate_capacity"] == bottleneck_target["gate_capacity"]

    assert baseline_scenario["disruptions"] == []
    assert bottleneck_scenario["disruptions"] == [
        {
            "airport": "B",
            "start_time": "2026-01-15T09:00:00Z",
            "end_time": "2026-01-15T10:00:00Z",
            "capacity_change": -2,
            "restriction_type": "departure_capacity_reduction",
        }
    ]
