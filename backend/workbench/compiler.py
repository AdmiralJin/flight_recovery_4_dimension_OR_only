from __future__ import annotations

from copy import deepcopy
from datetime import timedelta
from typing import Any

from pydantic import ValidationError

from backend.application.solve_service import (
    ALGORITHM,
    ROOT,
    default_profile_ids,
    solve_readiness,
)
from backend.config import load_cost_config, load_passenger_itinerary_generation_config
from backend.core import generate_passenger_itineraries
from backend.schemas.columns import (
    FlightChangeType,
    FlightOperationType,
    FlightOption,
    PassengerItinerary,
    RecoveryColumns,
)
from backend.schemas.result import SolveRequest
from backend.schemas.scenario import Scenario
from backend.schemas.workbench import (
    CapacityChange,
    CapacitySemantics,
    CompilePreview,
    DisruptionRule,
    DisruptionRuleType,
    DraftDocument,
    FlightImpact,
    WorkbenchIssue,
)

from .storage import content_hash


def draft_from_case_payload(payload: dict[str, Any], name: str | None = None) -> DraftDocument:
    metadata = payload["case"]
    return DraftDocument(
        name=name or metadata["label"],
        source_case_id=metadata["case_id"],
        capacity_semantics=CapacitySemantics.EFFECTIVE_LEGACY,
        scenario=deepcopy(payload["scenario"]),
        solve_bundle=deepcopy(payload.get("solve_bundle")),
        expected=deepcopy(metadata.get("expected")),
        notes=[
            "Imported from the v1 catalog. Airport intervals are treated as already effective; legacy disruptions are not applied again."
        ],
    )


def compile_draft(document: DraftDocument) -> CompilePreview:
    draft_data = document.model_dump(mode="json")
    draft_hash = content_hash(draft_data)
    issues: list[WorkbenchIssue] = []
    try:
        baseline = Scenario.model_validate(document.scenario)
    except ValidationError as exc:
        issues.extend(_validation_issues(exc, "scenario"))
        return CompilePreview(valid=False, draft_hash=draft_hash, issues=issues)

    effective = baseline
    capacity_changes: list[CapacityChange] = []
    if document.capacity_semantics is CapacitySemantics.BASELINE_COMPILED:
        effective, capacity_changes, capacity_issues = _compile_capacity(
            baseline, document.typed_disruptions
        )
        issues.extend(capacity_issues)
    elif document.typed_disruptions:
        issues.append(
            WorkbenchIssue(
                code="legacy_capacity_rules_not_applied",
                message=(
                    "This draft treats airport intervals as already effective. "
                    "Switch to baseline_compiled semantics before applying typed rules."
                ),
                severity="error",
                path="typed_disruptions",
            )
        )

    solve_request: dict[str, Any] | None = None
    candidate_counts: dict[str, int] = {}
    bundle = deepcopy(document.solve_bundle)
    if document.candidate_policy.regenerate_flight_options:
        bundle, generation_issues = _generate_bundle(
            effective, document, bundle
        )
        issues.extend(generation_issues)
    elif bundle is not None:
        bundle["scenario"] = effective.model_dump(mode="json")
        bundle, merge_issues = _merge_manual_candidates(bundle, document)
        issues.extend(merge_issues)

    if bundle is None:
        issues.append(
            WorkbenchIssue(
                code="missing_solve_bundle",
                message=(
                    "No Solve Bundle is available. Enable candidate generation or import explicit Flight Options, capacity, costs and profiles."
                ),
                path="solve_bundle",
            )
        )
    else:
        try:
            solve_request = SolveRequest.model_validate(bundle).model_dump(mode="json")
            columns = RecoveryColumns.model_validate(solve_request["recovery_columns"])
            candidate_counts = {
                "flight_options": len(columns.flight_options),
                "passenger_itineraries": len(columns.passenger_itineraries),
                "aircraft_strings": len(columns.aircraft_strings),
                "crew_pairings": len(columns.crew_pairings),
            }
        except ValidationError as exc:
            issues.extend(_validation_issues(exc, "solve_bundle"))
            solve_request = None

    readiness = solve_readiness(solve_request) if solve_request is not None else None
    if readiness and not readiness["solve_ready"]:
        for code in [
            *readiness.get("missing_inputs", []),
            *readiness.get("invalid_profiles", []),
        ]:
            issues.append(
                WorkbenchIssue(
                    code=str(code),
                    message=f"Solve input is not ready: {code}",
                    path="solve_bundle",
                )
            )
        for warning in readiness.get("warnings", []):
            issues.append(
                WorkbenchIssue(
                    code="readiness_detail",
                    message=str(warning),
                    severity="warning",
                    path="solve_bundle",
                )
            )

    impacts = _derive_impacts(effective, document.typed_disruptions)
    valid = solve_request is not None and not any(
        issue.severity == "error" for issue in issues
    )
    compiled_hash = content_hash(solve_request) if valid else None
    return CompilePreview(
        valid=valid,
        draft_hash=draft_hash,
        compiled_hash=compiled_hash,
        issues=issues,
        effective_scenario=effective.model_dump(mode="json"),
        solve_request=solve_request if valid else None,
        capacity_changes=capacity_changes,
        flight_impacts=impacts,
        candidate_counts=candidate_counts,
        readiness=readiness,
    )


def _validation_issues(exc: ValidationError, prefix: str) -> list[WorkbenchIssue]:
    issues: list[WorkbenchIssue] = []
    for item in exc.errors(include_context=False):
        location = ".".join(str(part) for part in item.get("loc", ()))
        path = f"{prefix}.{location}" if location else prefix
        issues.append(
            WorkbenchIssue(
                code=str(item.get("type", "validation_error")),
                message=str(item.get("msg", "Invalid value")),
                path=path,
            )
        )
    return issues


def _overlaps(start_a, end_a, start_b, end_b) -> bool:
    return start_a < end_b and start_b < end_a


def _compile_capacity(
    scenario: Scenario, rules: list[DisruptionRule]
) -> tuple[Scenario, list[CapacityChange], list[WorkbenchIssue]]:
    enabled = [rule for rule in rules if rule.enabled]
    issues: list[WorkbenchIssue] = []
    changes: list[CapacityChange] = []
    intervals: list[dict[str, Any]] = []
    covered_rules: set[str] = set()

    for index, interval in enumerate(scenario.airport_intervals):
        matching = [
            rule
            for rule in enabled
            if rule.airport_id == interval.airport
            and _overlaps(
                interval.start_time,
                interval.end_time,
                rule.start_time,
                rule.end_time,
            )
        ]
        boundaries = {interval.start_time, interval.end_time}
        for rule in matching:
            boundaries.add(max(interval.start_time, rule.start_time))
            boundaries.add(min(interval.end_time, rule.end_time))
        ordered = sorted(boundaries)
        for segment_index in range(len(ordered) - 1):
            start, end = ordered[segment_index], ordered[segment_index + 1]
            active = [
                rule
                for rule in matching
                if rule.start_time <= start and end <= rule.end_time
            ]
            covered_rules.update(rule.rule_id for rule in active)
            arr = interval.arr_capacity
            dep = interval.dep_capacity
            closure = any(
                rule.rule_type
                in {DisruptionRuleType.AIRPORT_CLOSURE, DisruptionRuleType.CURFEW}
                for rule in active
            )
            if closure:
                arr = 0
                dep = 0
            else:
                for rule in active:
                    delta = int(rule.capacity_delta or 0)
                    if rule.rule_type in {
                        DisruptionRuleType.ARRIVAL_CAPACITY_DELTA,
                        DisruptionRuleType.BOTH_CAPACITY_DELTA,
                    }:
                        arr += delta
                    if rule.rule_type in {
                        DisruptionRuleType.DEPARTURE_CAPACITY_DELTA,
                        DisruptionRuleType.BOTH_CAPACITY_DELTA,
                    }:
                        dep += delta
            if arr < 0 or dep < 0:
                issues.append(
                    WorkbenchIssue(
                        code="capacity_clamped_to_zero",
                        message=(
                            f"Capacity at {interval.airport} {start.isoformat()}–{end.isoformat()} was below zero and was clamped."
                        ),
                        severity="warning",
                        path=f"scenario.airport_intervals[{index}]",
                        entity_id=interval.airport,
                    )
                )
            arr = max(0, arr)
            dep = max(0, dep)
            item = interval.model_dump(mode="json")
            item.update(
                {
                    "start_time": start.isoformat(),
                    "end_time": end.isoformat(),
                    "arr_capacity": arr,
                    "dep_capacity": dep,
                }
            )
            intervals.append(item)
            if active or arr != interval.arr_capacity or dep != interval.dep_capacity:
                changes.append(
                    CapacityChange(
                        airport_id=interval.airport,
                        start_time=start,
                        end_time=end,
                        baseline_arrival=interval.arr_capacity,
                        effective_arrival=arr,
                        baseline_departure=interval.dep_capacity,
                        effective_departure=dep,
                        applied_rule_ids=[rule.rule_id for rule in active],
                    )
                )

    for rule in enabled:
        if rule.rule_id not in covered_rules:
            issues.append(
                WorkbenchIssue(
                    code="disruption_rule_uncovered",
                    message=(
                        f"Rule {rule.rule_id} does not overlap any baseline AirportInterval at {rule.airport_id}."
                    ),
                    severity="warning",
                    path="typed_disruptions",
                    entity_id=rule.rule_id,
                )
            )
    effective_data = scenario.model_dump(mode="json")
    effective_data["airport_intervals"] = intervals
    return Scenario.model_validate(effective_data), changes, issues


def _generate_bundle(
    scenario: Scenario,
    document: DraftDocument,
    source_bundle: dict[str, Any] | None,
) -> tuple[dict[str, Any] | None, list[WorkbenchIssue]]:
    policy = document.candidate_policy
    issues: list[WorkbenchIssue] = []
    options: list[FlightOption] = []
    for flight in scenario.flights:
        if policy.include_unchanged:
            options.append(
                FlightOption(
                    option_id=f"V2_{flight.flight_id}_ORIG",
                    base_flight_id=flight.flight_id,
                    operation_type=FlightOperationType.OPERATE,
                    change_types=[FlightChangeType.UNCHANGED],
                    origin=flight.origin,
                    destination=flight.destination,
                    dep_time=flight.sched_dep,
                    arr_time=flight.sched_arr,
                    block_minutes=flight.duration,
                    departure_delay_minutes=0,
                    arrival_delay_minutes=0,
                    notes="Generated unchanged option.",
                )
            )
        if policy.include_cancel:
            options.append(
                FlightOption(
                    option_id=f"V2_{flight.flight_id}_CANCEL",
                    base_flight_id=flight.flight_id,
                    operation_type=FlightOperationType.CANCEL,
                    change_types=[FlightChangeType.CANCEL],
                    origin=None,
                    destination=None,
                    dep_time=None,
                    arr_time=None,
                    block_minutes=None,
                    departure_delay_minutes=None,
                    arrival_delay_minutes=None,
                    notes="Generated cancellation option.",
                )
            )
        maximum = min(flight.max_delay, policy.maximum_delay_minutes)
        for delay in range(policy.delay_step_minutes, maximum + 1, policy.delay_step_minutes):
            options.append(
                FlightOption(
                    option_id=f"V2_{flight.flight_id}_D{delay}",
                    base_flight_id=flight.flight_id,
                    operation_type=FlightOperationType.OPERATE,
                    change_types=[FlightChangeType.DELAY],
                    origin=flight.origin,
                    destination=flight.destination,
                    dep_time=flight.sched_dep + timedelta(minutes=delay),
                    arr_time=flight.sched_arr + timedelta(minutes=delay),
                    block_minutes=flight.duration,
                    departure_delay_minutes=delay,
                    arrival_delay_minutes=delay,
                    notes="Generated delay option.",
                )
            )

    manual_options, manual_issues = _validate_unique_models(
        document.manual_flight_options, FlightOption, "manual_flight_options", "option_id"
    )
    issues.extend(manual_issues)
    generated_ids = {option.option_id for option in options}
    for option in manual_options:
        if option.option_id in generated_ids:
            issues.append(
                WorkbenchIssue(
                    code="duplicate_flight_option",
                    message=f"Manual option {option.option_id} duplicates a generated option.",
                    path="manual_flight_options",
                    entity_id=option.option_id,
                )
            )
        else:
            options.append(option)
            generated_ids.add(option.option_id)

    capacity_by_option: dict[str, int] = {}
    for option in options:
        if option.operation_type is not FlightOperationType.OPERATE:
            continue
        assert option.base_flight_id is not None
        if option.base_flight_id not in policy.residual_capacity_by_flight_id:
            if scenario.passengers:
                issues.append(
                    WorkbenchIssue(
                        code="missing_residual_capacity",
                        message=(
                            f"Residual passenger capacity is required for flight {option.base_flight_id}."
                        ),
                        path="candidate_policy.residual_capacity_by_flight_id",
                        entity_id=option.base_flight_id,
                    )
                )
            continue
        capacity_by_option[option.option_id] = policy.residual_capacity_by_flight_id[
            option.base_flight_id
        ]

    if any(issue.severity == "error" for issue in issues):
        return None, issues

    itinerary_config = load_passenger_itinerary_generation_config(
        ROOT / "data/config/phase7_test_itinerary_generation_v1.json"
    )
    itineraries = list(
        generate_passenger_itineraries(scenario, options, None, itinerary_config)
    )
    manual_itineraries, itinerary_issues = _validate_unique_models(
        document.manual_passenger_itineraries,
        PassengerItinerary,
        "manual_passenger_itineraries",
        "itinerary_id",
    )
    issues.extend(itinerary_issues)
    itinerary_ids = {item.itinerary_id for item in itineraries}
    for item in manual_itineraries:
        if item.itinerary_id in itinerary_ids:
            issues.append(
                WorkbenchIssue(
                    code="duplicate_passenger_itinerary",
                    message=f"Manual itinerary {item.itinerary_id} duplicates a generated itinerary.",
                    path="manual_passenger_itineraries",
                    entity_id=item.itinerary_id,
                )
            )
        else:
            itineraries.append(item)
            itinerary_ids.add(item.itinerary_id)

    columns = RecoveryColumns(
        schema_version="1.0.0",
        scenario_id=scenario.scenario_id,
        time_unit="minute",
        notes=["Generated by AIR Workbench v2 candidate compiler."],
        flight_options=options,
        aircraft_strings=[],
        crew_pairings=[],
        passenger_itineraries=itineraries,
    )
    baseline_cost = load_cost_config(ROOT / "data/costs/phase2_test_costs_v1.json")
    source = source_bundle or {}
    request = SolveRequest(
        schema_version="1.0.0",
        scenario=scenario.model_dump(mode="json"),
        recovery_columns=columns.model_dump(mode="json"),
        capacity_profile={
            "schema_version": "1.0.0",
            "capacity_profile_id": f"v2_{scenario.scenario_id}_residual_capacity",
            "scenario_id": scenario.scenario_id,
            "source": "implementation_assumption",
            "units": "seats",
            "seat_capacity_by_option_id": capacity_by_option,
            "notes": ["Explicit residual capacity supplied by the draft author."],
        },
        cost_profile_id=source.get("cost_profile_id", baseline_cost.cost_profile_id),
        cost_overrides=source.get("cost_overrides", {}),
        algorithm=ALGORITHM,
        profile_ids=source.get("profile_ids", default_profile_ids().model_dump()),
    )
    return request.model_dump(mode="json"), issues


def _validate_unique_models(raw_items, model, path: str, identifier: str):
    values = []
    issues: list[WorkbenchIssue] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_items):
        try:
            item = model.model_validate(raw)
        except ValidationError as exc:
            issues.extend(_validation_issues(exc, f"{path}[{index}]"))
            continue
        item_id = getattr(item, identifier)
        if item_id in seen:
            issues.append(
                WorkbenchIssue(
                    code=f"duplicate_{identifier}",
                    message=f"Duplicate {identifier}: {item_id}",
                    path=f"{path}[{index}]",
                    entity_id=item_id,
                )
            )
            continue
        seen.add(item_id)
        values.append(item)
    return values, issues


def _merge_manual_candidates(
    bundle: dict[str, Any], document: DraftDocument
) -> tuple[dict[str, Any], list[WorkbenchIssue]]:
    issues: list[WorkbenchIssue] = []
    columns_data = deepcopy(bundle.get("recovery_columns") or {})
    options = list(columns_data.get("flight_options") or [])
    option_ids = {item.get("option_id") for item in options}
    for index, raw in enumerate(document.manual_flight_options):
        try:
            option = FlightOption.model_validate(raw)
        except ValidationError as exc:
            issues.extend(_validation_issues(exc, f"manual_flight_options[{index}]"))
            continue
        if option.option_id in option_ids:
            issues.append(
                WorkbenchIssue(
                    code="duplicate_flight_option",
                    message=f"Manual option {option.option_id} already exists in the bundle.",
                    path=f"manual_flight_options[{index}]",
                    entity_id=option.option_id,
                )
            )
            continue
        options.append(option.model_dump(mode="json"))
        option_ids.add(option.option_id)
    columns_data["flight_options"] = options

    itineraries = list(columns_data.get("passenger_itineraries") or [])
    itinerary_ids = {item.get("itinerary_id") for item in itineraries}
    for index, raw in enumerate(document.manual_passenger_itineraries):
        try:
            itinerary = PassengerItinerary.model_validate(raw)
        except ValidationError as exc:
            issues.extend(
                _validation_issues(exc, f"manual_passenger_itineraries[{index}]")
            )
            continue
        if itinerary.itinerary_id in itinerary_ids:
            issues.append(
                WorkbenchIssue(
                    code="duplicate_passenger_itinerary",
                    message=(
                        f"Manual itinerary {itinerary.itinerary_id} already exists in the bundle."
                    ),
                    path=f"manual_passenger_itineraries[{index}]",
                    entity_id=itinerary.itinerary_id,
                )
            )
            continue
        itineraries.append(itinerary.model_dump(mode="json"))
        itinerary_ids.add(itinerary.itinerary_id)
    columns_data["passenger_itineraries"] = itineraries
    columns_data["aircraft_strings"] = []
    columns_data["crew_pairings"] = []
    bundle["recovery_columns"] = columns_data
    return bundle, issues


def _legacy_disruption_type(value: str) -> str:
    lowered = value.lower()
    if any(token in lowered for token in ("closure", "closed", "shutdown", "curfew")):
        return "both"
    if any(token in lowered for token in ("departure", "depart", "dep_")):
        return "departure"
    if any(token in lowered for token in ("arrival", "arrive", "arr_")):
        return "arrival"
    return "unknown"


def _derive_impacts(
    scenario: Scenario, rules: list[DisruptionRule]
) -> list[FlightImpact]:
    impacts: dict[str, dict[str, Any]] = {
        flight.flight_id: {"direct": [], "sources": []}
        for flight in scenario.flights
    }
    if rules:
        for rule in rules:
            if not rule.enabled:
                continue
            applies_departure = rule.rule_type in {
                DisruptionRuleType.DEPARTURE_CAPACITY_DELTA,
                DisruptionRuleType.BOTH_CAPACITY_DELTA,
                DisruptionRuleType.AIRPORT_CLOSURE,
                DisruptionRuleType.CURFEW,
            }
            applies_arrival = rule.rule_type in {
                DisruptionRuleType.ARRIVAL_CAPACITY_DELTA,
                DisruptionRuleType.BOTH_CAPACITY_DELTA,
                DisruptionRuleType.AIRPORT_CLOSURE,
                DisruptionRuleType.CURFEW,
            }
            for flight in scenario.flights:
                direct = (
                    applies_departure
                    and flight.origin == rule.airport_id
                    and rule.start_time <= flight.sched_dep < rule.end_time
                ) or (
                    applies_arrival
                    and flight.destination == rule.airport_id
                    and rule.start_time <= flight.sched_arr < rule.end_time
                )
                if direct:
                    impacts[flight.flight_id]["direct"].append(rule.rule_id)
    else:
        for index, disruption in enumerate(scenario.disruptions):
            kind = _legacy_disruption_type(disruption.restriction_type)
            if kind == "unknown":
                continue
            for flight in scenario.flights:
                direct = (
                    kind in {"both", "departure"}
                    and flight.origin == disruption.airport
                    and disruption.start_time <= flight.sched_dep < disruption.end_time
                ) or (
                    kind in {"both", "arrival"}
                    and flight.destination == disruption.airport
                    and disruption.start_time <= flight.sched_arr < disruption.end_time
                )
                if direct:
                    impacts[flight.flight_id]["direct"].append(f"legacy-{index}")

    def propagate(sequence: list[str], resource_type: str, resource_id: str) -> None:
        sources: list[str] = []
        for flight_id in sequence:
            impact = impacts.get(flight_id)
            if impact is None:
                continue
            if impact["direct"]:
                sources.append(flight_id)
                continue
            for source_id in sources:
                impact["sources"].append(
                    {
                        "type": resource_type,
                        "resource_id": resource_id,
                        "source_flight_id": source_id,
                    }
                )

    for aircraft in scenario.aircraft:
        propagate(aircraft.original_rotation, "aircraft", aircraft.tail_id)
    for crew in scenario.crew:
        propagate(crew.original_pairing, "crew", crew.crew_id)

    result: list[FlightImpact] = []
    for flight in scenario.flights:
        impact = impacts[flight.flight_id]
        status = "direct" if impact["direct"] else "downstream" if impact["sources"] else "normal"
        result.append(
            FlightImpact(
                flight_id=flight.flight_id,
                status=status,
                direct_rule_ids=impact["direct"],
                propagation_sources=impact["sources"],
            )
        )
    return result
