"""Aircraft-only public model for the four existing XMA algorithm drivers.

The drivers, Benders cuts and branch/pricing implementation are reused. The
business model builder is replaced explicitly because competition passenger
rules and aggregate fleet terminals do not define the frozen AIR subproblem.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from time import perf_counter
import math

import gurobipy as gp
from gurobipy import GRB

from backend.business.xma.schema import XmaSolveRequest, XmaDataset, Option
from backend.business.xma.model import JointModel, new_model, add_path
from backend.business.xma.objectives import assignment_cost, schedule_cost
from backend.business.xma.solver import EXPLICIT_BACKEND
from backend.core.string_generator import make_generated_aircraft_string
from backend.schemas.columns import FlightOperationType
from backend.solver.runtime import check_budget

from .audit import legal_leg, audit, EnumerationLimit
from .common import clean
from .model import PublicSolveRequest


def bridge(public, seconds):
    if public.model_type != "aircraft":
        raise ValueError("XMA cross-comparison only supports the common aircraft submodel")
    scenario = public.scenario
    seats_by_tail = {}
    for a in scenario.aircraft:
        f = next(f for f in scenario.flights if f.original_aircraft == a.tail_id)
        o = next(o for o in public.recovery_columns.flight_options if o.base_flight_id == f.flight_id and o.operation_type == FlightOperationType.OPERATE)
        seats_by_tail[a.tail_id] = public.capacity_profile.seat_capacity_by_option_id[o.option_id]
    data = XmaDataset(dataset_id=public.instance_id, source_sha256=public.problem_sha256,
        adjustment_start=scenario.recovery_window.start_time, adjustment_end=scenario.recovery_window.end_time,
        flights=[dict(flight_id=f.flight_id, date=f.sched_dep.date().isoformat(), flight_no=f.flight_id,
                      domestic=True, origin=f.origin, destination=f.destination, sched_dep=f.sched_dep, sched_arr=f.sched_arr,
                      original_aircraft=f.original_aircraft, equipment=f.original_equipment,
                      passengers=0, through_passengers=0, seats=seats_by_tail[f.original_aircraft], importance=1,
                      source=dict(sheet="public_normalized_records", row=i+2)) for i, f in enumerate(scenario.flights)],
        aircraft=[dict(tail_id=a.tail_id, equipment=a.equipment_type, seats=seats_by_tail[a.tail_id],
                       initial_station=a.initial_station_at_t, original_terminal=a.required_station_at_T_end,
                       original_rotation=a.original_rotation) for a in scenario.aircraft],
        airports={a.airport_id: True for a in scenario.airports}, route_prohibitions=[], closures=[], scenes=[],
        travel_minutes={}, transfers=[], connected_pairs=[], original_turn_minutes={}, movement_windows=[],
        public_rules=public.model_dump(mode="json"),
        notes=["Aircraft-only optimization. Original passenger observations are retained in public_rules.source."])
    coeff = public.costs.coefficients
    request = XmaSolveRequest(dataset=data, objective_profile="air_linear_v1",
        air_objective=dict(flight_delay_per_minute=coeff.flight_delay_per_minute.value,
                           flight_cancellation=coeff.flight_cancellation.value,
                           aircraft_reassignment=coeff.aircraft_reassignment.value),
        algorithm=public.algorithm.removeprefix("xma_"), time_limit_seconds=seconds,
        maximum_delay_minutes=public.candidate_policy["max_delay_minutes"],
        delay_step_minutes=public.candidate_policy["step_minutes"])
    opts = [Option(option_id=o.option_id, flight_id=o.base_flight_id,
                   cancelled=o.operation_type == FlightOperationType.CANCEL,
                   dep=o.dep_time or next(f.sched_dep for f in scenario.flights if f.flight_id == o.base_flight_id),
                   arr=o.arr_time or next(f.sched_arr for f in scenario.flights if f.flight_id == o.base_flight_id),
                   delay=o.departure_delay_minutes or 0) for o in public.recovery_columns.flight_options]
    return request, opts


def build_public_joint(request, options, *, representation, schedule, relax, branch_bounds, enumerate_all):
    public = PublicSolveRequest.model_validate(request.dataset.public_rules)
    if schedule is not None:
        options = [o for o in options if o.option_id in schedule]
    model, env = new_model("public_xma_"+representation)
    ints = []
    def variable(name):
        v = model.addVar(lb=0, ub=1, vtype=GRB.CONTINUOUS if relax else GRB.BINARY, name=name)
        ints.append(v)
        return v
    x = {o.option_id: variable("x:"+o.option_id) for o in options}
    for f in public.scenario.flights:
        model.addConstr(gp.quicksum(x[o.option_id] for o in options if o.flight_id == f.flight_id) == 1,
                        name="flight:"+f.flight_id)
        if f.strategic_flag:
            model.addConstr(gp.quicksum(x[o.option_id] for o in options if o.flight_id == f.flight_id and not o.cancelled) == 1,
                            name="fixed_operate:"+f.flight_id)
    if schedule is not None:
        for v in x.values():
            v.LB = 1
    base = {f.flight_id: f for f in public.scenario.flights}
    air_opts = {o.option_id: o for o in public.recovery_columns.flight_options}
    opt_by_id = {o.option_id: o for o in options}
    u, networks = {}, {}
    objective = gp.quicksum(schedule_cost(request, f, o)*x[o.option_id]
        for o in options for f in request.dataset.flights if f.flight_id == o.flight_id)
    for a in public.scenario.aircraft:
        check_budget()
        legal = {o.option_id: o for o in options if not o.cancelled
                 and legal_leg(public.scenario, a, base[o.flight_id], air_opts[o.option_id])}
        ordered = sorted(legal, key=lambda oid: (legal[oid].dep, oid))
        turn = public.configs["flight_string_generation"]["equipment_overrides"][a.equipment_type]
        edges = {oid: [nid for nid in ordered if legal[nid].flight_id != legal[oid].flight_id
                      and base[legal[oid].flight_id].destination == base[legal[nid].flight_id].origin
                      and legal[nid].dep >= legal[oid].arr+timedelta(minutes=turn)] for oid in ordered}
        starts = [oid for oid in ordered if base[legal[oid].flight_id].origin == a.initial_station_at_t]
        networks[a.tail_id] = dict(options=legal, ordered=ordered, starts=starts, edges=edges)
        for oid in ordered:
            u[a.tail_id, oid] = variable("u:"+a.tail_id+":"+oid)
            f = next(f for f in request.dataset.flights if f.flight_id == legal[oid].flight_id)
            objective += assignment_cost(request, f, a.tail_id)*u[a.tail_id, oid]
    for o in options:
        if not o.cancelled:
            model.addConstr(gp.quicksum(v for (tail, oid), v in u.items() if oid == o.option_id) == x[o.option_id],
                            name="coverage:"+o.option_id)
    rows = {}
    for a in public.scenario.aircraft:
        tail = a.tail_id
        net = networks[tail]
        if representation == "arc":
            incoming, outgoing, terminal = defaultdict(list), defaultdict(list), defaultdict(list)
            idle = variable("idle:"+tail)
            terminal[a.initial_station_at_t].append(idle)
            starts = []
            for oid in net["ordered"]:
                if oid in net["starts"]:
                    v = variable("start:"+tail+":"+oid)
                    starts.append(v)
                    incoming[oid].append(v)
                v = variable("end:"+tail+":"+oid)
                outgoing[oid].append(v)
                terminal[base[net["options"][oid].flight_id].destination].append(v)
                for nid in net["edges"][oid]:
                    v = variable("arc:"+tail+":"+oid+":"+nid)
                    outgoing[oid].append(v)
                    incoming[nid].append(v)
            model.addConstr(gp.quicksum(starts)+idle == 1, name="start:"+tail)
            for oid in net["ordered"]:
                model.addConstr(gp.quicksum(incoming[oid]) == u[tail, oid], name="in:"+tail+":"+oid)
                model.addConstr(gp.quicksum(outgoing[oid]) == u[tail, oid], name="out:"+tail+":"+oid)
            for station in {a.initial_station_at_t, a.required_station_at_T_end} | set(terminal):
                model.addConstr(gp.quicksum(terminal[station]) == int(station == a.required_station_at_T_end),
                                name="terminal:"+tail+":"+station)
        else:
            rows["select", tail] = model.addConstr(gp.LinExpr() == 1, name="select:"+tail)
            for oid in net["ordered"]:
                rows["u", tail, oid] = model.addConstr(-u[tail, oid] == 0, name="path_link:"+tail+":"+oid)
            for station in request.dataset.airports:
                rows["terminal", tail, station] = model.addConstr(gp.LinExpr() == int(station == a.required_station_at_T_end),
                                                                 name="terminal:"+tail+":"+station)
    model.setObjective(objective, GRB.MINIMIZE)
    joint = JointModel(model, request, options, networks, x, u, {}, {}, {}, ints, rows,
                       objective=objective, environment=env)
    if representation != "arc" and enumerate_all:
        if len(base) > 12:
            joint.close()
            raise EnumerationLimit("XMA path Oracle restricted to 12 public flights")
        from backend.business.xma.rules import enumerate_paths
        count = 0
        for tail, net in networks.items():
            paths = [(), *enumerate_paths(net, request.oracle_path_limit-count)]
            count += len(paths)
            if count > request.oracle_path_limit:
                joint.close()
                raise EnumerationLimit("XMA full path enumeration limit")
            for path in paths:
                add_path(joint, tail, path, integer=not relax)
    model.update()
    for name, (lb, ub) in (branch_bounds or {}).items():
        v = model.getVarByName(name)
        if v is None:
            joint.close()
            raise ValueError("unknown public XMA branch variable "+name)
        v.LB, v.UB = max(v.LB, lb), min(v.UB, ub)
    return joint


def _decisions(public, decisions):
    base = {f.flight_id: f for f in public.scenario.flights}
    selected = dict(flight_options=[d.option_id for d in decisions], aircraft_strings=[],
                    crew_pairings=[], passenger_itineraries=[])
    paths = []
    for a in public.scenario.aircraft:
        rotation = sorted((d for d in decisions if not d.cancelled and d.aircraft_id == a.tail_id), key=lambda d: d.dep)
        path = make_generated_aircraft_string(a, [d.option_id for d in rotation])
        paths.append(path)
        selected["aircraft_strings"].append(path.string_id)
    columns = public.recovery_columns.model_copy(update={"aircraft_strings": paths})
    c = public.costs.coefficients
    objective = sum(c.flight_cancellation.value if d.cancelled else (
        c.flight_delay_per_minute.value*(d.dep-base[d.flight_id].sched_dep).total_seconds()/60
        + c.aircraft_reassignment.value*(d.aircraft_id != base[d.flight_id].original_aircraft)) for d in decisions)
    primal = audit(public, columns, selected, objective)
    return selected, columns, objective, primal


def evaluate_public(request, decisions):
    public = PublicSolveRequest.model_validate(request.dataset.public_rules)
    try:
        _, _, objective, primal = _decisions(public, decisions)
    except (ValueError, KeyError, TypeError) as exc:
        return dict(valid=False, violations=[str(exc)], objective=None)
    return dict(valid=primal["pass"], violations=primal["violations"], objective=objective,
                score=objective, raw_score=objective, penalty=0)


def execute_xma(public, *, seconds, cancel_check, event_sink, checkpoint_sink=None):
    from backend.business.xma.algorithms import Budget, direct, benders
    started = perf_counter()
    request, options = bridge(public, seconds)
    budget = Budget(seconds, event_sink, cancel_check)
    if checkpoint_sink:
        def checkpoint(outcome):
            selected, columns, objective, primal = _decisions(public, outcome.decisions)
            if primal["pass"]:
                checkpoint_sink(clean(dict(status="not_converged", problem_sha256=public.problem_sha256,
                    objective=objective, lower_bound=outcome.lower, upper_bound=objective, audit=primal,
                    selected=selected, columns=columns)))
        budget.incumbent_sink = checkpoint
    token = EXPLICIT_BACKEND.set(public.backend)
    try:
        outcome = (direct(request, options, budget, oracle=public.algorithm.endswith("path_oracle"))
                   if request.algorithm in ("joint_arc_flow", "joint_path_oracle") else
                   benders(request, options, budget, use_cg=request.algorithm == "benders_cg_bp", strengthen_master=True))
    finally:
        EXPLICIT_BACKEND.reset(token)
    selected, columns, objective, primal = _decisions(public, outcome.decisions) if outcome.decisions else (None, None, None, None)
    if objective is not None and abs(objective-outcome.objective) > 1e-5:
        raise RuntimeError("XMA public independent objective mismatch")
    certified = bool(primal and primal["pass"] and outcome.status == "optimal" and outcome.lower is not None
                     and outcome.upper is not None and abs(outcome.lower-outcome.upper) <= 1e-5)
    if outcome.status == "optimal" and not certified:
        raise RuntimeError("XMA public optimal label rejected by audit/bound closure")
    return clean(dict(status=outcome.status, algorithm=public.algorithm, backend=public.backend,
        problem_sha256=public.problem_sha256, objective=outcome.objective,
        lower_bound=outcome.lower, upper_bound=outcome.upper,
        gap=max(0, outcome.upper-outcome.lower) if outcome.upper is not None and outcome.lower is not None else None,
        audit=primal, selected=selected, solution_columns=columns, core=outcome,
        certified_optimal=certified, runtime_seconds=perf_counter()-started,
        original_rules=dict(eligible=False, historical_gap=None),
        certificate_scope="frozen_common_aircraft_model; XMA algorithm drivers with explicit public model builder"))
