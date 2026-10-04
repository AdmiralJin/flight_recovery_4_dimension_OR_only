from __future__ import annotations

from datetime import datetime
from typing import Any

from backend.schemas.workbench import (
    CompilePreview,
    DraftDocument,
    SnapshotRecord,
    VisualizationAvailability,
    VisualizationModel,
)

from .comparison import build_comparison


def build_draft_visualization(
    draft_id: str,
    working_hash: str,
    document: DraftDocument,
    preview: CompilePreview,
) -> VisualizationModel:
    return _build_model(
        source_type="draft",
        source_id=draft_id,
        draft_id=draft_id,
        document=document,
        preview=preview,
        working_hash=working_hash,
    )


def build_run_visualization(
    snapshot: SnapshotRecord,
    result: dict[str, Any] | None,
    solution_artifact: dict[str, Any] | None,
    *,
    run_id: str,
    optimization_status: str | None,
) -> VisualizationModel:
    return _build_model(
        source_type="run",
        source_id=run_id,
        draft_id=snapshot.draft_id,
        document=snapshot.draft_document,
        preview=snapshot.compile_preview,
        snapshot_id=snapshot.snapshot_id,
        run_id=run_id,
        input_hash=snapshot.content_hash,
        result=result,
        solution_artifact=solution_artifact,
        optimization_status=optimization_status,
    )


def _build_model(
    *,
    source_type: str,
    source_id: str,
    draft_id: str,
    document: DraftDocument,
    preview: CompilePreview,
    working_hash: str | None = None,
    snapshot_id: str | None = None,
    run_id: str | None = None,
    input_hash: str | None = None,
    result: dict[str, Any] | None = None,
    solution_artifact: dict[str, Any] | None = None,
    optimization_status: str | None = None,
) -> VisualizationModel:
    original = document.scenario
    effective = preview.effective_scenario or original
    original_flights = original.get("flights", [])
    effective_by_id = {
        item["flight_id"]: item for item in effective.get("flights", [])
    }
    impacts = {
        item.flight_id: item.model_dump(mode="json")
        for item in preview.flight_impacts
    }
    recovered_by_id = {
        item["resolved"]["flight_id"]: item["resolved"]
        for item in (result or {}).get("resolved_flights", [])
    }
    optimal = bool(result and result.get("status") == "optimal")
    recovered_complete = optimal and len(recovered_by_id) == len(original_flights)

    if source_type == "run":
        comparison = build_comparison(
            SnapshotRecord(
                snapshot_id=snapshot_id,
                draft_id=draft_id,
                revision_id="visualization",
                content_hash=input_hash or preview.compiled_hash or preview.draft_hash,
                created_at=datetime.now().astimezone().isoformat(),
                solve_request={},
                compile_preview=preview,
                draft_document=document,
            ),
            result,
        )
        comparison_by_id = {
            item["flight_id"]: item for item in comparison["flights"]
        }
    else:
        comparison = None
        comparison_by_id = {}

    passenger_links: dict[str, list[str]] = {}
    for passenger in original.get("passengers", []):
        for flight_id in passenger.get("original_itinerary", []):
            passenger_links.setdefault(flight_id, []).append(passenger["pax_group_id"])

    flights = []
    for flight in original_flights:
        flight_id = flight["flight_id"]
        compared = comparison_by_id.get(flight_id)
        flights.append(
            {
                "flight_id": flight_id,
                "original": flight,
                "effective": effective_by_id.get(flight_id, flight),
                "impact": impacts.get(flight_id, _normal_impact(flight_id)),
                "recovered": recovered_by_id.get(flight_id) if optimal else None,
                "changed": bool(compared and compared["changed"]),
                "change_flags": compared["change_flags"] if compared else ["unchanged"],
                "primary_change": compared["primary_change"] if compared else "unchanged",
                "resources": {
                    "original_aircraft": flight.get("original_aircraft"),
                    "original_crew": flight.get("original_crew"),
                    "recovered_aircraft": recovered_by_id.get(flight_id, {}).get("aircraft_id"),
                    "recovered_crew": recovered_by_id.get(flight_id, {}).get("crew_id"),
                },
                "passenger_group_ids": passenger_links.get(flight_id, []),
            }
        )

    options = {
        item["option_id"]: item
        for item in (solution_artifact or {}).get("flight_options", [])
    }
    aircraft, aircraft_full = _aircraft_timelines(
        original, flights, result, solution_artifact, options
    )
    crew, crew_full = _crew_timelines(
        original, flights, result, solution_artifact, options
    )
    passengers, passengers_full = _passenger_timelines(
        original, flights, result, solution_artifact, options
    )
    capacity = _capacity_sets(original, effective, recovered_by_id if optimal else {})
    disruptions = _disruption_windows(document, preview)
    propagation_edges = _propagation_edges(preview)
    delay_distribution = (
        comparison["delay_distribution"] if comparison else []
    )
    cost_items = _cost_items(solution_artifact)

    mode_availability = {
        "original": _available(bool(original_flights), "No baseline flights are defined."),
        "impact": _available(
            bool(preview.effective_scenario and preview.flight_impacts),
            "Compile the draft successfully to view effective disruption impact.",
        ),
        "recovered": _available(
            recovered_complete,
            "A complete optimal result is required for recovered views.",
        ),
        "delta": _available(
            recovered_complete,
            "A complete optimal result is required for delta views.",
        ),
    }
    layer_availability = {
        "flights": _available(bool(flights), "No flights are defined."),
        "disruptions": _available(bool(disruptions), "No disruption windows are defined."),
        "aircraft": _available(bool(aircraft), "No aircraft are defined."),
        "aircraft_recovered_detail": _available(
            aircraft_full, "Selected Aircraft String artifact is unavailable; showing result fallback."
        ),
        "crew": _available(bool(crew), "No crew are defined."),
        "crew_recovered_detail": _available(
            crew_full, "Selected Crew Pairing artifact is unavailable; REST and transfer may be incomplete."
        ),
        "passengers": _available(bool(passengers), "No passenger groups are defined."),
        "passenger_recovered_detail": _available(
            passengers_full, "Selected Passenger Itinerary artifact is unavailable; surface segments may be incomplete."
        ),
        "capacity": _available(
            bool(capacity["baseline"]), "No airport capacity intervals are defined."
        ),
        "propagation": _available(
            bool(propagation_edges), "No resource-sequence propagation evidence is available."
        ),
        "cost": _available(bool((result or {}).get("objective")), "No optimal objective is available."),
        "delay": _available(bool(delay_distribution), "No recovered delay distribution is available."),
    }
    time_range = _time_range(
        flights, disruptions, capacity, aircraft, crew, passengers
    )
    return VisualizationModel(
        source_type=source_type,
        source_id=source_id,
        draft_id=draft_id,
        snapshot_id=snapshot_id,
        run_id=run_id,
        working_hash=working_hash,
        compiled_hash=preview.compiled_hash,
        input_hash=input_hash,
        optimization_status=optimization_status or (result or {}).get("status"),
        time_range=time_range,
        mode_availability=mode_availability,
        layer_availability=layer_availability,
        issues=preview.issues,
        disruptions=disruptions,
        flights=flights,
        propagation_edges=propagation_edges,
        aircraft=aircraft,
        crew=crew,
        passengers=passengers,
        capacity=capacity,
        objective=(result or {}).get("objective"),
        cost_items=cost_items,
        delay_distribution=delay_distribution,
        recovery_actions=(result or {}).get("recovery_actions", []),
    )


def _available(value: bool, reason: str) -> VisualizationAvailability:
    return VisualizationAvailability(available=value, reason=None if value else reason)


def _normal_impact(flight_id: str) -> dict[str, Any]:
    return {
        "flight_id": flight_id,
        "status": "normal",
        "direct_rule_ids": [],
        "propagation_sources": [],
    }


def _disruption_windows(
    document: DraftDocument, preview: CompilePreview
) -> list[dict[str, Any]]:
    changes = [item.model_dump(mode="json") for item in preview.capacity_changes]
    if document.typed_disruptions:
        windows = []
        for rule in document.typed_disruptions:
            direction = (
                "arrival"
                if rule.rule_type.value == "arrival_capacity_delta"
                else "departure"
                if rule.rule_type.value == "departure_capacity_delta"
                else "both"
            )
            windows.append(
                {
                    **rule.model_dump(mode="json"),
                    "direction": direction,
                    "capacity_changes": [
                        item
                        for item in changes
                        if rule.rule_id in item.get("applied_rule_ids", [])
                    ],
                    "semantics": "compiled_rule",
                }
            )
        return windows
    return [
        {
            "rule_id": f"legacy-{index}",
            "rule_type": item.get("restriction_type", "unknown"),
            "airport_id": item.get("airport"),
            "start_time": item.get("start_time"),
            "end_time": item.get("end_time"),
            "capacity_delta": item.get("capacity_change"),
            "direction": _legacy_direction(str(item.get("restriction_type", ""))),
            "enabled": True,
            "source": "legacy_effective_input",
            "capacity_changes": [],
            "semantics": "legacy_already_effective",
        }
        for index, item in enumerate(document.scenario.get("disruptions", []))
    ]


def _legacy_direction(value: str) -> str:
    lowered = value.lower()
    if "arr" in lowered:
        return "arrival"
    if "dep" in lowered:
        return "departure"
    if any(token in lowered for token in ("closure", "closed", "curfew")):
        return "both"
    return "unknown"


def _propagation_edges(preview: CompilePreview) -> list[dict[str, Any]]:
    edges = []
    seen: set[tuple[str, str, str, str]] = set()
    for impact in preview.flight_impacts:
        for source in impact.propagation_sources:
            key = (
                str(source.get("source_flight_id")),
                impact.flight_id,
                str(source.get("type")),
                str(source.get("resource_id")),
            )
            if key in seen:
                continue
            seen.add(key)
            edges.append(
                {
                    "source_flight_id": key[0],
                    "target_flight_id": key[1],
                    "resource_type": key[2],
                    "resource_id": key[3],
                    "evidence": "resource_sequence_exposure",
                }
            )
    return edges


def _flight_leg(flight: dict[str, Any], *, state: str, segment_type: str = "flight") -> dict[str, Any]:
    return {
        "segment_id": flight.get("flight_id") or flight.get("option_id"),
        "flight_id": flight.get("flight_id") or flight.get("base_flight_id"),
        "segment_type": segment_type,
        "origin": flight.get("origin") or flight.get("recovered_origin"),
        "destination": flight.get("destination") or flight.get("recovered_destination"),
        "start_time": flight.get("sched_dep") or flight.get("dep_time") or flight.get("recovered_dep"),
        "end_time": flight.get("sched_arr") or flight.get("arr_time") or flight.get("recovered_arr"),
        "state": state,
    }


def _aircraft_timelines(
    scenario: dict[str, Any],
    flights: list[dict[str, Any]],
    result: dict[str, Any] | None,
    artifact: dict[str, Any] | None,
    options: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], bool]:
    originals = {item["flight_id"]: item["original"] for item in flights}
    recovered = {item["flight_id"]: item["recovered"] for item in flights if item["recovered"]}
    strings = {
        item["aircraft_id"]: item for item in (artifact or {}).get("aircraft_strings", [])
    }
    outcomes = {item["aircraft_id"]: item for item in (result or {}).get("aircraft_outcomes", [])}
    rows = []
    for aircraft in scenario.get("aircraft", []):
        aircraft_id = aircraft["tail_id"]
        original_segments = [
            _flight_leg(originals[item], state="original")
            for item in aircraft.get("original_rotation", [])
            if item in originals
        ]
        selected = strings.get(aircraft_id)
        if selected:
            recovered_segments = [
                _flight_leg(
                    options[option_id],
                    state="ferry" if options[option_id].get("operation_type") == "ferry" else "recovered",
                    segment_type="ferry" if options[option_id].get("operation_type") == "ferry" else "flight",
                )
                for option_id in selected.get("leg_option_ids", [])
                if option_id in options
            ]
        else:
            outcome = outcomes.get(aircraft_id, {})
            recovered_segments = [
                _flight_leg(recovered[item], state="recovered")
                for item in outcome.get("recovered_flight_ids", [])
                if item in recovered
            ]
        rows.append(
            {
                "aircraft_id": aircraft_id,
                "equipment_type": aircraft.get("equipment_type"),
                "initial_station": aircraft.get("initial_station_at_t"),
                "required_final_station": aircraft.get("required_station_at_T_end"),
                "actual_final_station": outcomes.get(aircraft_id, {}).get("final_station"),
                "maintenance_required": aircraft.get("maintenance_required", False),
                "maintenance_stations": aircraft.get("maintenance_stations", []),
                "original_segments": _with_ground_intervals(original_segments),
                "recovered_segments": _with_ground_intervals(recovered_segments),
                "changed": outcomes.get(aircraft_id, {}).get("reassignment_count", 0) > 0,
            }
        )
    return rows, bool(strings) or not bool(result and result.get("status") == "optimal")


def _with_ground_intervals(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = sorted(segments, key=lambda item: str(item.get("start_time") or ""))
    result: list[dict[str, Any]] = []
    for segment in ordered:
        if result:
            previous = result[-1]
            if previous.get("end_time") and segment.get("start_time") and previous["end_time"] < segment["start_time"]:
                result.append(
                    {
                        "segment_id": f"ground-{previous.get('segment_id')}-{segment.get('segment_id')}",
                        "segment_type": "ground",
                        "origin": previous.get("destination"),
                        "destination": segment.get("origin"),
                        "start_time": previous["end_time"],
                        "end_time": segment["start_time"],
                        "state": "ground",
                    }
                )
        result.append(segment)
    return result


def _crew_timelines(
    scenario: dict[str, Any],
    flights: list[dict[str, Any]],
    result: dict[str, Any] | None,
    artifact: dict[str, Any] | None,
    options: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], bool]:
    originals = {item["flight_id"]: item["original"] for item in flights}
    pairings = {item["crew_id"]: item for item in (artifact or {}).get("crew_pairings", [])}
    outcomes = {item["crew_id"]: item for item in (result or {}).get("crew_outcomes", [])}
    rows = []
    for crew in scenario.get("crew", []):
        original_duties = []
        for duty_index, duty in enumerate(crew.get("original_duties", []), start=1):
            original_duties.append(
                {
                    "duty_id": f"original-{duty_index}",
                    "segments": [
                        {**_flight_leg(originals[item], state="original"), "segment_type": "operate"}
                        for item in duty
                        if item in originals
                    ],
                }
            )
        pairing = pairings.get(crew["crew_id"])
        recovered_duties = []
        if pairing:
            for duty in pairing.get("duties", []):
                segments = []
                for segment in duty.get("segments", []):
                    option = options.get(segment.get("flight_option_id", ""), {})
                    segments.append(
                        {
                            "segment_id": segment.get("flight_option_id") or f"{duty.get('duty_id')}-{len(segments)}",
                            "flight_id": option.get("base_flight_id"),
                            "segment_type": segment.get("segment_type"),
                            "origin": segment.get("origin") or option.get("origin"),
                            "destination": segment.get("destination") or option.get("destination"),
                            "start_time": segment.get("start_time") or option.get("dep_time"),
                            "end_time": segment.get("end_time") or option.get("arr_time"),
                            "state": segment.get("segment_type"),
                        }
                    )
                recovered_duties.append({"duty_id": duty.get("duty_id"), "segments": segments})
        rows.append(
            {
                "crew_id": crew["crew_id"],
                "rating": crew.get("rating"),
                "start_station": crew.get("start_station_at_t"),
                "required_final_station": crew.get("required_station_at_T_end"),
                "actual_final_station": outcomes.get(crew["crew_id"], {}).get("final_station"),
                "original_duties": original_duties,
                "recovered_duties": recovered_duties,
                "changed": outcomes.get(crew["crew_id"], {}).get("reassignment_count", 0) > 0,
            }
        )
    return rows, bool(pairings) or not bool(result and result.get("status") == "optimal")


def _passenger_timelines(
    scenario: dict[str, Any],
    flights: list[dict[str, Any]],
    result: dict[str, Any] | None,
    artifact: dict[str, Any] | None,
    options: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], bool]:
    originals = {item["flight_id"]: item for item in flights}
    itineraries = {
        item["pax_group_id"]: item
        for item in (artifact or {}).get("passenger_itineraries", [])
    }
    outcomes = {
        item["outcome"]["pax_group_id"]: item
        for item in (result or {}).get("passenger_outcomes", [])
    }
    rows = []
    for passenger in scenario.get("passengers", []):
        group_id = passenger["pax_group_id"]
        original_segments = [
            {**_flight_leg(originals[item]["original"], state="original"), "flight_id": item}
            for item in passenger.get("original_itinerary", [])
            if item in originals
        ]
        itinerary = itineraries.get(group_id)
        recovered_segments = []
        if itinerary:
            for index, segment in enumerate(itinerary.get("segments", [])):
                option = options.get(segment.get("flight_option_id", ""), {})
                recovered_segments.append(
                    {
                        "segment_id": segment.get("flight_option_id") or f"surface-{group_id}-{index}",
                        "flight_id": option.get("base_flight_id"),
                        "segment_type": segment.get("segment_type"),
                        "origin": segment.get("origin") or option.get("origin"),
                        "destination": segment.get("destination") or option.get("destination"),
                        "start_time": segment.get("dep_time") or option.get("dep_time"),
                        "end_time": segment.get("arr_time") or option.get("arr_time"),
                        "state": segment.get("segment_type"),
                    }
                )
        outcome = outcomes.get(group_id, {})
        outcome_data = outcome.get("outcome", {})
        affected = [
            item for item in passenger.get("original_itinerary", [])
            if originals.get(item, {}).get("impact", {}).get("status") != "normal"
        ]
        rows.append(
            {
                "pax_group_id": group_id,
                "count": passenger.get("count"),
                "origin": passenger.get("origin"),
                "destination": passenger.get("destination"),
                "first_affected_flight_id": affected[0] if affected else None,
                "original_segments": original_segments,
                "recovered_segments": recovered_segments,
                "status": outcome_data.get("status"),
                "arrival_delay_minutes": outcome_data.get("arrival_delay_minutes"),
                "unserved_count": outcome_data.get("unserved_count", 0),
                "changed": bool(outcome and outcome.get("recovered_itinerary") != passenger.get("original_itinerary")),
            }
        )
    return rows, bool(itineraries) or not bool(result and result.get("status") == "optimal")


def _capacity_sets(
    original: dict[str, Any],
    effective: dict[str, Any],
    recovered_by_id: dict[str, dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    original_flights = original.get("flights", [])
    effective_flights = effective.get("flights", [])
    recovered_flights = [
        {
            "flight_id": item["flight_id"],
            "origin": item.get("recovered_origin"),
            "destination": item.get("recovered_destination"),
            "sched_dep": item.get("recovered_dep"),
            "sched_arr": item.get("recovered_arr"),
        }
        for item in recovered_by_id.values()
        if item.get("status") != "cancelled"
    ]
    return {
        "baseline": _capacity_rows(original, original_flights),
        "effective": _capacity_rows(effective, effective_flights),
        "recovered": _capacity_rows(effective, recovered_flights) if recovered_by_id else [],
    }


def _capacity_rows(scenario: dict[str, Any], flights: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for interval in scenario.get("airport_intervals", []):
        start = _parse_time(interval.get("start_time"))
        end = _parse_time(interval.get("end_time"))
        if start is None or end is None:
            continue
        departure_load = sum(
            flight.get("origin") == interval.get("airport")
            and _inside(flight.get("sched_dep"), start, end)
            for flight in flights
        )
        arrival_load = sum(
            flight.get("destination") == interval.get("airport")
            and _inside(flight.get("sched_arr"), start, end)
            for flight in flights
        )
        dep_capacity = int(interval.get("dep_capacity") or 0)
        arr_capacity = int(interval.get("arr_capacity") or 0)
        rows.append(
            {
                "airport_id": interval.get("airport"),
                "start_time": interval.get("start_time"),
                "end_time": interval.get("end_time"),
                "departure_load": departure_load,
                "departure_capacity": dep_capacity,
                "departure_slack": dep_capacity - departure_load,
                "departure_utilization": departure_load / dep_capacity if dep_capacity else None,
                "departure_binding": departure_load >= dep_capacity,
                "arrival_load": arrival_load,
                "arrival_capacity": arr_capacity,
                "arrival_slack": arr_capacity - arrival_load,
                "arrival_utilization": arrival_load / arr_capacity if arr_capacity else None,
                "arrival_binding": arrival_load >= arr_capacity,
            }
        )
    return rows


def _cost_items(artifact: dict[str, Any] | None) -> list[dict[str, Any]]:
    items = []
    for collection, entity_type, id_key in (
        ("aircraft_strings", "aircraft", "aircraft_id"),
        ("crew_pairings", "crew", "crew_id"),
        ("passenger_itineraries", "passenger", "pax_group_id"),
    ):
        for item in (artifact or {}).get(collection, []):
            for component, value in item.get("cost_components", {}).items():
                if value is not None:
                    items.append(
                        {
                            "entity_type": entity_type,
                            "entity_id": item.get(id_key),
                            "component": component,
                            "value": value,
                        }
                    )
    return items


def _time_range(*collections: Any) -> dict[str, str | None]:
    values: list[str] = []

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key in {
                    "sched_dep", "sched_arr", "recovered_dep", "recovered_arr",
                    "dep_time", "arr_time", "start_time", "end_time",
                } and isinstance(child, str) and _parse_time(child):
                    values.append(child)
                else:
                    visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    for collection in collections:
        visit(collection)
    ordered = sorted(values, key=lambda item: _parse_time(item) or datetime.min)
    return {"start": ordered[0] if ordered else None, "end": ordered[-1] if ordered else None, "timezone": "UTC"}


def _parse_time(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _inside(value: Any, start: datetime, end: datetime) -> bool:
    parsed = _parse_time(value)
    return parsed is not None and start <= parsed < end
