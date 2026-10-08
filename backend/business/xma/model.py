"""Shared joint equations with arc-flow or aircraft-path representations."""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field

import gurobipy as gp
from gurobipy import GRB

from .objectives import assignment_cost, resident_cost, schedule_cost, sign_cost, unserved_cost
from .rules import adjustable, build_networks, enumerate_paths, movement_buckets
from .schema import Decision, Option, XmaSolveRequest
from .solver import ScalableModel, value


@dataclass
class JointModel:
    model: ScalableModel
    request: XmaSolveRequest
    options: list[Option]
    networks: dict
    x: dict
    u: dict
    sign: dict
    resident: dict
    loss: dict
    integer_variables: list = field(default_factory=list)
    path_rows: dict = field(default_factory=dict)
    paths: dict = field(default_factory=dict)
    path_variables: dict = field(default_factory=dict)
    objective: object = None
    environment: object = None

    def close(self):
        self.model.dispose()
        self.environment.dispose()


def new_model(name: str):
    env=gp.Env(empty=True)
    env.setParam("OutputFlag",0)
    env.start()
    model=ScalableModel(name,env)
    model.Params.OutputFlag=0
    model.Params.Threads=1
    model.Params.Seed=0
    return model,env


def add_schedule_rows(model,request,options,x):
    by_flight=defaultdict(list)
    for o in options:
        by_flight[o.flight_id].append(o)
    for f in request.dataset.flights:
        model.addConstr(gp.quicksum(x[o.option_id] for o in by_flight[f.flight_id])==1,name=f"flight:{f.flight_id}")
    for key,ids in movement_buckets(request.dataset,options).items():
        model.addConstr(gp.quicksum(x[oid] for oid in ids)<=request.dataset.movement_limit,name=f"movement:{key}")
    flights={f.flight_id:f for f in request.dataset.flights}
    for a,b in request.dataset.connected_pairs:
        if not adjustable(request.dataset,flights[a]) or not adjustable(request.dataset,flights[b]):
            for fid in (a,b):
                for o in by_flight[fid]:
                    if o.cancelled:
                        model.addConstr(x[o.option_id]==0,name=f"frozen_connected:{fid}")


def build_joint(request: XmaSolveRequest, options: list[Option], *, representation="arc", schedule=None,
                relax=False, branch_bounds=None, enumerate_all=False) -> JointModel:
    if schedule is not None:
        options=[o for o in options if o.option_id in schedule]
    data=request.dataset
    flights={f.flight_id:f for f in data.flights}
    tails={a.tail_id:a for a in data.aircraft}
    model,env=new_model(f"xma_joint_{representation}")
    binary=GRB.CONTINUOUS if relax else GRB.BINARY
    integer=GRB.CONTINUOUS if relax else GRB.INTEGER
    ints=[]
    def var(name,ub=1,kind=binary):
        v=model.addVar(lb=0,ub=ub,vtype=kind,name=name)
        ints.append(v)
        return v
    x={o.option_id:var("x:"+o.option_id) for o in options}
    if schedule is not None:
        for v in x.values():
            v.LB=1
    add_schedule_rows(model,request,options,x)
    by_flight=defaultdict(list)
    for o in options:
        by_flight[o.flight_id].append(o)
    c={f.flight_id:gp.quicksum(x[o.option_id] for o in by_flight[f.flight_id] if o.cancelled) for f in data.flights}
    alive={f.flight_id:1-c[f.flight_id] for f in data.flights}
    networks=build_networks(data,options,connect=representation!="arc")
    u={}
    objective=gp.quicksum(schedule_cost(request,flights[o.flight_id],o)*x[o.option_id] for o in options)
    for tail,net in networks.items():
        for oid in net["ordered"]:
            u[tail,oid]=var(f"u:{tail}:{oid}")
            f=flights[net["options"][oid].flight_id]
            model.addConstr(u[tail,oid]<=x[oid],name=f"assignment_schedule:{tail}:{oid}")
            objective+=assignment_cost(request,f,tail)*u[tail,oid]
            if not adjustable(data,f):
                model.addConstr(u[tail,oid]==x[oid],name=f"frozen_tail:{tail}:{oid}")
    option_u=defaultdict(list)
    for (tail,oid),v in u.items():
        option_u[oid].append(v)
    for o in options:
        if not o.cancelled:
            model.addConstr(gp.quicksum(option_u[o.option_id])==x[o.option_id],name="coverage:"+o.option_id)
    terminals=Counter((a.equipment,a.original_terminal) for a in data.aircraft)
    parking_limits={s.airport:min(t.parking_limit for t in data.scenes if t.kind=="parking" and t.airport==s.airport)
        for s in data.scenes if s.kind=="parking"}
    pair_keys=set(data.connected_pairs)
    shortcuts=defaultdict(set)
    for key,turn in data.original_turn_minutes.items():
        if turn<50:
            left,right=key.split("#")
            shortcuts[left].add(right)
    for left,right in pair_keys:
        shortcuts[left].add(right)
    rows={}
    if representation=="arc":
        terminal_terms=defaultdict(list)
        parking_terms=defaultdict(list)
        pair_terms=defaultdict(list)
        for tail,net in networks.items():
            # Station event timelines compress quadratic flight-to-flight edges.
            # A landing has its own state; ordinary release is after 50 minutes.
            # Original short turns and through adjacency have explicit shortcuts.
            from datetime import timedelta
            events=defaultdict(set)
            incoming=defaultdict(list)
            outgoing=defaultdict(list)
            boarding=defaultdict(list)
            start_time=min(f.sched_dep for f in data.flights)
            source_node=(tails[tail].initial_station,start_time)
            events[source_node[0]].add(start_time)
            local_by_flight=defaultdict(list)
            for oid in net["ordered"]:
                o=net["options"][oid]
                f=flights[o.flight_id]
                local_by_flight[f.flight_id].append(o)
                events[f.origin].add(o.dep)
                events[f.destination].add(o.arr+timedelta(minutes=50))
                board=var(f"board:{tail}:{oid}")
                outgoing[f.origin,o.dep].append(board)
                boarding[oid].append(board)
            for airport,times in events.items():
                times=sorted(times)
                for left,right in zip(times,times[1:]):
                    v=var(f"ground:{tail}:{airport}:{left.isoformat()}")
                    outgoing[airport,left].append(v)
                    incoming[airport,right].append(v)
            endings=[]
            for oid in net["ordered"]:
                o=net["options"][oid]
                f=flights[o.flight_id]
                v=var(f"arc:{tail}:{oid}:END")
                endings.append(v)
                landing_out=[v]
                terminal_terms[tails[tail].equipment,f.destination].append(v)
                release=var(f"release:{tail}:{oid}")
                landing_out.append(release)
                incoming[f.destination,o.arr+timedelta(minutes=50)].append(release)
                for next_fid in shortcuts[f.flight_id]:
                    next_options=local_by_flight[next_fid]
                    short=data.original_turn_minutes.get(f"{f.flight_id}#{next_fid}",50)<50
                    pair=(f.flight_id,next_fid)
                    if not short and pair not in pair_keys:
                        continue
                    turn=min(50,data.original_turn_minutes.get(f"{f.flight_id}#{next_fid}",50))
                    for right in next_options:
                        if f.destination!=flights[next_fid].origin or right.dep<o.arr+timedelta(minutes=turn):
                            continue
                        edge=var(f"shortcut:{tail}:{oid}:{right.option_id}")
                        landing_out.append(edge)
                        # Directly enter this flight, never the shared station
                        # timeline: otherwise the tail could board another leg.
                        boarding[right.option_id].append(edge)
                        if pair in pair_keys:
                            pair_terms[pair].append(edge)
                model.addConstr(gp.quicksum(landing_out)==u[tail,oid],name=f"landing:{tail}:{oid}")
            for oid in net["ordered"]:
                model.addConstr(gp.quicksum(boarding[oid])==u[tail,oid],name=f"boarding:{tail}:{oid}")
            model.addConstr(gp.quicksum(endings)==1,name="end:"+tail)
            for airport,times in events.items():
                for time in times:
                    node=(airport,time)
                    model.addConstr(gp.quicksum(incoming[node])+(node==source_node)==gp.quicksum(outgoing[node]),name=f"event:{tail}:{airport}:{time.isoformat()}")
            for i,s in enumerate(data.scenes):
                if s.kind!="parking":
                    continue
                pre=gp.quicksum(u[tail,oid] for oid in net["ordered"] if flights[net["options"][oid].flight_id].destination==s.airport and net["options"][oid].arr<=s.start)
                future=gp.quicksum(u[tail,oid] for oid in net["ordered"] if flights[net["options"][oid].flight_id].origin==s.airport and net["options"][oid].dep>=s.end)
                departures=gp.quicksum(u[tail,oid] for oid in net["ordered"] if flights[net["options"][oid].flight_id].origin==s.airport and net["options"][oid].dep<=s.start)
                within=gp.quicksum(u[tail,oid] for oid in net["ordered"] if flights[net["options"][oid].flight_id].origin==s.airport and s.start<net["options"][oid].dep<s.end)
                ground=(tails[tail].initial_station==s.airport)+pre-departures
                has_pre=var(f"park_pre:{tail}:{i}")
                has_future=var(f"park_future:{tail}:{i}")
                no_departure=var(f"park_no_departure:{tail}:{i}")
                spans=var(f"park_span:{tail}:{i}")
                n=max(1,len(net["ordered"]))
                model.addConstr(pre>=has_pre)
                model.addConstr(pre<=n*has_pre)
                model.addConstr(future>=has_future)
                model.addConstr(future<=n*has_future)
                model.addConstr(within>=1-no_departure)
                model.addConstr(within<=n*(1-no_departure))
                for condition in (ground,has_pre,has_future,no_departure):
                    model.addConstr(spans<=condition)
                model.addConstr(spans>=ground+has_pre+has_future+no_departure-3)
                parking_terms[s.airport].append(spans)
        for key in set(terminals)|set(terminal_terms):
            model.addConstr(gp.quicksum(terminal_terms[key])==terminals[key],name=f"terminal:{key}")
        for airport,limit in parking_limits.items():
            model.addConstr(gp.quicksum(parking_terms[airport])<=limit,name="parking:"+airport)
        for a,b in data.connected_pairs:
            model.addConstr(gp.quicksum(pair_terms[a,b])>=alive[a]+alive[b]-1,name=f"connected:{a}:{b}")
    else:
        for tail in networks:
            rows["select",tail]=model.addConstr(gp.LinExpr()==1,name="select:"+tail)
        for (tail,oid),v in u.items():
            rows["u",tail,oid]=model.addConstr(-v==0,name=f"path_link:{tail}:{oid}")
        all_terminal_keys=set(terminals)|{(a.equipment,airport) for a in data.aircraft for airport in data.airports}
        for key in sorted(all_terminal_keys):
            rows["terminal",*key]=model.addConstr(gp.LinExpr()==terminals[key],name=f"terminal:{key}")
        for airport,limit in parking_limits.items():
            rows["parking",airport]=model.addConstr(gp.LinExpr()<=limit,name="parking:"+airport)
        for a,b in data.connected_pairs:
            rows["connected",a,b]=model.addConstr(-alive[a]-alive[b]>=-1,name=f"connected:{a}:{b}")
    epoch=min(f.sched_dep for f in data.flights)
    min_time=min((o.dep-epoch).total_seconds()/60 for o in options)
    max_time=max((o.arr-epoch).total_seconds()/60 for o in options)
    time_big=max_time-min_time+max((t.minimum_minutes for t in data.transfers),default=0)+1
    dep={fid:gp.quicksum((o.dep-epoch).total_seconds()/60*x[o.option_id] for o in opts) for fid,opts in by_flight.items()}
    arr={fid:gp.quicksum((o.arr-epoch).total_seconds()/60*x[o.option_id] for o in opts) for fid,opts in by_flight.items()}
    for fid,f in data.boundary_flights.items():
        dep[fid]=(f.sched_dep-epoch).total_seconds()/60
        arr[fid]=(f.sched_arr-epoch).total_seconds()/60
        c[fid]=0
        alive[fid]=1
        time_big=max(time_big,abs(dep[fid]-min_time)+abs(arr[fid]-max_time)+100)
    cancelled_in=defaultdict(list)
    failed_in=defaultdict(list)
    incoming_count=Counter()
    for i,t in enumerate(data.transfers):
        incoming_count[t.outbound]+=t.count
        cancelled_in[t.outbound].append(t.count*c[t.inbound])
        fail=var(f"transfer_fail:{i}")
        gap=dep[t.outbound]-arr[t.inbound]-t.minimum_minutes
        model.addConstr(fail<=alive[t.inbound],name=f"transfer_source:{i}")
        model.addConstr(gap>=-time_big*(fail+c[t.inbound]),name=f"transfer_ok:{i}")
        model.addConstr(gap<=-1+time_big*(1-fail+c[t.inbound]),name=f"transfer_bad:{i}")
        failed_in[t.outbound].append(t.count*fail)
    partner={a:b for a,b in data.connected_pairs}|{b:a for a,b in data.connected_pairs}
    first={a for a,b in data.connected_pairs}
    M=2*max(f.passengers+f.through_passengers for f in data.flights)+max(a.seats for a in data.aircraft)+1
    resident={}
    loss={}
    overflow={}
    send={}
    for f in data.flights:
        fid=f.flight_id
        tc=gp.quicksum(cancelled_in[fid])
        tf=gp.quicksum(failed_in[fid])
        through=f.through_passengers*c[partner[fid]] if fid in partner else 0
        N=f.passengers+f.through_passengers-tc-tf-through if adjustable(data,f) else f.passengers+f.through_passengers
        seat=gp.quicksum(
            tails[tail].seats*u[tail,o.option_id] for o in by_flight[fid] if not o.cancelled for tail in networks if (tail,o.option_id) in u)
        over=var("overflow:"+fid,M,integer)
        flag=var("overflow_flag:"+fid)
        model.addConstr(over>=N-seat-M*c[fid],name="overflow_lower:"+fid)
        model.addConstr(over<=N-seat+M*(1-flag+c[fid]),name="overflow_upper:"+fid)
        model.addConstr(over<=M*flag,name="overflow_zero:"+fid)
        model.addConstr(over<=M*alive[fid],name="overflow_operated:"+fid)
        resident[fid]=var("resident:"+fid,M,integer)
        model.addConstr(resident[fid]<=M*alive[fid],name="resident_operated:"+fid)
        model.addConstr(resident[fid]-N+over<=M*c[fid],name="resident_upper:"+fid)
        model.addConstr(resident[fid]-N+over>=-M*c[fid],name="resident_lower:"+fid)
        overflow[fid]=over
        loss[fid]=var("loss:"+fid,M,integer)
        operating_loss=tc+tf+over+(through if fid in first else 0) if adjustable(data,f) else over
        cancel_loss=f.passengers+(f.through_passengers if fid in first else 0)
        model.addConstr(loss[fid]-operating_loss<=M*c[fid],name="loss_operating_upper:"+fid)
        model.addConstr(loss[fid]-operating_loss>=-M*c[fid],name="loss_operating_lower:"+fid)
        model.addConstr(loss[fid]-cancel_loss<=M*alive[fid],name="loss_cancel_upper:"+fid)
        model.addConstr(loss[fid]-cancel_loss>=-M*alive[fid],name="loss_cancel_lower:"+fid)
        send[fid]=var("send:"+fid)
        if not adjustable(data,f):
            send[fid].UB=0
        parts=[]
        for o in by_flight[fid]:
            if o.cancelled:
                continue
            part=var("resident_part:"+o.option_id,M,integer)
            model.addConstr(part<=M*x[o.option_id],name="resident_option:"+o.option_id)
            parts.append(part)
            coefficient=resident_cost(request,o)
            if request.objective_profile=="tianchi_2017" and not adjustable(data,f):
                coefficient=0
            objective+=coefficient*part
        model.addConstr(gp.quicksum(parts)==resident[fid],name="resident_parts:"+fid)
    sign={}
    outs=defaultdict(list)
    ins=defaultdict(list)
    by_route=defaultdict(list)
    for o in options:
        if not o.cancelled:
            f=flights[o.flight_id]
            by_route[f.origin,f.destination].append(o)
    for f in data.flights:
        if not adjustable(data,f):
            continue
        for o in by_route[f.origin,f.destination]:
            if o.flight_id==f.flight_id or o.dep<f.sched_dep:
                continue
            v=var(f"sign:{f.flight_id}:{o.option_id}",M,integer)
            sign[f.flight_id,o.option_id]=v
            outs[f.flight_id].append(v)
            ins[o.flight_id].append(v)
            model.addConstr(v<=M*x[o.option_id],name=f"sign_target:{f.flight_id}:{o.option_id}")
            delay=(o.dep-f.sched_dep).total_seconds()/60
            coefficient=sign_cost(request,delay)
            if request.objective_profile=="tianchi_2017" and not adjustable(data,flights[o.flight_id]):
                coefficient=0
            objective+=coefficient*v
    for f in data.flights:
        fid=f.flight_id
        out=gp.quicksum(outs[fid])
        model.addConstr(out<=M*send[fid],name="send_upper:"+fid)
        model.addConstr(out>=send[fid],name="send_positive:"+fid)
        model.addConstr(gp.quicksum(ins[fid])<=M*(1-send[fid]),name="no_sign_chain:"+fid)
        tc=gp.quicksum(cancelled_in[fid])
        tf=gp.quicksum(failed_in[fid])
        model.addConstr(out<=tf+overflow[fid]+M*c[fid],name="sign_disruption:"+fid)
        model.addConstr(out<=f.passengers-incoming_count[fid]-tc+M*(1-c[fid])+M*(1-send[fid]),name="sign_ordinary:"+fid)
        model.addConstr(out<=loss[fid],name="sign_loss:"+fid)
        seat=gp.quicksum(tails[tail].seats*u[tail,o.option_id] for o in by_flight[fid] if not o.cancelled for tail in networks if (tail,o.option_id) in u)
        model.addConstr(resident[fid]+gp.quicksum(ins[fid])<=seat,name="physical_seats:"+fid)
        objective+=unserved_cost(request)*(loss[fid]-out)
    model.setObjective(objective,GRB.MINIMIZE)
    joint=JointModel(model,request,options,networks,x,u,sign,resident,loss,ints,rows,objective=objective,environment=env)
    if branch_bounds:
        model.update()
        for name,(lb,ub) in branch_bounds.items():
            v=model.getVarByName(name)
            if v is None:
                raise ValueError("unknown branching variable "+name)
            v.LB=max(v.LB,lb)
            v.UB=min(v.UB,ub)
    if representation!="arc" and enumerate_all:
        try:
            count=0
            for tail,net in networks.items():
                paths=enumerate_paths(net,request.oracle_path_limit-count)
                count+=len(paths)
                for path in paths:
                    add_path(joint,tail,path,integer=not relax)
        except ValueError:
            joint.close()
            raise
    model.update()
    return joint


def path_coefficients(joint: JointModel, tail: str, path: tuple) -> dict:
    data=joint.request.dataset
    flights={f.flight_id:f for f in data.flights}
    aircraft=next(a for a in data.aircraft if a.tail_id==tail)
    net=joint.networks[tail]
    coeff={("select",tail):1}
    for oid in path:
        coeff["u",tail,oid]=1
    end=flights[net["options"][path[-1]].flight_id].destination
    coeff["terminal",aircraft.equipment,end]=1
    for left,right in zip(path,path[1:]):
        a,b=net["options"][left],net["options"][right]
        pair=(a.flight_id,b.flight_id)
        if ("connected",*pair) in joint.path_rows:
            coeff["connected",*pair]=coeff.get(("connected",*pair),0)+1
        airport=flights[b.flight_id].origin
        for s in data.scenes:
            if s.kind=="parking" and s.airport==airport and a.arr<=s.start and b.dep>=s.end:
                coeff["parking",airport]=coeff.get(("parking",airport),0)+1
    return coeff


def add_path(joint: JointModel, tail: str, path: tuple, *, integer=False):
    key=(tail,path)
    if key in joint.path_variables:
        return
    coeff=path_coefficients(joint,tail,path)
    column=gp.Column([v for v in coeff.values()],[joint.path_rows[k] for k in coeff])
    v=joint.model.addVar(lb=0,ub=GRB.INFINITY,vtype=GRB.BINARY if integer else GRB.CONTINUOUS,
        obj=0,column=column,name=f"path:{tail}:{len(joint.path_variables)}")
    joint.paths[key]=coeff
    joint.path_variables[key]=v


def decisions_from_model(joint: JointModel) -> list[Decision]:
    chosen={o.flight_id:o for o in joint.options if value(joint.model,joint.x[o.option_id])>0.5}
    flights={f.flight_id:f for f in joint.request.dataset.flights}
    assigned={oid:tail for (tail,oid),v in joint.u.items() if value(joint.model,v)>0.5}
    options={o.option_id:o for o in joint.options}
    rebook=defaultdict(Counter)
    for (fid,oid),v in joint.sign.items():
        if value(joint.model,v)>0.5:
            rebook[fid][options[oid].flight_id]+=int(round(value(joint.model,v)))
    return [Decision(flight_id=fid,option_id=o.option_id,aircraft_id=assigned.get(o.option_id,flights[fid].original_aircraft),
        cancelled=o.cancelled,dep=o.dep,arr=o.arr,rebook=dict(rebook[fid])) for fid,o in chosen.items()]
