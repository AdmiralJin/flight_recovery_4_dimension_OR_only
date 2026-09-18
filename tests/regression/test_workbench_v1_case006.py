import copy
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
        ("default_capacity", "wb_v1_006_passenger_connection_bundle.json"),
        (
            "low_recovery_capacity",
            "wb_v1_006_passenger_connection_low_capacity_bundle.json",
        ),
    ],
)
def test_workbench_v1_case006_passenger_recovery_exact_solve(
    variant_name: str,
    bundle_name: str,
):
    bundle = _load_json("bundles", bundle_name)
    expected = _load_json(
        "expected", "wb_v1_006_passenger_connection_expected.json"
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
    assert set(result["selected"]["flight_options"]) == set(
        strong["selected_flight_options"]
    )
    assert result["selected"]["passenger_itineraries"] == [
        strong["selected_passenger_itinerary"]
    ]

    resolved = {
        item["resolved"]["flight_id"]: item["resolved"]
        for item in result["resolved_flights"]
    }
    assert resolved["WB6_F101"]["departure_delay_minutes"] == 60
    assert resolved["WB6_F102"]["departure_delay_minutes"] == 0
    assert resolved["WB6_F103"]["departure_delay_minutes"] == 0

    assert resolved["WB6_F101"]["aircraft_id"] == "WB6_AC1"
    assert resolved["WB6_F102"]["aircraft_id"] == "WB6_AC2"
    assert resolved["WB6_F103"]["aircraft_id"] == "WB6_AC3"
    assert resolved["WB6_F101"]["crew_id"] == "WB6_C1"
    assert resolved["WB6_F102"]["crew_id"] == "WB6_C2"
    assert resolved["WB6_F103"]["crew_id"] == "WB6_C3"

    assert len(result["passenger_outcomes"]) == 1
    passenger = result["passenger_outcomes"][0]
    assert passenger["outcome"]["pax_group_id"] == "WB6_PG1"
    assert passenger["outcome"]["selected_itinerary_id"] == strong[
        "selected_passenger_itinerary"
    ]
    assert passenger["outcome"]["status"] == strong["passenger_status"]
    assert passenger["outcome"]["arrival_delay_minutes"] == strong[
        "passenger_arrival_delay_minutes"
    ]
    assert passenger["count"] == strong["passenger_count"]
    assert passenger["recovered_itinerary"] == strong["recovered_itinerary"]
    if strong["passenger_status"] == "transported":
        assert passenger["outcome"]["unserved_count"] == 0
    else:
        assert passenger["outcome"]["unserved_count"] == strong["passenger_count"]

    recovery_metrics = result["metrics"]["recovery"]
    assert recovery_metrics["passenger_reaccommodated_groups"] == strong[
        "passenger_reaccommodated_groups"
    ]
    assert recovery_metrics["passenger_reaccommodated_count"] == strong[
        "passenger_reaccommodated_count"
    ]
    assert recovery_metrics["passenger_delay_minutes_weighted"] == strong[
        "passenger_delay_minutes_weighted"
    ]
    assert recovery_metrics["unserved_passengers"] == strong["unserved_passengers"]
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

    assert len(result["recovery_actions"]) == strong["recovery_actions_count"]
    assert result["diagnostics"]["integrated_audit_pass"] is strong[
        "integrated_audit_pass"
    ]
    assert result["diagnostics"]["formal_full_enumerators_used"] is False


def test_workbench_v1_case006_variants_change_only_residual_capacity():
    default = _load_json(
        "bundles", "wb_v1_006_passenger_connection_bundle.json"
    )
    low = _load_json(
        "bundles", "wb_v1_006_passenger_connection_low_capacity_bundle.json"
    )

    assert default["scenario"] == low["scenario"]
    assert default["recovery_columns"] == low["recovery_columns"]
    assert default["cost_profile_id"] == low["cost_profile_id"]
    assert default["cost_overrides"] == low["cost_overrides"]
    assert default["algorithm"] == low["algorithm"]
    assert default["profile_ids"] == low["profile_ids"]

    default_capacity = copy.deepcopy(default["capacity_profile"])
    low_capacity = copy.deepcopy(low["capacity_profile"])
    default_capacity.pop("capacity_profile_id")
    low_capacity.pop("capacity_profile_id")
    default_capacity.pop("notes")
    low_capacity.pop("notes")
    default_capacity["seat_capacity_by_option_id"]["WB6_F103_ORIG"] = 10

    assert default_capacity == low_capacity
    assert default["capacity_profile"]["seat_capacity_by_option_id"][
        "WB6_F103_ORIG"
    ] == 40
    assert low["capacity_profile"]["seat_capacity_by_option_id"][
        "WB6_F103_ORIG"
    ] == 10
