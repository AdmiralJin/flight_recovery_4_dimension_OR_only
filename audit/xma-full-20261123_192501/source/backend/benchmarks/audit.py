"""Primal audit and exhaustive paths, independent of AIR model construction."""
from __future__ import annotations

from collections import Counter
from datetime import timedelta
import math

from backend.core.string_generator import make_generated_aircraft_string
from backend.schemas.columns import FlightOperationType, PassengerItineraryStatus
from backend.solver.runtime import check_budget


class EnumerationLimit(ValueError):
    pass


def legal_leg(scenario, plane, flight, option):
    if option.operation_type != FlightOperationType.OPERATE or option.dep_time is None:
        return False
    if flight.original_equipment != plane.equipment_type:
        return False
    if flight.cancel_required or (flight.fixed_delay is not None and (
            option.departure_delay_minutes != flight.fixed_delay or plane.tail_id != flight.original_aircraft)):
        return False
    if option.dep_time < scenario.recovery_window.start_time or option.arr_time > scenario.recovery_window.end_time:
        return False
    if plane.ready_at is not None and option.dep_time < plane.ready_at:
        return False
    if plane.available_until is not None and option.arr_time > plane.available_until:
        return False
    if flight.earliest_departure is not None and option.dep_time < flight.earliest_departure:
        return False
    if any(option.dep_time < u.end and option.arr_time > u.start for u in plane.unavailable):
        return False
    return (option.origin == flight.origin and option.destination == flight.destination
            and option.arr_time-option.dep_time == timedelta(minutes=flight.duration)
            and option.dep_time-flight.sched_dep == timedelta(minutes=option.departure_delay_minutes)
            and 0 <= option.departure_delay_minutes <= flight.max_delay)


def enumerate_paths(request, max_paths=200000, max_nodes=1000000):
    scenario = request.scenario
    if len(scenario.flights) > 12:
        raise EnumerationLimit("full enumeration restricted to at most 12 adjustable flights")
    flight = {f.flight_id: f for f in scenario.flights}
    result, nodes = [], 0
    for plane in scenario.aircraft:
        options = sorted((o for o in request.recovery_columns.flight_options
                          if o.base_flight_id in flight and legal_leg(scenario, plane, flight[o.base_flight_id], o)),
                         key=lambda o: (o.dep_time, o.option_id))
        turn = request.configs["flight_string_generation"]["equipment_overrides"][plane.equipment_type]

        def visit(path, station, available, used):
            nonlocal nodes
            check_budget()
            nodes += 1
            if nodes > max_nodes:
                raise EnumerationLimit(f"enumeration exceeded {max_nodes} nodes; no completeness claim")
            if station == plane.required_station_at_T_end:
                result.append(make_generated_aircraft_string(plane, [o.option_id for o in path]))
                if len(result) > max_paths:
                    raise EnumerationLimit(f"enumeration exceeded {max_paths} paths; no truncated pool accepted")
            for o in options:
                if o.base_flight_id not in used and o.origin == station and o.dep_time >= available:
                    visit(path+[o], o.destination, o.arr_time+timedelta(minutes=turn), used | {o.base_flight_id})
        visit([], plane.initial_station_at_t, max(scenario.recovery_window.start_time,
              plane.ready_at or scenario.recovery_window.start_time), set())
    return result, {"complete": True, "paths": len(result), "nodes": nodes,
                    "enumerator": "independent_station_time_DFS_v1"}


def necessary_infeasibility_certificate(request):
    """A relaxation: a tail may reuse a base flight; unreachable still proves infeasible.

    No path pool is generated. The certificate is distinguished from an algorithm
    run so trivial infeasibility checks cannot inflate solver performance claims.
    """
    base = {f.flight_id: f for f in request.scenario.flights}
    options = sorted((o for o in request.recovery_columns.flight_options if o.operation_type == FlightOperationType.OPERATE),
                     key=lambda o: (o.dep_time, o.option_id))
    for a in request.scenario.aircraft:
        if a.initial_station_at_t == a.required_station_at_T_end:
            continue
        turn = request.configs["flight_string_generation"]["equipment_overrides"][a.equipment_type]
        earliest = {a.initial_station_at_t: max(request.scenario.recovery_window.start_time,
                    a.ready_at or request.scenario.recovery_window.start_time)}
        reachable = False
        for o in options:
            if legal_leg(request.scenario, a, base[o.base_flight_id], o) and earliest.get(o.origin, o.dep_time+timedelta(days=1)) <= o.dep_time:
                earliest[o.destination] = min(earliest.get(o.destination, o.arr_time+timedelta(days=1)),
                                              o.arr_time+timedelta(minutes=turn))
                if o.destination == a.required_station_at_T_end:
                    reachable = True
                    break
        if not reachable:
            return {"type": "unreachable_required_tail_terminal_in_relaxed_temporal_network",
                    "tail": a.tail_id, "reachable_stations": list(earliest), "complete": True,
                    "algorithm_exercised": False}
    return None


def audit(request, columns, selected, reported_objective):
    scenario = request.scenario
    violations, coverage, load = [], Counter(), Counter()
    opts = {o.option_id: o for o in request.recovery_columns.flight_options}
    flights = {f.flight_id: f for f in scenario.flights}
    planes = {a.tail_id: a for a in scenario.aircraft}
    strings = {s.string_id: s for s in columns.aircraft_strings}
    journeys = {p.itinerary_id: p for p in columns.passenger_itineraries}
    groups = {p.pax_group_id: p for p in scenario.passengers}
    picked = {}
    coeff = request.costs.coefficients
    cost = {"schedule": 0., "aircraft": 0., "crew": 0., "passenger": 0.}
    for oid in selected["flight_options"]:
        o = opts.get(oid)
        if o is None or o.base_flight_id in picked:
            violations.append(f"unknown or duplicate flight decision {oid}")
            continue
        picked[o.base_flight_id] = o
        if flights[o.base_flight_id].strategic_flag and o.operation_type == FlightOperationType.CANCEL:
            violations.append(f"fixed operated flight cannot be cancelled {o.base_flight_id}")
        cost["schedule"] += coeff.flight_cancellation.value if o.operation_type == FlightOperationType.CANCEL else (
            coeff.flight_delay_per_minute.value * o.departure_delay_minutes)
    if set(picked) != set(flights):
        violations.append("flight decision coverage differs from source scenario")
    owners = set()
    for sid in selected["aircraft_strings"]:
        path = strings.get(sid)
        if path is None or path.aircraft_id in owners or path.aircraft_id not in planes:
            violations.append(f"unknown or duplicate aircraft decision {sid}")
            continue
        owners.add(path.aircraft_id)
        a = planes[path.aircraft_id]
        station, available, used = a.initial_station_at_t, max(scenario.recovery_window.start_time,
            a.ready_at or scenario.recovery_window.start_time), set()
        turn = request.configs["flight_string_generation"]["equipment_overrides"][a.equipment_type]
        for oid in path.leg_option_ids:
            o = opts.get(oid)
            if o is None or o.base_flight_id not in flights:
                violations.append(f"unknown path option {oid}")
                continue
            f = flights[o.base_flight_id]
            if not legal_leg(scenario, a, f, o) or o.origin != station or o.dep_time < available or f.flight_id in used:
                violations.append(f"resource continuity, eligibility or timing failure: {sid}/{oid}")
            coverage[oid] += 1
            used.add(f.flight_id)
            station, available = o.destination, o.arr_time+timedelta(minutes=turn)
            cost["aircraft"] += coeff.aircraft_reassignment.value * (a.tail_id != f.original_aircraft)
        if station != a.required_station_at_T_end:
            violations.append(f"terminal mismatch {a.tail_id}")
    if owners != set(planes):
        violations.append("aircraft selection coverage mismatch")
    expected = Counter({o.option_id: 1 for o in picked.values() if o.operation_type == FlightOperationType.OPERATE})
    if coverage != expected:
        violations.append("operated option coverage differs between schedule and aircraft")
    if selected.get("crew_pairings") or scenario.crew or scenario.crew_enabled:
        violations.append("public profile must have CRM disabled and no crew decisions")
    group_owners = set()
    for iid in selected["passenger_itineraries"]:
        p = journeys.get(iid)
        if p is None or p.pax_group_id in group_owners or p.pax_group_id not in groups:
            violations.append(f"unknown or duplicate passenger decision {iid}")
            continue
        group_owners.add(p.pax_group_id)
        g = groups[p.pax_group_id]
        if p.status == PassengerItineraryStatus.UNSERVED:
            cost["passenger"] += coeff.unserved_passenger.value*g.count
            continue
        station, previous = g.origin, g.original_departure
        used = set()
        mct = request.configs["itinerary_generation"]["default_mct_minutes"]
        for i, seg in enumerate(p.segments):
            o = opts.get(seg.flight_option_id)
            if o is None or o.option_id not in expected or o.origin != station or o.base_flight_id in used:
                violations.append(f"passenger path availability/continuity {iid}")
                continue
            if o.dep_time < previous + (timedelta(minutes=mct) if i else timedelta()):
                violations.append(f"passenger connection timing {iid}")
            used.add(o.base_flight_id)
            station, previous = o.destination, o.arr_time
            load[o.option_id] += g.count
        if station != g.destination or previous != p.arrival_time:
            violations.append(f"passenger final destination/time {iid}")
        actual = max(0, (previous-g.scheduled_arrival).total_seconds()/60)
        if not math.isclose(actual, p.arrival_delay_minutes, abs_tol=1e-6):
            violations.append(f"passenger delay mismatch {iid}")
        cost["passenger"] += coeff.passenger_delay_per_pax_minute.value*g.count*actual
    if group_owners != set(groups):
        violations.append("passenger group selection coverage mismatch")
    for oid, amount in load.items():
        if amount > request.capacity_profile.seat_capacity_by_option_id[oid]:
            violations.append(f"seat capacity exceeded {oid}")
    total = sum(cost.values())
    if reported_objective is None or not math.isclose(total, reported_objective, abs_tol=1e-5, rel_tol=1e-9):
        violations.append(f"objective mismatch independently computed={total}, reported={reported_objective}")
    return {"pass": not violations, "violations": violations, "objective": total, "breakdown": cost,
            "scope": "frozen_public_research_model_and_generated_candidates",
            "original_rule_check": "not_performed", "crew_enabled": False}
