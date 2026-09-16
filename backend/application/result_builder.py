from __future__ import annotations

import math
from collections import Counter

from backend.config import (
    FixedColumnCostConfig,
    PassengerCapacityProfile,
    aircraft_string_cost,
    crew_pairing_cost,
    passenger_itinerary_cost,
    schedule_flight_option_cost,
)
from backend.core.benders_branch_and_price import BendersBranchAndPriceResult
from backend.schemas.columns import (
    CrewSegmentType,
    FlightOperationType,
    PassengerItineraryStatus,
    PassengerSegmentType,
    RecoveryColumns,
)
from backend.schemas.expected import (
    PassengerOutcome,
    RecoveryAction,
    RecoveryActionType,
    RecoveryEntityType,
    RecoveryMetrics,
    ResolvedFlight,
    ResolvedFlightStatus,
)
from backend.schemas.result import (
    AircraftOutcome,
    CrewOutcome,
    CrewOutcomeSegment,
    FlightRecovery,
    OriginalFlight,
    PassengerRecovery,
    RecoveredMetrics,
    RecoveredObjective,
    RecoveredResult,
    RecoveredStatus,
    RunMetadata,
    SelectedDecisions,
    SolveDiagnostics,
)
from backend.schemas.scenario import Scenario


class ResultBuildError(ValueError):
    """Core selections cannot be transformed into a consistent business result."""


def _selected_map(
    ids: tuple[str, ...], lookup: dict, owners: set[str], owner_attr: str
) -> dict:
    selected: dict = {}
    for item_id in ids:
        item = lookup.get(item_id)
        if item is None:
            raise ResultBuildError(f"selected ID {item_id!r} has no generated column")
        owner = getattr(item, owner_attr)
        if owner in selected:
            raise ResultBuildError(f"duplicate selected owner {owner!r}")
        selected[owner] = item
    if set(selected) != owners:
        raise ResultBuildError(
            f"selection ownership mismatch: missing={sorted(owners-set(selected))}"
        )
    return selected


def build_recovered_result(
    scenario: Scenario,
    formal_columns: RecoveryColumns,
    core: BendersBranchAndPriceResult,
    costs: FixedColumnCostConfig,
    capacity: PassengerCapacityProfile,
    metadata: RunMetadata,
) -> RecoveredResult:
    """Independently recheck selections, assignments, costs and metrics."""

    raw_metrics = core.diagnostics.get("metrics", {})
    phase11_metrics = core.diagnostics.get("phase11_metrics", {})
    if not phase11_metrics:
        phase11_diagnostics = core.diagnostics.get("phase11_diagnostics", {})
        if hasattr(phase11_diagnostics, "get"):
            phase11_metrics = phase11_diagnostics.get("metrics", {})
    if not isinstance(raw_metrics, dict):
        raw_metrics = dict(raw_metrics)
    if not isinstance(phase11_metrics, dict):
        phase11_metrics = dict(phase11_metrics)
    lower = core.lower_bound
    upper = core.upper_bound
    integrated_audit = core.diagnostics.get("integrated_audit")
    if integrated_audit is None:
        nested = core.diagnostics.get("phase11_diagnostics", {})
        if isinstance(nested, dict):
            integrated_audit = nested.get("integrated_audit")
        elif hasattr(nested, "get"):
            integrated_audit = nested.get("integrated_audit")
    diagnostics = SolveDiagnostics(
        algorithm=metadata.algorithm,
        runtime_seconds=metadata.runtime_seconds,
        objective=core.objective_value,
        lower_bound=lower,
        upper_bound=upper,
        gap=(
            max(0.0, upper - lower) if upper is not None and lower is not None else None
        ),
        benders_master_iterations=int(raw_metrics.get("benders_master_iterations", 0)),
        visited_schedules=int(raw_metrics.get("visited_schedules", 0)),
        lp_cuts=int(raw_metrics.get("lp_lower_bound_cuts", 0)),
        exact_integer_cuts=int(raw_metrics.get("exact_integer_cuts", 0)),
        feasibility_cuts=int(raw_metrics.get("feasibility_cuts", 0)),
        aircraft_cg_calls=int(phase11_metrics.get("aircraft_cg_calls", 0)),
        aircraft_generated_columns=int(
            phase11_metrics.get("aircraft_generated_columns", 0)
        ),
        aircraft_bp_nodes=int(raw_metrics.get("aircraft_branch_and_price_nodes", 0)),
        crew_cg_calls=int(phase11_metrics.get("crew_cg_calls", 0)),
        crew_generated_pairings=int(phase11_metrics.get("crew_generated_columns", 0)),
        crew_bp_nodes=int(raw_metrics.get("crew_branch_and_price_nodes", 0)),
        passenger_itinerary_count=len(formal_columns.passenger_itineraries),
        formal_full_enumerators_used=bool(
            core.diagnostics.get("formal_full_enumerators_used", False)
        ),
        integrated_audit_pass=(
            bool(integrated_audit.get("all_constraints_satisfied"))
            if integrated_audit is not None
            else None
        ),
        terminal_reason=str(core.diagnostics.get("terminal_reason", "unknown")),
    )
    status = RecoveredStatus(core.status.value)
    empty = SelectedDecisions(
        flight_options=[],
        aircraft_strings=[],
        crew_pairings=[],
        passenger_itineraries=[],
    )
    common = dict(
        schema_version="1.0.0",
        run_id=metadata.run_id,
        scenario_id=scenario.scenario_id,
        status=status,
        algorithm=metadata.algorithm,
        diagnostics=diagnostics,
        run_metadata=metadata,
    )
    if status is not RecoveredStatus.OPTIMAL:
        return RecoveredResult(
            **common,
            objective=None,
            selected=empty,
            resolved_flights=[],
            aircraft_outcomes=[],
            crew_outcomes=[],
            passenger_outcomes=[],
            recovery_actions=[],
            metrics=None,
        )
    columns = core.solution_columns
    if columns is None or core.objective_value is None:
        raise ResultBuildError("optimal core result has no solution columns/objective")
    if diagnostics.integrated_audit_pass is not True:
        raise ResultBuildError("optimal result lacks a passing integrated audit")
    flights = {item.flight_id: item for item in scenario.flights}
    options = {item.option_id: item for item in formal_columns.flight_options}
    strings = {item.string_id: item for item in columns.aircraft_strings}
    pairings = {item.pairing_id: item for item in columns.crew_pairings}
    itineraries = {
        item.itinerary_id: item for item in formal_columns.passenger_itineraries
    }
    passengers = {item.pax_group_id: item for item in scenario.passengers}
    aircraft = {item.tail_id: item for item in scenario.aircraft}
    crew = {item.crew_id: item for item in scenario.crew}
    selected_options = _selected_map(
        core.selected_flight_options, options, set(flights), "base_flight_id"
    )
    selected_strings = _selected_map(
        core.selected_aircraft_strings, strings, set(aircraft), "aircraft_id"
    )
    selected_pairings = _selected_map(
        core.selected_crew_pairings, pairings, set(crew), "crew_id"
    )
    selected_itineraries = _selected_map(
        core.selected_passenger_itineraries,
        itineraries,
        set(passengers),
        "pax_group_id",
    )
    aircraft_cover: Counter[str] = Counter()
    aircraft_owner: dict[str, str] = {}
    crew_cover: Counter[str] = Counter()
    crew_owner: dict[str, str] = {}
    aircraft_outcomes = []
    for owner in sorted(aircraft):
        item = selected_strings[owner]
        ferry = []
        recovered = []
        for option_id in item.leg_option_ids:
            option = options.get(option_id)
            if option is None or option.operation_type is FlightOperationType.CANCEL:
                raise ResultBuildError(
                    "Aircraft String references missing/cancel option"
                )
            if option.operation_type is FlightOperationType.FERRY:
                ferry.append(option_id)
            else:
                recovered.append(option.base_flight_id)
                aircraft_cover[option_id] += 1
                aircraft_owner[option_id] = owner
        aircraft_outcomes.append(
            AircraftOutcome(
                aircraft_id=owner,
                selected_string_id=item.string_id,
                ordered_flight_option_ids=list(item.leg_option_ids),
                original_flight_ids=list(aircraft[owner].original_rotation),
                recovered_flight_ids=recovered,
                reassignment_count=aircraft_string_cost(
                    scenario, options, item, costs
                ).reassignment_count,
                ferry_legs=ferry,
                final_station=item.end_station,
            )
        )
    crew_outcomes = []
    for owner in sorted(crew):
        item = selected_pairings[owner]
        segments = []
        operated = []
        deadhead = []
        for duty in item.duties:
            for segment in duty.segments:
                segments.append(
                    CrewOutcomeSegment(
                        segment_type=segment.segment_type,
                        flight_option_id=segment.flight_option_id,
                    )
                )
                if segment.segment_type not in {
                    CrewSegmentType.OPERATE,
                    CrewSegmentType.DEADHEAD,
                }:
                    continue
                option = options.get(segment.flight_option_id or "")
                if (
                    option is None
                    or option.operation_type is not FlightOperationType.OPERATE
                ):
                    raise ResultBuildError("Crew Pairing references non-operate option")
                if segment.segment_type is CrewSegmentType.OPERATE:
                    operated.append(option.base_flight_id)
                    crew_cover[option.option_id] += 1
                    crew_owner[option.option_id] = owner
                else:
                    deadhead.append(option.base_flight_id)
        crew_outcomes.append(
            CrewOutcome(
                crew_id=owner,
                selected_pairing_id=item.pairing_id,
                original_flight_ids=list(crew[owner].original_pairing),
                segments=segments,
                operated_flights=operated,
                deadhead_flights=deadhead,
                reassignment_count=crew_pairing_cost(
                    scenario, options, item, costs
                ).crew_reassignment_count,
                final_station=item.end_station,
            )
        )
    resolved = []
    actions = []
    for flight_id in sorted(flights):
        original = flights[flight_id]
        option = selected_options[flight_id]
        if option.operation_type is FlightOperationType.CANCEL:
            if aircraft_cover[option.option_id] or crew_cover[option.option_id]:
                raise ResultBuildError("cancelled option has resource coverage")
            flight_result = ResolvedFlight(
                flight_id=flight_id,
                selected_option_id=option.option_id,
                status=ResolvedFlightStatus.CANCELLED,
                change_types=list(option.change_types),
                recovered_origin=None,
                recovered_destination=None,
                recovered_dep=None,
                recovered_arr=None,
                departure_delay_minutes=None,
                arrival_delay_minutes=None,
                aircraft_id=None,
                crew_id=None,
            )
            actions.append(
                RecoveryAction(
                    action_type=RecoveryActionType.CANCEL,
                    entity_type=RecoveryEntityType.FLIGHT,
                    entity_id=flight_id,
                    **{"from": {"option": "original"}},
                    to={"option": option.option_id},
                    reason="Selected recovery schedule",
                )
            )
        else:
            if (
                aircraft_cover[option.option_id] != 1
                or crew_cover[option.option_id] != 1
            ):
                raise ResultBuildError(
                    f"operated option {option.option_id} lacks unique resources"
                )
            flight_result = ResolvedFlight(
                flight_id=flight_id,
                selected_option_id=option.option_id,
                status=ResolvedFlightStatus.OPERATED,
                change_types=list(option.change_types),
                recovered_origin=option.origin,
                recovered_destination=option.destination,
                recovered_dep=option.dep_time,
                recovered_arr=option.arr_time,
                departure_delay_minutes=option.departure_delay_minutes,
                arrival_delay_minutes=option.arrival_delay_minutes,
                aircraft_id=aircraft_owner[option.option_id],
                crew_id=crew_owner[option.option_id],
            )
            for changed, kind in (
                (
                    (option.departure_delay_minutes or 0) > 0
                    or (option.arrival_delay_minutes or 0) > 0,
                    RecoveryActionType.DELAY,
                ),
                (option.origin != original.origin, RecoveryActionType.ORIGIN_CHANGE),
                (
                    option.destination != original.destination,
                    RecoveryActionType.DESTINATION_CHANGE,
                ),
                (
                    flight_result.aircraft_id != original.original_aircraft,
                    RecoveryActionType.AIRCRAFT_REASSIGNMENT,
                ),
                (
                    flight_result.crew_id != original.original_crew,
                    RecoveryActionType.CREW_REASSIGNMENT,
                ),
            ):
                if changed:
                    actions.append(
                        RecoveryAction(
                            action_type=kind,
                            entity_type=RecoveryEntityType.FLIGHT,
                            entity_id=flight_id,
                            **{"from": {"flight_id": flight_id}},
                            to={"option_id": option.option_id},
                            reason="Selected recovery decision",
                        )
                    )
        resolved.append(
            FlightRecovery(
                resolved=flight_result,
                original=OriginalFlight(
                    origin=original.origin,
                    destination=original.destination,
                    dep=original.sched_dep,
                    arr=original.sched_arr,
                ),
            )
        )
    selected_operated = {
        item.option_id
        for item in selected_options.values()
        if item.operation_type is FlightOperationType.OPERATE
    }
    if any(option_id not in selected_operated for option_id in aircraft_cover):
        raise ResultBuildError("Aircraft selection covers an unselected option")
    if any(option_id not in selected_operated for option_id in crew_cover):
        raise ResultBuildError("Crew selection covers an unselected option")
    passenger_outcomes = []
    reaccommodated_groups = reaccommodated_count = weighted_delay = unserved = 0
    for group_id in sorted(passengers):
        group = passengers[group_id]
        itinerary = selected_itineraries[group_id]
        path = []
        surface = False
        for segment in itinerary.segments:
            if segment.segment_type is PassengerSegmentType.SURFACE:
                surface = True
                continue
            option_id = segment.flight_option_id or ""
            if option_id not in selected_operated:
                raise ResultBuildError(
                    f"Passenger itinerary uses unselected option {option_id!r}"
                )
            path.append(options[option_id].base_flight_id)
        if itinerary.status is PassengerItineraryStatus.TRANSPORTED:
            weighted_delay += group.count * (itinerary.arrival_delay_minutes or 0)
            if surface or path != group.original_itinerary:
                reaccommodated_groups += 1
                reaccommodated_count += group.count
                actions.append(
                    RecoveryAction(
                        action_type=RecoveryActionType.PASSENGER_REACCOMMODATION,
                        entity_type=RecoveryEntityType.PASSENGER_GROUP,
                        entity_id=group_id,
                        **{"from": {"itinerary": group.original_itinerary}},
                        to={
                            "itinerary": path,
                            "selected_itinerary_id": itinerary.itinerary_id,
                        },
                        reason="Selected passenger itinerary",
                    )
                )
        else:
            unserved += group.count
            actions.append(
                RecoveryAction(
                    action_type=RecoveryActionType.PASSENGER_UNSERVED,
                    entity_type=RecoveryEntityType.PASSENGER_GROUP,
                    entity_id=group_id,
                    **{"from": {"itinerary": group.original_itinerary}},
                    to=None,
                    reason="Selected unserved itinerary",
                )
            )
        passenger_outcomes.append(
            PassengerRecovery(
                outcome=PassengerOutcome(
                    pax_group_id=group_id,
                    selected_itinerary_id=itinerary.itinerary_id,
                    status=itinerary.status,
                    arrival_time=itinerary.arrival_time,
                    arrival_delay_minutes=itinerary.arrival_delay_minutes,
                    unserved_count=(
                        group.count
                        if itinerary.status is PassengerItineraryStatus.UNSERVED
                        else 0
                    ),
                ),
                count=group.count,
                original_itinerary=list(group.original_itinerary),
                recovered_itinerary=path,
            )
        )
    operated_flights = [
        item
        for item in resolved
        if item.resolved.status is ResolvedFlightStatus.OPERATED
    ]
    delays = [item.resolved.departure_delay_minutes or 0 for item in operated_flights]
    metrics = RecoveryMetrics(
        operated_flights=len(operated_flights),
        cancelled_flights=len(resolved) - len(operated_flights),
        delayed_flights=sum(
            (item.resolved.departure_delay_minutes or 0) > 0
            or (item.resolved.arrival_delay_minutes or 0) > 0
            for item in operated_flights
        ),
        origin_changed_flights=sum(
            item.resolved.recovered_origin != flights[item.resolved.flight_id].origin
            for item in operated_flights
        ),
        destination_changed_flights=sum(
            item.resolved.recovered_destination
            != flights[item.resolved.flight_id].destination
            for item in operated_flights
        ),
        aircraft_reassignments=sum(
            item.reassignment_count for item in aircraft_outcomes
        ),
        crew_reassignments=sum(item.reassignment_count for item in crew_outcomes),
        passenger_reaccommodated_groups=reaccommodated_groups,
        passenger_reaccommodated_count=reaccommodated_count,
        total_flight_departure_delay_minutes=sum(delays),
        passenger_delay_minutes_weighted=weighted_delay,
        unserved_passengers=unserved,
    )
    objective = RecoveredObjective(
        schedule=sum(
            schedule_flight_option_cost(scenario, item, costs)
            for item in selected_options.values()
        ),
        aircraft=sum(
            aircraft_string_cost(scenario, options, item, costs).total
            for item in selected_strings.values()
        ),
        crew=sum(
            crew_pairing_cost(scenario, options, item, costs).total
            for item in selected_pairings.values()
        ),
        passenger=sum(
            passenger_itinerary_cost(passengers[owner].count, item, costs).total
            for owner, item in selected_itineraries.items()
        ),
        total=float(core.objective_value),
    )
    if not math.isclose(
        objective.total, core.objective_value, abs_tol=1e-5, rel_tol=1e-7
    ):
        raise ResultBuildError("recomputed objective differs from core")
    return RecoveredResult(
        **common,
        objective=objective,
        selected=SelectedDecisions(
            flight_options=list(core.selected_flight_options),
            aircraft_strings=list(core.selected_aircraft_strings),
            crew_pairings=list(core.selected_crew_pairings),
            passenger_itineraries=list(core.selected_passenger_itineraries),
        ),
        resolved_flights=resolved,
        aircraft_outcomes=aircraft_outcomes,
        crew_outcomes=crew_outcomes,
        passenger_outcomes=passenger_outcomes,
        recovery_actions=actions,
        metrics=RecoveredMetrics(
            recovery=metrics,
            mean_departure_delay_minutes=(sum(delays) / len(delays) if delays else 0.0),
            max_departure_delay_minutes=max(delays, default=0),
        ),
    )
