"""Compact public aircraft/passenger MIP: one native solve, no path enumeration."""
from collections import defaultdict
from datetime import timedelta
import math
from time import perf_counter

from backend.core.string_generator import make_generated_aircraft_string
from backend.schemas.columns import FlightOperationType, PassengerItineraryStatus
from backend.solver import HighsAdapter, GurobiAdapter, VariableType, ConstraintSense
from backend.solver.runtime import SolveBudget, SolveStopped, check_budget, use_budget
from .audit import audit, legal_leg
from .common import clean


def execute_direct(request, *, seconds, event_sink=None, checkpoint_sink=None, cancel_check=None,
                   output_flag=False, max_variables=1000000, max_constraints=1000000):
    started = perf_counter()
    emit = event_sink or (lambda value: None)
    base = {f.flight_id: f for f in request.scenario.flights}
    options = {o.option_id: o for o in request.recovery_columns.flight_options}
    groups = {g.pax_group_id: g for g in request.scenario.passengers}
    coeff = request.costs.coefficients
    counts = dict(variables=0, constraints=0, aircraft_arcs=0)
    selected = None
    saved = None
    x, u, w, objective = {}, {}, {}, {}
    solver = (HighsAdapter if request.backend == "highs" else GurobiAdapter)(
        output_flag=output_flag, cancel_check=cancel_check)
    budget = SolveBudget(seconds, cancel_check)
    budget.reserve = 0

    def event(kind, **kw):
        emit(dict(stage="direct_mip", type=kind, message=kind,
                  elapsed_seconds=perf_counter()-started, **kw))

    def variable(name, cost=0):
        check_budget()
        if counts["variables"] >= max_variables:
            raise OverflowError("direct MIP variable limit reached; model was not truncated")
        v = solver.add_variable(name, upper_bound=1, variable_type=VariableType.BINARY)
        counts["variables"] += 1
        objective[v] = cost
        return v

    def row(values, rhs=0, sense=ConstraintSense.EQUAL):
        check_budget()
        if counts["constraints"] >= max_constraints:
            raise OverflowError("direct MIP constraint limit reached; model was not truncated")
        counts["constraints"] += 1
        solver.add_linear_constraint(values, sense, rhs, name=f"r{counts['constraints']}")

    def extract(value, reported, lb=None):
        picked = dict(flight_options=[oid for oid, v in x.items() if value(v) > .5],
                      aircraft_strings=[], crew_pairings=[],
                      passenger_itineraries=[iid for iid, v in w.items() if value(v) > .5])
        paths = []
        for a in request.scenario.aircraft:
            legs = sorted((oid for (tail, oid), v in u.items() if tail == a.tail_id and value(v) > .5),
                          key=lambda oid: (options[oid].dep_time, oid))
            path = make_generated_aircraft_string(a, legs)
            paths.append(path)
            picked["aircraft_strings"].append(path.string_id)
        columns = request.recovery_columns.model_copy(update={"aircraft_strings": paths})
        primal = audit(request, columns, picked, reported)
        return dict(status="not_converged", problem_sha256=request.problem_sha256,
                    objective=reported, lower_bound=lb, upper_bound=reported, audit=primal,
                    selected=picked, columns=columns)

    def finite(value):
        return float(value) if value is not None and math.isfinite(value) else None

    try:
        with solver, use_budget(budget):
            solver.create_model("public_compact_direct_mip")
            by_flight = defaultdict(list)
            for oid, o in options.items():
                cancel = o.operation_type == FlightOperationType.CANCEL
                x[oid] = variable("x:"+oid, coeff.flight_cancellation.value if cancel else
                                  coeff.flight_delay_per_minute.value*o.departure_delay_minutes)
                by_flight[o.base_flight_id].append(oid)
            for f in base.values():
                row({x[oid]: 1 for oid in by_flight[f.flight_id]}, 1)
                if f.strategic_flag:
                    row({x[oid]: 1 for oid in by_flight[f.flight_id]
                         if options[oid].operation_type == FlightOperationType.OPERATE}, 1)
            coverage = defaultdict(dict)
            for a in request.scenario.aircraft:
                check_budget()
                legal = sorted((oid for oid, o in options.items()
                                if legal_leg(request.scenario, a, base[o.base_flight_id], o)),
                               key=lambda oid: (options[oid].dep_time, oid))
                turn = timedelta(minutes=request.configs["flight_string_generation"]["equipment_overrides"][a.equipment_type])
                incoming, outgoing, terminal = defaultdict(dict), defaultdict(dict), defaultdict(dict)
                idle = variable("idle:"+a.tail_id)
                start = {idle: 1}
                terminal[a.initial_station_at_t][idle] = 1
                for oid in legal:
                    o = options[oid]
                    v = variable("u:"+a.tail_id+":"+oid,
                                 coeff.aircraft_reassignment.value*(a.tail_id != base[o.base_flight_id].original_aircraft))
                    u[a.tail_id, oid] = v
                    coverage[oid][v] = 1
                    if o.origin == a.initial_station_at_t:
                        v = variable("start:"+a.tail_id+":"+oid)
                        start[v] = incoming[oid][v] = 1
                    v = variable("end:"+a.tail_id+":"+oid)
                    outgoing[oid][v] = terminal[o.destination][v] = 1
                by_origin = defaultdict(list)
                for oid in legal:
                    by_origin[options[oid].origin].append(oid)
                for oid in legal:
                    left = options[oid]
                    for nid in by_origin[left.destination]:
                        check_budget()
                        right = options[nid]
                        if left.base_flight_id != right.base_flight_id and right.dep_time >= left.arr_time+turn:
                            v = variable("arc:"+a.tail_id+":"+oid+":"+nid)
                            outgoing[oid][v] = incoming[nid][v] = 1
                            counts["aircraft_arcs"] += 1
                row(start, 1)
                for oid in legal:
                    row({**incoming[oid], u[a.tail_id, oid]: -1})
                    row({**outgoing[oid], u[a.tail_id, oid]: -1})
                for station in set(terminal) | {a.required_station_at_T_end}:
                    row(terminal[station], int(station == a.required_station_at_T_end))
            for oid, o in options.items():
                if o.operation_type == FlightOperationType.OPERATE:
                    row({**coverage[oid], x[oid]: -1})
            group_rows, loads = defaultdict(dict), defaultdict(dict)
            for itinerary in request.recovery_columns.passenger_itineraries:
                g = groups[itinerary.pax_group_id]
                cost = (coeff.unserved_passenger.value*g.count
                        if itinerary.status == PassengerItineraryStatus.UNSERVED else
                        coeff.passenger_delay_per_pax_minute.value*g.count*itinerary.arrival_delay_minutes)
                v = w[itinerary.itinerary_id] = variable("w:"+itinerary.itinerary_id, cost)
                group_rows[g.pax_group_id][v] = 1
                for seg in itinerary.segments:
                    oid = seg.flight_option_id
                    row({v: 1, x[oid]: -1}, sense=ConstraintSense.LESS_EQUAL)
                    loads[oid][v] = loads[oid].get(v, 0)+g.count
            for gid in groups:
                row(group_rows[gid], 1)
            for oid, terms in loads.items():
                row({**terms, x[oid]: -request.capacity_profile.seat_capacity_by_option_id[oid]},
                    sense=ConstraintSense.LESS_EQUAL)
            solver.set_objective(objective)
            build_seconds = perf_counter()-started
            event("model_built", metrics={**counts, "backend": request.backend, "build_seconds": build_seconds})
            # Native HiGHS callbacks retain independently audited incumbents even
            # if an external watchdog subsequently terminates the worker.
            if request.backend == "highs":
                def incumbent(e):
                    nonlocal saved
                    data = e.data_out
                    values = data.mip_solution
                    result = extract(lambda v: values[solver._variables[v.name]],
                                     finite(data.mip_primal_bound), finite(data.mip_dual_bound))
                    if result["audit"]["pass"]:
                        saved = result
                        if checkpoint_sink:
                            checkpoint_sink(clean(result))
                        event("incumbent_audited", upper_bound=result["objective"],
                              lower_bound=result["lower_bound"], metrics={"bound_scope": "global"})
                def progress(e):
                    data = e.data_out
                    event("mip_progress", lower_bound=finite(data.mip_dual_bound),
                          upper_bound=finite(data.mip_primal_bound), metrics={
                              "bound_scope": "global", "node_count": int(data.mip_node_count)})
                solver._model.cbMipImprovingSolution.subscribe(incumbent)
                solver._model.cbMipLogging.subscribe(progress)
            result = solver.solve({"TimeLimit": max(.001, budget.remaining()), "MIPGap": 0.0,
                                   "MIPGapAbs": 0.0, "Threads": 1})
            if result.has_solution:
                # Read the native vector once; repeated getSolution() calls for
                # every assignment would copy a large vector quadratically.
                values = solver._model.getSolution().col_value if request.backend == "highs" else None
                value = (lambda v: values[solver._variables[v.name]]) if values is not None else solver.get_variable_value
                selected = extract(value, result.objective_value, result.best_bound)
                if not selected["audit"]["pass"]:
                    raise RuntimeError("direct MIP independent audit rejected solution: "+str(selected["audit"]))
                saved = selected
                if checkpoint_sink:
                    checkpoint_sink(clean(selected))
            lb, ub = result.best_bound, selected["objective"] if selected else None
            closed = lb is not None and ub is not None and abs(ub-lb) <= 1e-5
            cancelled = bool(cancel_check and cancel_check())
            optimal = result.status.value == "optimal" and selected is not None and closed and not cancelled
            if result.status.value == "optimal" and not optimal and not cancelled:
                raise RuntimeError("direct MIP optimal label rejected: missing audited primal or closed bounds")
            status = "aborted" if cancelled else "optimal" if optimal else "infeasible" if result.status.value == "infeasible" else "not_converged"
            return clean(dict(status=status, algorithm="direct_mip", backend=request.backend,
                problem_sha256=request.problem_sha256, objective=ub, lower_bound=lb, upper_bound=ub,
                gap=max(0, ub-lb) if ub is not None and lb is not None else None,
                certified_optimal=optimal, certified_infeasible=status == "infeasible",
                audit=selected["audit"] if selected else None, selected=selected["selected"] if selected else None,
                solution_columns=selected["columns"] if selected else None, core=result,
                timings={"model_build_seconds": build_seconds, "solver_call_seconds": result.runtime_seconds},
                model_size=counts, runtime_seconds=perf_counter()-started,
                original_rules={"eligible": False},
                certificate_scope="frozen_public_research_model; compact aircraft flow; fixed passenger candidates"))
    except (SolveStopped, OverflowError) as exc:
        return clean(dict(status="input_limit" if isinstance(exc, OverflowError) else
                          "aborted" if str(exc) == "cancelled" else "not_converged",
            algorithm="direct_mip", backend=request.backend, problem_sha256=request.problem_sha256,
            reason=str(exc), objective=saved["objective"] if saved else None,
            lower_bound=saved["lower_bound"] if saved else None, upper_bound=saved["objective"] if saved else None,
            audit=saved["audit"] if saved else None, selected=saved["selected"] if saved else None,
            solution_columns=saved["columns"] if saved else None, model_size=counts,
            certified_optimal=False, runtime_seconds=perf_counter()-started, original_rules={"eligible": False}))
