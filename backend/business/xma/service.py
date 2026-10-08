from __future__ import annotations

import hashlib
from collections import Counter
from datetime import datetime, timedelta, timezone
from time import perf_counter

from backend.schemas.workbench import CompilePreview, DraftDocument, FlightImpact, WorkbenchIssue
from backend.workbench.storage import content_hash

from .algorithms import Budget, benders, direct
from .evaluator import evaluate, export_csv
from .importer import validate_dataset
from .rules import adjustable, generate_options, build_networks
from .schema import XmaSolveRequest


def presentation_scenario(request: XmaSolveRequest) -> dict:
    """Read-only workbench presentation; intentionally not an AIR Scenario."""
    data=request.dataset
    return {"scenario_id":data.dataset_id,"recovery_window":{"start_time":min(f.sched_dep for f in data.flights).isoformat(),
        "end_time":(max(f.sched_arr for f in data.flights)+timedelta(minutes=request.maximum_delay_minutes)).isoformat()},
        "airports":[{"airport_id":a,"name":a} for a in sorted(data.airports)],
        "flights":[{"flight_id":f.flight_id,"origin":f.origin,"destination":f.destination,"sched_dep":f.sched_dep.isoformat(),
            "sched_arr":f.sched_arr.isoformat(),"duration":int((f.sched_arr-f.sched_dep).total_seconds()/60),
            "original_aircraft":f.original_aircraft,"original_equipment":f.equipment,"original_crew":None,
            "strategic_flag":False,"market_flag":False,"min_seats":0,"max_delay":request.maximum_delay_minutes,
            "passengers":f.passengers,"through_passengers":f.through_passengers,"physical_seats":f.seats,"importance":f.importance}
            for f in data.flights],
        "aircraft":[{"tail_id":a.tail_id,"equipment_type":a.equipment,"initial_station_at_t":a.initial_station,
            "required_station_at_T_end":None,"original_terminal":a.original_terminal,"original_rotation":a.original_rotation,"maintenance_required":False,
            "maintenance_stations":[],"physical_seats":a.seats,"terminal_semantics":"fleet aggregate, not fixed per tail"} for a in data.aircraft],
        "crew":[],"passengers":[{"pax_group_id":"LOAD_"+f.flight_id,"count":f.passengers+f.through_passengers,
            "origin":f.origin,"destination":f.destination,"original_departure":f.sched_dep.isoformat(),
            "scheduled_arrival":f.sched_arr.isoformat(),"original_itinerary":[f.flight_id],"semantics":"flight-leg load, not unique people"}
            for f in data.flights if f.passengers+f.through_passengers],
        "airport_intervals":[],"disruptions":[{"airport":s.airport,"start_time":s.start.isoformat(),"end_time":s.end.isoformat(),
            "restriction_type":s.kind,"capacity_change":None,"parking_limit":s.parking_limit} for s in data.scenes]}


def make_document(request: XmaSolveRequest) -> DraftDocument:
    return DraftDocument(name="厦航研究 · "+request.dataset.dataset_id,scenario=presentation_scenario(request),
        solve_bundle=request.model_dump(mode="json"),notes=["XMA business contract. Crew disabled. Airport capacities unspecified outside source rules.",
        "Two independent objectives; all algorithm comparisons must use the same candidate parameters."])


def normalize_document(document: DraftDocument) -> DraftDocument:
    if (document.solve_bundle or {}).get("schema_version")=="xma-solve-1.0":
        request=XmaSolveRequest.model_validate(document.solve_bundle)
        return document.model_copy(update={"scenario":presentation_scenario(request)})
    return document


def precheck(request: XmaSolveRequest) -> dict:
    errors=validate_dataset(request.dataset)
    if any(s.flight_id or s.tail_id for s in request.dataset.scenes):
        errors.append("flight/tail-specific scenes are unsupported in this dataset profile")
    options=generate_options(request) if not errors else []
    counts=Counter(o.flight_id for o in options)
    errors.extend(f"no legal candidate for flight {f.flight_id}" for f in request.dataset.flights if not counts[f.flight_id])
    assignment_count=sum(len(n["ordered"]) for n in build_networks(request.dataset,options,connect=False).values()) if not errors else 0
    if assignment_count>request.max_assignment_options:
        errors.append(f"assignment network has {assignment_count} tail-option pairs, exceeds configured limit {request.max_assignment_options}; increase delay_step_minutes, lower maximum_delay_minutes, or explicitly raise max_assignment_options")
    return {"solve_ready":not errors,"errors":errors,"flight_options":len(options),"crew_enabled":False,
        "capacity_semantics":"physical seats by selected tail","semantics":"INPUT_READINESS_NOT_OPTIMIZATION_FEASIBILITY",
        "objective_profile":request.objective_profile,"algorithm":request.algorithm,"normal_airport_capacity":"unspecified",
        "assignment_options":assignment_count}


def compile_document(document: DraftDocument) -> CompilePreview:
    digest=content_hash(document.model_dump(mode="json"))
    try:
        request=XmaSolveRequest.model_validate(document.solve_bundle)
        if document.typed_disruptions or document.manual_flight_options or document.manual_passenger_itineraries:
            raise ValueError("XMA rules and candidates must be edited in the business dataset/configuration, not legacy AIR fields")
        ready=precheck(request)
        scenario=presentation_scenario(request)
        impacts=[]
        direct_ids=set()
        for f in request.dataset.flights:
            refs=[f"xma-{s.source.row}" for s in request.dataset.scenes if
                s.kind=="departure" and s.airport==f.origin and s.start<f.sched_dep<s.end or
                s.kind=="arrival" and s.airport==f.destination and s.start<f.sched_arr<s.end]
            if refs:
                direct_ids.add(f.flight_id)
            impacts.append(FlightImpact(flight_id=f.flight_id,status="direct" if refs else "normal",direct_rule_ids=refs))
        by_id={i.flight_id:i for i in impacts}
        for a in request.dataset.aircraft:
            seeds=[]
            for fid in a.original_rotation:
                if fid in direct_ids:
                    seeds.append(fid)
                elif seeds:
                    by_id[fid].status="downstream"
                    by_id[fid].propagation_sources=[{"source_flight_id":s,"type":"aircraft","resource_id":a.tail_id} for s in seeds]
        bundle=request.model_dump(mode="json")
        valid=ready["solve_ready"]
        return CompilePreview(valid=valid,draft_hash=digest,compiled_hash=content_hash(bundle) if valid else None,
            effective_scenario=scenario,solve_request=bundle if valid else None,readiness=ready,flight_impacts=impacts,
            candidate_counts={"flight_options":ready["flight_options"],"passenger_itineraries":0,"crew_pairings":0,"aircraft_strings":0},
            issues=[WorkbenchIssue(code="xma_input",message=e,path="solve_bundle.dataset") for e in ready["errors"]])
    except ValueError as exc:
        return CompilePreview(valid=False,draft_hash=digest,issues=[WorkbenchIssue(code="invalid_xma_input",message=str(exc),path="solve_bundle")])


def solve(request: XmaSolveRequest, *, event_sink=None,cancel_check=None,run_id=None,runtime_controls=None,solution_artifact_sink=None) -> dict:
    started=perf_counter()
    input_digest=content_hash(request.model_dump(mode="json"))
    ready=precheck(request)
    if not ready["solve_ready"]:
        raise ValueError("; ".join(ready["errors"]))
    if runtime_controls:
        duration=runtime_controls.get("time_limit_seconds")
        if duration:
            request=request.model_copy(update={"time_limit_seconds":min(request.time_limit_seconds,float(duration))})
        limits={"max_benders_iterations":"max_benders_iterations","max_branch_nodes":"max_bp_nodes"}
        request=request.model_copy(update={target:min(getattr(request,target),int(runtime_controls[source]))
            for source,target in limits.items() if runtime_controls.get(source)})
        if runtime_controls.get("relative_gap_tolerance") is not None:
            request=request.model_copy(update={"mip_gap":float(runtime_controls["relative_gap_tolerance"])})
    budget=Budget(request.time_limit_seconds,event_sink,cancel_check)
    options=generate_options(request)
    if request.algorithm in ("joint_arc_flow","joint_path_oracle"):
        outcome=direct(request,options,budget,oracle=request.algorithm=="joint_path_oracle")
    else:
        outcome=benders(request,options,budget,use_cg=request.algorithm=="benders_cg_bp")
    audit=evaluate(request,outcome.decisions) if outcome.decisions else None
    data=request.dataset
    flights={f.flight_id:f for f in data.flights}
    resolved=[]
    for d in outcome.decisions:
        f=flights[d.flight_id]
        delay=int((d.dep-f.sched_dep).total_seconds()/60)
        resolved.append({"resolved":{"flight_id":d.flight_id,"selected_option_id":d.option_id,
            "status":"cancelled" if d.cancelled else "operated","recovered_origin":None if d.cancelled else f.origin,
            "recovered_destination":None if d.cancelled else f.destination,"recovered_dep":None if d.cancelled else d.dep.isoformat(),
            "recovered_arr":None if d.cancelled else d.arr.isoformat(),"aircraft_id":None if d.cancelled else d.aircraft_id,
            "crew_id":None,"departure_delay_minutes":None if d.cancelled else delay,"arrival_delay_minutes":None if d.cancelled else delay},
            "original":{"origin":f.origin,"destination":f.destination,"dep":f.sched_dep.isoformat(),"arr":f.sched_arr.isoformat()}})
    rotations={a.tail_id:sorted([d for d in outcome.decisions if not d.cancelled and d.aircraft_id==a.tail_id],key=lambda d:d.dep) for a in data.aircraft}
    aircraft_outcomes=[{"aircraft_id":a.tail_id,"selected_string_id":"XMA_PATH_"+a.tail_id,
        "ordered_flight_option_ids":[d.option_id for d in rotations[a.tail_id]],"original_flight_ids":a.original_rotation,
        "recovered_flight_ids":[d.flight_id for d in rotations[a.tail_id]],
        "reassignment_count":sum(flights[d.flight_id].original_aircraft!=a.tail_id for d in rotations[a.tail_id]),
        "ferry_legs":[],"final_station":flights[rotations[a.tail_id][-1].flight_id].destination if rotations[a.tail_id] else a.initial_station}
        for a in data.aircraft] if outcome.decisions else []
    objective=None
    if audit:
        if request.objective_profile=="tianchi_2017":
            b=audit["breakdown"]
            objective={"total":audit["objective"],"schedule":b["cancel_flight"]+b["flight_delay"],"aircraft":b["swap_flight"],
                "crew":0,"passenger":b["passenger_cancel"]+b["passenger_delay"]+b["sign_change_delay"],
                "profile":request.objective_profile,"units":"tianchi_score","breakdown":b}
        else:
            objective={"total":audit["objective"],**audit["air_breakdown"],"crew":0,"profile":request.objective_profile,"units":"abstract_cost_units"}
    metrics={"operated_flights":sum(not d.cancelled for d in outcome.decisions),"cancelled_flights":sum(d.cancelled for d in outcome.decisions),
        "delayed_flights":sum(not d.cancelled and d.dep>flights[d.flight_id].sched_dep for d in outcome.decisions),
        "total_flight_departure_delay_minutes":sum(int((d.dep-flights[d.flight_id].sched_dep).total_seconds()/60) for d in outcome.decisions if not d.cancelled),
        "aircraft_reassignments":sum(not d.cancelled and d.aircraft_id!=flights[d.flight_id].original_aircraft for d in outcome.decisions),
        "crew_reassignments":0,"passenger_reaccommodated_count":sum(sum(d.rebook.values()) for d in outcome.decisions),
        "unserved_passengers":sum(row["unserved"] for row in audit["passenger_ledger"]) if audit else 0,
        "passenger_count_semantics":"flight-leg scoring quantities, not unique traveler count"}
    digest=content_hash(request.model_dump(mode="json"))
    from .importer import DEFAULT_WORKBOOK
    evaluator_file=DEFAULT_WORKBOOK.parent/"XMAEvaluation_source_code.zip"
    evaluator_sha=hashlib.sha256(evaluator_file.read_bytes()).hexdigest() if evaluator_file.exists() else None
    diagnostics={"algorithm":request.algorithm,"lower_bound":outcome.lower,"upper_bound":outcome.upper,
        "gap":max(0,outcome.upper-outcome.lower) if outcome.upper is not None and outcome.lower is not None else None,
        "relative_gap":max(0,outcome.upper-outcome.lower)/max(1,abs(outcome.upper)) if outcome.upper is not None and outcome.lower is not None else None,
        "runtime_seconds":perf_counter()-started,"terminal_reason":outcome.reason,"integrated_audit_pass":audit["valid"] if audit else None,
        "statistics":outcome.statistics,"candidate_options":len(options),"candidate_scope":"finite delay grid plus source boundary times",
        "pricing_uses_enumeration":False if request.algorithm=="benders_cg_bp" else None}
    artifact={"schema_version":"xma-result-1.0","flight_options":[{"option_id":o.option_id,"base_flight_id":o.flight_id,
        "flight_id":o.flight_id,"operation_type":"cancel" if o.cancelled else "operate","origin":flights[o.flight_id].origin,
        "destination":flights[o.flight_id].destination,"dep_time":o.dep.isoformat(),"arr_time":o.arr.isoformat()} for o in options],
        "aircraft_strings":[{"aircraft_id":a["aircraft_id"],"leg_option_ids":a["ordered_flight_option_ids"]} for a in aircraft_outcomes],
        "cost_items":[{"name":k,"value":v} for k,v in (audit["breakdown"] if audit and request.objective_profile=="tianchi_2017" else audit["air_breakdown"] if audit else {}).items()],
        "business_decisions":[d.model_dump(mode="json") for d in outcome.decisions],"independent_audit":audit}
    if solution_artifact_sink and outcome.decisions:
        solution_artifact_sink(artifact)
    if audit:
        budget.emit("audit","audit_completed","独立评分与业务约束复算完成",metrics={"integrated_audit":audit})
    budget.emit("complete","solve_bounds","求解结束",lower_bound=outcome.lower,upper_bound=outcome.upper)
    return {"schema_version":"xma-result-1.0","status":outcome.status,"scenario_id":data.dataset_id,"objective":objective,
        "diagnostics":diagnostics,"metrics":metrics,"resolved_flights":resolved,"aircraft_outcomes":aircraft_outcomes,"crew_outcomes":[],
        "passenger_outcomes":[],"passenger_allocations":audit["passenger_ledger"] if audit else [],
        "selected":{"flight_options":[d.option_id for d in outcome.decisions],"aircraft_strings":[a["selected_string_id"] for a in aircraft_outcomes],
            "crew_pairings":[],"passenger_itineraries":[]},"recovery_actions":[{"flight_id":d.flight_id,"action_type":"cancel" if d.cancelled else "delay_or_reassign",
            "rebook":d.rebook} for d in outcome.decisions if d.cancelled or d.dep!=flights[d.flight_id].sched_dep or d.aircraft_id!=flights[d.flight_id].original_aircraft or d.rebook],
        "business_decisions":[d.model_dump(mode="json") for d in outcome.decisions],"independent_audit":audit,
        "run_metadata":{"run_id":run_id,"input_hash":input_digest,"effective_input_hash":digest,"runtime_controls":runtime_controls,
            "source_sha256":data.source_sha256,"objective_profile":request.objective_profile,
            "objective_version":"tianchi_2017_supported_actions_v1" if request.objective_profile=="tianchi_2017" else "air_linear_v1",
            "source_evaluator_sha256":evaluator_sha,
            "objective_parameters":request.air_objective.model_dump() if request.objective_profile=="air_linear_v1" else "bundled Configuration.java / ResultEvaluator.java",
            "algorithm":request.algorithm,"created_at":datetime.now(timezone.utc).isoformat(),"crew_enabled":False,"maintenance_enabled":False},
        "tianchi_csv":export_csv(request,outcome.decisions) if outcome.decisions else None}
