from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from backend.main import app


CASE_ROOT = ROOT / "data" / "workbench_validation"
client = TestClient(app)


@dataclass(frozen=True)
class NormalRun:
    label: str
    bundle: str
    expected: str
    variant: str | None = None


@dataclass
class Row:
    case_id: str
    validate: str
    precheck: str
    solve_status: str
    expected_check: str
    passed: bool
    detail: str = ""


NORMAL_RUNS = [
    NormalRun(
        "001",
        "wb_v1_001_baseline_bundle.json",
        "wb_v1_001_baseline_expected.json",
    ),
    NormalRun(
        "002",
        "wb_v1_002_single_delay_bundle.json",
        "wb_v1_002_single_delay_expected.json",
    ),
    NormalRun(
        "003/default",
        "wb_v1_003_delay_vs_cancel_bundle.json",
        "wb_v1_003_delay_vs_cancel_expected.json",
        "default_costs",
    ),
    NormalRun(
        "003/low-cancel",
        "wb_v1_003_delay_vs_cancel_low_cancel_bundle.json",
        "wb_v1_003_delay_vs_cancel_expected.json",
        "low_cancellation_cost",
    ),
    NormalRun(
        "004",
        "wb_v1_004_aircraft_swap_bundle.json",
        "wb_v1_004_aircraft_swap_expected.json",
    ),
    NormalRun(
        "005/default",
        "wb_v1_005_crew_recovery_bundle.json",
        "wb_v1_005_crew_recovery_expected.json",
        "default_crew_cost",
    ),
    NormalRun(
        "005/high-crew-cost",
        "wb_v1_005_crew_recovery_high_crew_cost_bundle.json",
        "wb_v1_005_crew_recovery_expected.json",
        "high_crew_reassignment_cost",
    ),
    NormalRun(
        "006/default",
        "wb_v1_006_passenger_connection_bundle.json",
        "wb_v1_006_passenger_connection_expected.json",
        "default_capacity",
    ),
    NormalRun(
        "006/low-capacity",
        "wb_v1_006_passenger_connection_low_capacity_bundle.json",
        "wb_v1_006_passenger_connection_expected.json",
        "low_recovery_capacity",
    ),
    NormalRun(
        "007/baseline",
        "wb_v1_007_capacity_baseline_bundle.json",
        "wb_v1_007_capacity_bottleneck_expected.json",
        "baseline_capacity",
    ),
    NormalRun(
        "007/bottleneck",
        "wb_v1_007_capacity_bottleneck_bundle.json",
        "wb_v1_007_capacity_bottleneck_expected.json",
        "bottleneck_capacity",
    ),
]


INVALID_NEGATIVE_CASES = [
    ("008A", "wb_v1_008a_duplicate_flight_id.json"),
    ("008B", "wb_v1_008b_invalid_flight_time.json"),
    ("008C", "wb_v1_008c_invalid_duration.json"),
    ("008D", "wb_v1_008d_invalid_market_min_seats.json"),
    ("008E", "wb_v1_008e_invalid_disruption_interval.json"),
]


def _load_json(*parts: str) -> dict[str, Any]:
    return json.loads(CASE_ROOT.joinpath(*parts).read_text(encoding="utf-8"))


def _same_number(actual: Any, expected: Any) -> bool:
    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        return math.isclose(float(actual), float(expected), rel_tol=1e-9, abs_tol=1e-6)
    return actual == expected


def _resolved_by_flight(result: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        item["resolved"]["flight_id"]: item["resolved"]
        for item in result.get("resolved_flights", [])
    }


def _check_expected(result: dict[str, Any], spec: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    expected_status = spec.get("expected_status")
    if expected_status is not None and result.get("status") != expected_status:
        errors.append(
            f"status={result.get('status')!r}, expected {expected_status!r}"
        )

    expected_objective = spec.get("expected_objective")
    if expected_objective is not None:
        objective = result.get("objective")
        if objective is None:
            errors.append("objective is null")
        else:
            for key, expected_value in expected_objective.items():
                actual_value = objective.get(key)
                if not _same_number(actual_value, expected_value):
                    errors.append(
                        f"objective.{key}={actual_value!r}, expected {expected_value!r}"
                    )

    strong = spec.get("strong_assertions", {})
    selected = result.get("selected", {})
    resolved = _resolved_by_flight(result)
    metrics = result.get("metrics") or {}
    recovery = metrics.get("recovery") or {}

    if "selected_flight_options" in strong:
        actual = set(selected.get("flight_options", []))
        expected = set(strong["selected_flight_options"])
        if actual != expected:
            errors.append(
                f"selected flight options differ: actual={sorted(actual)!r}, "
                f"expected={sorted(expected)!r}"
            )

    if "cancelled_base_flights" in strong:
        actual = {
            flight_id
            for flight_id, item in resolved.items()
            if item.get("status") == "cancelled"
        }
        expected = set(strong["cancelled_base_flights"])
        if actual != expected:
            errors.append(
                f"cancelled flights differ: actual={sorted(actual)!r}, "
                f"expected={sorted(expected)!r}"
            )

    for key, field in (
        ("delayed_flights", "delayed_flights"),
        ("cancelled_flights", "cancelled_flights"),
        ("total_departure_delay_minutes", "total_flight_departure_delay_minutes"),
        ("aircraft_reassignment_count_total", "aircraft_reassignments"),
        ("crew_reassignment_count_total", "crew_reassignments"),
        ("passenger_reaccommodated_groups", "passenger_reaccommodated_groups"),
        ("passenger_reaccommodated_count", "passenger_reaccommodated_count"),
        ("passenger_delay_minutes_weighted", "passenger_delay_minutes_weighted"),
        ("unserved_passengers", "unserved_passengers"),
    ):
        if key in strong and recovery.get(field) != strong[key]:
            errors.append(
                f"metrics.recovery.{field}={recovery.get(field)!r}, "
                f"expected {strong[key]!r}"
            )

    if "max_departure_delay_minutes" in strong:
        actual = metrics.get("max_departure_delay_minutes")
        if actual != strong["max_departure_delay_minutes"]:
            errors.append(
                f"max_departure_delay_minutes={actual!r}, "
                f"expected {strong['max_departure_delay_minutes']!r}"
            )

    if "recovery_actions_count" in strong:
        actual = len(result.get("recovery_actions", []))
        if actual != strong["recovery_actions_count"]:
            errors.append(
                f"recovery_actions={actual}, expected {strong['recovery_actions_count']}"
            )

    if "passenger_outcomes_count" in strong:
        actual = len(result.get("passenger_outcomes", []))
        if actual != strong["passenger_outcomes_count"]:
            errors.append(
                f"passenger_outcomes={actual}, "
                f"expected {strong['passenger_outcomes_count']}"
            )

    if "integrated_audit_pass" in strong:
        actual = result.get("diagnostics", {}).get("integrated_audit_pass")
        if actual is not strong["integrated_audit_pass"]:
            errors.append(
                f"integrated_audit_pass={actual!r}, "
                f"expected {strong['integrated_audit_pass']!r}"
            )

    for assertion_key, result_key in (
        ("per_flight_departure_delay_minutes", "departure_delay_minutes"),
        ("per_flight_aircraft", "aircraft_id"),
        ("per_flight_crew", "crew_id"),
    ):
        if assertion_key in strong:
            for flight_id, expected_value in strong[assertion_key].items():
                actual = resolved.get(flight_id, {}).get(result_key)
                if actual != expected_value:
                    errors.append(
                        f"{flight_id}.{result_key}={actual!r}, "
                        f"expected {expected_value!r}"
                    )

    if "selected_passenger_itinerary" in strong:
        actual = selected.get("passenger_itineraries", [])
        expected = [strong["selected_passenger_itinerary"]]
        if actual != expected:
            errors.append(
                f"selected passenger itineraries={actual!r}, expected {expected!r}"
            )

    if any(
        key in strong
        for key in (
            "passenger_status",
            "passenger_arrival_delay_minutes",
            "passenger_count",
            "recovered_itinerary",
        )
    ):
        outcomes = result.get("passenger_outcomes", [])
        if len(outcomes) != 1:
            errors.append(
                f"expected exactly one passenger outcome, found {len(outcomes)}"
            )
        else:
            passenger = outcomes[0]
            outcome = passenger["outcome"]
            checks = (
                ("passenger_status", outcome.get("status")),
                (
                    "passenger_arrival_delay_minutes",
                    outcome.get("arrival_delay_minutes"),
                ),
                ("passenger_count", passenger.get("count")),
                ("recovered_itinerary", passenger.get("recovered_itinerary")),
            )
            for key, actual in checks:
                if key in strong and actual != strong[key]:
                    errors.append(
                        f"{key}={actual!r}, expected {strong[key]!r}"
                    )

    return errors


def _normal_run(run: NormalRun) -> Row:
    bundle = _load_json("bundles", run.bundle)
    expected_payload = _load_json("expected", run.expected)
    spec = (
        expected_payload["variants"][run.variant]
        if run.variant is not None
        else expected_payload
    )

    validation = client.post("/api/validate", json=bundle["scenario"])
    validate_ok = (
        validation.status_code == 200 and validation.json().get("valid") is True
    )
    validate_text = "PASS" if validate_ok else "FAIL"
    if not validate_ok:
        return Row(
            run.label,
            validate_text,
            "SKIP",
            "SKIP",
            "FAIL",
            False,
            f"validation: {validation.status_code} {validation.json()}",
        )

    precheck = client.post("/api/solve/precheck", json=bundle)
    readiness = precheck.json()
    precheck_ok = (
        precheck.status_code == 200
        and readiness.get("solve_ready") is True
        and readiness.get("missing_inputs") == []
        and readiness.get("invalid_profiles") == []
    )
    precheck_text = "READY" if precheck_ok else "NOT_READY"
    if not precheck_ok:
        return Row(
            run.label,
            validate_text,
            precheck_text,
            "SKIP",
            "FAIL",
            False,
            f"precheck: {readiness}",
        )

    response = client.post("/api/solve", json=bundle)
    if response.status_code != 200:
        return Row(
            run.label,
            validate_text,
            precheck_text,
            f"HTTP_{response.status_code}",
            "FAIL",
            False,
            str(response.json()),
        )

    result = response.json()
    errors = _check_expected(result, spec)
    return Row(
        run.label,
        validate_text,
        precheck_text,
        str(result.get("status")),
        "PASS" if not errors else "FAIL",
        not errors,
        "; ".join(errors),
    )


def _invalid_negative_run(subcase: str, filename: str) -> Row:
    expected = _load_json(
        "expected", "wb_v1_008_negative_cases_expected.json"
    )["subcases"][subcase]
    scenario = _load_json("negative", filename)
    response = client.post("/api/validate", json=scenario)
    payload = response.json()

    ok = (
        response.status_code == expected["expected_http_status"]
        and payload.get("valid") is expected["expected_valid"]
        and bool(payload.get("errors"))
    )
    if ok and "expected_error_code" in expected:
        ok = expected["expected_error_code"] in {
            item["code"] for item in payload["errors"]
        }
    if ok and "expected_message_contains" in expected:
        ok = any(
            expected["expected_message_contains"] in item["message"]
            for item in payload["errors"]
        )

    return Row(
        subcase,
        "EXPECTED_REJECT" if ok else "FAIL",
        "N/A",
        "N/A",
        "PASS" if ok else "FAIL",
        ok,
        "" if ok else f"validate response: {response.status_code} {payload}",
    )


def _case008f() -> Row:
    expected = _load_json(
        "expected", "wb_v1_008_negative_cases_expected.json"
    )["subcases"]["008F"]
    scenario = _load_json(
        "negative", "wb_v1_008f_scenario_only_missing_solve_inputs.json"
    )

    validation = client.post("/api/validate", json=scenario)
    validate_ok = (
        validation.status_code == expected["validate_expected_http_status"]
        and validation.json().get("valid") is expected["validate_expected_valid"]
    )

    incomplete_request = {
        "schema_version": "1.0.0",
        "scenario": scenario,
        "cost_profile_id": "phase2_test_v1",
        "cost_overrides": {},
        "algorithm": "benders_branch_and_price_v1",
    }
    precheck = client.post("/api/solve/precheck", json=incomplete_request)
    readiness = precheck.json()
    precheck_ok = (
        readiness.get("solve_ready") is expected["precheck_expected_solve_ready"]
        and set(readiness.get("missing_inputs", []))
        == set(expected["expected_missing_inputs"])
        and readiness.get("semantics")
        == "INPUT_READINESS_NOT_OPTIMIZATION_FEASIBILITY"
    )

    solve = client.post("/api/solve", json=incomplete_request)
    detail = solve.json().get("detail", {})
    solve_ok = (
        solve.status_code == expected["solve_expected_http_status"]
        and detail.get("status") == expected["solve_expected_status"]
        and set(expected["expected_missing_inputs"]).issubset(
            set(detail.get("codes", []))
        )
    )
    ok = validate_ok and precheck_ok and solve_ok
    return Row(
        "008F",
        "PASS" if validate_ok else "FAIL",
        "NOT_READY" if precheck_ok else "FAIL",
        expected["solve_expected_status"] if solve_ok else "FAIL",
        "PASS" if ok else "FAIL",
        ok,
        "" if ok else f"validate={validation.json()} precheck={readiness} solve={solve.json()}",
    )


def _case008g() -> Row:
    expected = _load_json(
        "expected", "wb_v1_008_negative_cases_expected.json"
    )["subcases"]["008G"]
    bundle = _load_json(
        "bundles", "wb_v1_008g_valid_but_infeasible_bundle.json"
    )

    validation = client.post("/api/validate", json=bundle["scenario"])
    validate_ok = (
        validation.status_code == expected["validate_expected_http_status"]
        and validation.json().get("valid") is expected["validate_expected_valid"]
    )

    precheck = client.post("/api/solve/precheck", json=bundle)
    readiness = precheck.json()
    precheck_ok = (
        precheck.status_code == 200
        and readiness.get("solve_ready") is expected["precheck_expected_solve_ready"]
        and readiness.get("missing_inputs") == []
        and readiness.get("invalid_profiles") == []
        and readiness.get("semantics")
        == "INPUT_READINESS_NOT_OPTIMIZATION_FEASIBILITY"
    )

    response = client.post("/api/solve", json=bundle)
    result = response.json()
    empty_selected = all(
        not result.get("selected", {}).get(key)
        for key in (
            "flight_options",
            "aircraft_strings",
            "crew_pairings",
            "passenger_itineraries",
        )
    )
    empty_outputs = all(
        not result.get(key)
        for key in (
            "resolved_flights",
            "aircraft_outcomes",
            "crew_outcomes",
            "passenger_outcomes",
            "recovery_actions",
        )
    )
    solve_ok = (
        response.status_code == expected["solve_expected_http_status"]
        and result.get("status") == expected["expected_status"]
        and result.get("objective") is expected["expected_objective"]
        and result.get("metrics") is None
        and empty_selected
        and empty_outputs
    )
    ok = validate_ok and precheck_ok and solve_ok
    return Row(
        "008G",
        "PASS" if validate_ok else "FAIL",
        "READY" if precheck_ok else "FAIL",
        str(result.get("status")) if response.status_code == 200 else f"HTTP_{response.status_code}",
        "PASS" if ok else "FAIL",
        ok,
        "" if ok else f"validate={validation.json()} precheck={readiness} solve={result}",
    )


def _matches_filter(label: str, filters: list[str]) -> bool:
    if not filters:
        return True
    normalized = label.lower()
    return any(item.lower() in normalized for item in filters)


def run_suite(filters: list[str] | None = None) -> list[Row]:
    filters = filters or []
    rows: list[Row] = []

    for run in NORMAL_RUNS:
        if _matches_filter(run.label, filters):
            rows.append(_normal_run(run))

    for subcase, filename in INVALID_NEGATIVE_CASES:
        if _matches_filter(subcase, filters) or _matches_filter("008", filters):
            rows.append(_invalid_negative_run(subcase, filename))

    if _matches_filter("008F", filters) or _matches_filter("008", filters):
        rows.append(_case008f())
    if _matches_filter("008G", filters) or _matches_filter("008", filters):
        rows.append(_case008g())

    return rows


def _print_rows(rows: list[Row]) -> None:
    headers = [
        "Case ID",
        "Validate",
        "Precheck",
        "Solve Status",
        "Expected Check",
        "PASS/FAIL",
    ]
    data = [
        [
            row.case_id,
            row.validate,
            row.precheck,
            row.solve_status,
            row.expected_check,
            "PASS" if row.passed else "FAIL",
        ]
        for row in rows
    ]
    widths = [
        max(len(headers[index]), *(len(item[index]) for item in data))
        for index in range(len(headers))
    ]

    def render(items: list[str]) -> str:
        return " | ".join(
            item.ljust(widths[index]) for index, item in enumerate(items)
        )

    print(render(headers))
    print("-+-".join("-" * width for width in widths))
    for items in data:
        print(render(items))

    failures = [row for row in rows if not row.passed]
    print()
    print(f"Summary: {len(rows) - len(failures)}/{len(rows)} PASS")
    if failures:
        print("Failures:")
        for row in failures:
            print(f"- {row.case_id}: {row.detail}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run Workbench v1 Case 001-008 system acceptance checks."
    )
    parser.add_argument(
        "--case",
        action="append",
        default=[],
        help=(
            "Optional case filter; repeatable. Examples: --case 006, "
            "--case 003/default, --case 008."
        ),
    )
    args = parser.parse_args()

    rows = run_suite(args.case)
    if not rows:
        print("No validation cases matched the requested --case filters.")
        return 2

    _print_rows(rows)
    return 0 if all(row.passed for row in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
