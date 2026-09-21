from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any

from backend.schemas.workbench import SnapshotRecord


PRIMARY_PRIORITY = (
    "cancelled",
    "od_changed",
    "time_changed",
    "aircraft_reassigned",
    "crew_reassigned",
    "block_time_changed",
    "unchanged",
)


def build_comparison(
    snapshot: SnapshotRecord, result: dict[str, Any] | None
) -> dict[str, Any]:
    original_scenario = snapshot.draft_document.scenario
    effective_scenario = snapshot.compile_preview.effective_scenario or original_scenario
    impacts = {
        item.flight_id: item.model_dump(mode="json")
        for item in snapshot.compile_preview.flight_impacts
    }
    resolved_by_id = {
        item["resolved"]["flight_id"]: item
        for item in (result or {}).get("resolved_flights", [])
    }
    original_by_id = {
        item["flight_id"]: item for item in original_scenario.get("flights", [])
    }
    effective_by_id = {
        item["flight_id"]: item for item in effective_scenario.get("flights", [])
    }
    optimal = bool(result and result.get("status") == "optimal")
    flights: list[dict[str, Any]] = []
    change_counts: Counter[str] = Counter()
    for flight_id, original in original_by_id.items():
        effective = effective_by_id.get(flight_id, original)
        recovery = resolved_by_id.get(flight_id)
        resolved = recovery.get("resolved") if recovery else None
        flags = _flight_change_flags(original, resolved) if optimal else []
        changed = bool(flags)
        if not flags:
            flags = ["unchanged"]
        primary = next(item for item in PRIMARY_PRIORITY if item in flags)
        for flag in flags:
            change_counts[flag] += 1
        flights.append(
            {
                "flight_id": flight_id,
                "original": original,
                "effective": effective,
                "impact": impacts.get(
                    flight_id,
                    {
                        "flight_id": flight_id,
                        "status": "normal",
                        "direct_rule_ids": [],
                        "propagation_sources": [],
                    },
                ),
                "recovered": resolved if optimal else None,
                "changed": changed,
                "change_flags": flags,
                "primary_change": primary,
            }
        )

    aircraft = _aircraft_comparison(original_scenario, result if optimal else None)
    crew = _crew_comparison(original_scenario, result if optimal else None)
    passengers = _passenger_comparison(original_scenario, result if optimal else None)
    return {
        "schema_version": "2.0.0",
        "snapshot_id": snapshot.snapshot_id,
        "input_hash": snapshot.content_hash,
        "optimization_status": (result or {}).get("status"),
        "recovered_available": optimal and len(resolved_by_id) == len(original_by_id),
        "mode_semantics": {
            "original": "Baseline schedule and resources only.",
            "impact": "Compiled capacity effects and exposure risk; not a recovery decision.",
            "recovered": "Solver-selected plan; available only for a complete optimal result.",
            "delta": "Original ghost plus recovered plan, classified by canonical change flags.",
        },
        "counts": {
            "total_flights": len(flights),
            "changed_flights": sum(1 for item in flights if item["changed"]),
            "unchanged_flights": sum(1 for item in flights if not item["changed"]),
            "change_flags": dict(sorted(change_counts.items())),
        },
        "flights": flights,
        "aircraft": aircraft,
        "crew": crew,
        "passengers": passengers,
        "capacity": {
            "baseline": _capacity_loads(original_scenario, original_scenario.get("flights", [])),
            "effective": _capacity_loads(effective_scenario, effective_scenario.get("flights", [])),
            "recovered": _capacity_loads(
                effective_scenario,
                [
                    _resolved_as_flight(item["resolved"])
                    for item in (result or {}).get("resolved_flights", [])
                    if item["resolved"].get("status") != "cancelled"
                ],
            )
            if optimal
            else [],
        },
        "objective": (result or {}).get("objective") if optimal else None,
        "delay_distribution": [
            {
                "flight_id": item["flight_id"],
                "departure_delay_minutes": item["recovered"].get(
                    "departure_delay_minutes", 0
                ),
                "arrival_delay_minutes": item["recovered"].get(
                    "arrival_delay_minutes", 0
                ),
            }
            for item in flights
            if item["recovered"] is not None
        ],
    }


def build_audit(
    snapshot: SnapshotRecord, result: dict[str, Any] | None, events: list[dict[str, Any]]
) -> dict[str, Any]:
    expected = snapshot.draft_document.expected
    expected_check = None
    if expected is not None and result is not None:
        expected_check = {
            "status_matches": expected.get("optimization_status") == result.get("status"),
            "objective_matches": _number_matches(
                expected.get("objective_total"),
                (result.get("objective") or {}).get("total"),
            ),
        }
    integrated_audit = next(
        (
            item.get("metrics", {}).get("integrated_audit")
            for item in events
            if item.get("event_type") == "audit_completed"
        ),
        None,
    )
    diagnostics = (result or {}).get("diagnostics") or {}
    lower = diagnostics.get("lower_bound")
    upper = diagnostics.get("upper_bound")
    absolute_gap = (
        max(0.0, float(upper) - float(lower))
        if lower is not None and upper is not None
        else None
    )
    relative_gap = (
        absolute_gap / max(abs(float(upper)), 1.0)
        if absolute_gap is not None and upper is not None
        else None
    )
    return {
        "schema_version": "2.0.0",
        "snapshot_id": snapshot.snapshot_id,
        "draft_id": snapshot.draft_id,
        "revision_id": snapshot.revision_id,
        "input_hash": snapshot.content_hash,
        "solve_request": snapshot.solve_request,
        "compile_preview": snapshot.compile_preview.model_dump(mode="json"),
        "result": result,
        "selected": (result or {}).get("selected"),
        "recovery_actions": (result or {}).get("recovery_actions", []),
        "objective": (result or {}).get("objective"),
        "diagnostics": diagnostics,
        "bounds": {
            "lower_bound": lower,
            "upper_bound": upper,
            "absolute_gap": absolute_gap,
            "relative_gap": relative_gap,
        },
        "integrated_audit": integrated_audit,
        "run_metadata": (result or {}).get("run_metadata"),
        "expected": expected,
        "expected_check": expected_check,
        "events": events,
        "evidence_boundary": (
            "Exposure and binding constraints are evidence; they are not asserted as causal explanations for a selected recovery action."
        ),
    }


def _flight_change_flags(
    original: dict[str, Any], resolved: dict[str, Any] | None
) -> list[str]:
    if resolved is None:
        return []
    if resolved.get("status") == "cancelled":
        return ["cancelled"]
    flags: list[str] = []
    if (
        resolved.get("recovered_origin") != original.get("origin")
        or resolved.get("recovered_destination") != original.get("destination")
    ):
        flags.append("od_changed")
    if (
        int(resolved.get("departure_delay_minutes") or 0) != 0
        or int(resolved.get("arrival_delay_minutes") or 0) != 0
    ):
        flags.append("time_changed")
    if resolved.get("aircraft_id") != original.get("original_aircraft"):
        flags.append("aircraft_reassigned")
    if resolved.get("crew_id") != original.get("original_crew"):
        flags.append("crew_reassigned")
    recovered_dep = _parse_time(resolved.get("recovered_dep"))
    recovered_arr = _parse_time(resolved.get("recovered_arr"))
    if recovered_dep and recovered_arr:
        block = int((recovered_arr - recovered_dep).total_seconds() / 60)
        if block != int(original.get("duration") or block):
            flags.append("block_time_changed")
    return flags


def _aircraft_comparison(scenario: dict[str, Any], result: dict[str, Any] | None):
    outcomes = {
        item["aircraft_id"]: item for item in (result or {}).get("aircraft_outcomes", [])
    }
    values = []
    for item in scenario.get("aircraft", []):
        outcome = outcomes.get(item["tail_id"])
        original = item.get("original_rotation", [])
        recovered = outcome.get("recovered_flight_ids", []) if outcome else None
        values.append(
            {
                "aircraft_id": item["tail_id"],
                "original_rotation": original,
                "recovered_rotation": recovered,
                "changed": recovered is not None and recovered != original,
                "outcome": outcome,
            }
        )
    return values


def _crew_comparison(scenario: dict[str, Any], result: dict[str, Any] | None):
    outcomes = {item["crew_id"]: item for item in (result or {}).get("crew_outcomes", [])}
    values = []
    for item in scenario.get("crew", []):
        outcome = outcomes.get(item["crew_id"])
        original = item.get("original_pairing", [])
        recovered = outcome.get("operated_flights", []) if outcome else None
        values.append(
            {
                "crew_id": item["crew_id"],
                "original_pairing": original,
                "recovered_operate": recovered,
                "deadhead": outcome.get("deadhead_flights", []) if outcome else None,
                "changed": recovered is not None and recovered != original,
                "outcome": outcome,
            }
        )
    return values


def _passenger_comparison(scenario: dict[str, Any], result: dict[str, Any] | None):
    outcomes = {
        item["outcome"]["pax_group_id"]: item
        for item in (result or {}).get("passenger_outcomes", [])
    }
    values = []
    for item in scenario.get("passengers", []):
        outcome = outcomes.get(item["pax_group_id"])
        original = item.get("original_itinerary", [])
        recovered = outcome.get("recovered_itinerary", []) if outcome else None
        values.append(
            {
                "pax_group_id": item["pax_group_id"],
                "count": item.get("count"),
                "original_itinerary": original,
                "recovered_itinerary": recovered,
                "changed": recovered is not None and recovered != original,
                "outcome": outcome,
            }
        )
    return values


def _capacity_loads(scenario: dict[str, Any], flights: list[dict[str, Any]]):
    rows = []
    for interval in scenario.get("airport_intervals", []):
        start = _parse_time(interval.get("start_time"))
        end = _parse_time(interval.get("end_time"))
        if start is None or end is None:
            continue
        departure_load = sum(
            1
            for flight in flights
            if flight.get("origin") == interval.get("airport")
            and _inside(flight.get("sched_dep"), start, end)
        )
        arrival_load = sum(
            1
            for flight in flights
            if flight.get("destination") == interval.get("airport")
            and _inside(flight.get("sched_arr"), start, end)
        )
        rows.append(
            {
                "airport_id": interval.get("airport"),
                "start_time": interval.get("start_time"),
                "end_time": interval.get("end_time"),
                "departure_load": departure_load,
                "departure_capacity": interval.get("dep_capacity"),
                "arrival_load": arrival_load,
                "arrival_capacity": interval.get("arr_capacity"),
            }
        )
    return rows


def _resolved_as_flight(resolved: dict[str, Any]) -> dict[str, Any]:
    return {
        "flight_id": resolved.get("flight_id"),
        "origin": resolved.get("recovered_origin"),
        "destination": resolved.get("recovered_destination"),
        "sched_dep": resolved.get("recovered_dep"),
        "sched_arr": resolved.get("recovered_arr"),
    }


def _parse_time(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _inside(value: Any, start: datetime, end: datetime) -> bool:
    parsed = _parse_time(value)
    return parsed is not None and start <= parsed < end


def _number_matches(left: Any, right: Any) -> bool:
    if left is None or right is None:
        return left is right
    return abs(float(left) - float(right)) <= 1e-5
