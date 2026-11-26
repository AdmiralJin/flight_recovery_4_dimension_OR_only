from copy import deepcopy
from pathlib import Path
import json

from backend.core import prm, srm
from backend.services.constraint_precheck import precheck_constraints


PROJECT_ROOT = Path(__file__).parents[2]


def _capacity_data():
    return json.loads(
        (PROJECT_ROOT / "data" / "capacities" / "phase2_test_seat_capacity_v1.json").read_text(encoding="utf-8")
    )


def _by_id(result):
    return {item["constraint_id"]: item for item in result["results"]}


def test_benchmark_precheck_has_no_failed_input_checks(
    phase1_benchmark_001_data, phase1_columns_001_data
):
    result = precheck_constraints(
        phase1_benchmark_001_data,
        phase1_columns_001_data,
        _capacity_data(),
    )

    assert result["precheck_semantics"] == "DETERMINISTIC_PRECHECK_NOT_MIP_FEASIBILITY"
    assert result["overall_status"] == "warning"
    assert not [item for item in result["results"] if item["status"] == "failed"]
    assert _by_id(result)[prm.PRM_C03_SEAT_CAPACITY]["status"] == "passed"


def test_precheck_detects_broken_flight_option_coverage(
    phase1_benchmark_001_data, phase1_columns_001_data
):
    broken = deepcopy(phase1_columns_001_data)
    broken["flight_options"] = [
        item for item in broken["flight_options"] if item.get("base_flight_id") != "F1"
    ]

    result = precheck_constraints(phase1_benchmark_001_data, broken)

    assert result["overall_status"] == "failed"
    check = _by_id(result)[srm.SRM_C01_FLIGHT_COVERAGE]
    assert check["status"] == "failed"
    assert "F1" in " ".join(check["issues"])


def test_precheck_rejects_broken_capacity_input(
    phase1_benchmark_001_data, phase1_columns_001_data
):
    capacity = _capacity_data()
    capacity["seat_capacity_by_option_id"]["FO_F1_ORIG"] = -1

    result = precheck_constraints(
        phase1_benchmark_001_data, phase1_columns_001_data, capacity
    )

    assert _by_id(result)[prm.PRM_C03_SEAT_CAPACITY]["status"] == "failed"


def test_precheck_warns_when_passenger_capacity_is_missing(
    phase1_benchmark_001_data, phase1_columns_001_data
):
    result = precheck_constraints(
        phase1_benchmark_001_data, phase1_columns_001_data
    )

    check = _by_id(result)[prm.PRM_C03_SEAT_CAPACITY]
    assert check["status"] == "warning"
    assert check["derived_values"]["capacity_profile_present"] is False


def test_scenario_only_precheck_runs_available_checks_instead_of_uniform_warning(
    phase1_benchmark_001_data,
):
    result = precheck_constraints(phase1_benchmark_001_data)
    checks = _by_id(result)

    assert result["overall_status"] == "warning"
    assert {item["status"] for item in result["results"]} == {"passed", "warning"}
    assert checks[srm.SRM_C03_ARRIVAL_CAPACITY]["status"] == "passed"
    assert checks[srm.SRM_C04_DEPARTURE_CAPACITY]["status"] == "passed"
    assert checks[srm.SRM_C06_MARKET_SEAT]["status"] == "passed"
    assert checks[srm.SRM_C01_FLIGHT_COVERAGE]["status"] == "warning"
    assert checks[prm.PRM_C03_SEAT_CAPACITY]["status"] == "warning"
