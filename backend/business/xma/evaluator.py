"""Independent implementation of the bundled evaluator's supported action subset.

Does not inspect model variables, generated networks or objective expressions.
"""
from __future__ import annotations

import csv
import io
from collections import Counter, defaultdict
from datetime import timedelta, timezone

from .objectives import assignment_cost, normal_delay_cost, rebook_delay_cost
from .rules import adjustable, closed
from .schema import Decision, XmaSolveRequest


def evaluate(request: XmaSolveRequest, decisions: list[Decision]) -> dict:
    data=request.dataset
    flights={f.flight_id:f for f in data.flights}
    chosen={d.flight_id:d for d in decisions}
    tails={a.tail_id:a for a in data.aircraft}
    errors=[]
    if len(chosen)!=len(decisions) or set(chosen)!=set(flights):
        return {"valid":False,"violations":["flight IDs are missing, duplicated or unknown"],"score":None}
    for fid,f in data.boundary_flights.items():
        chosen[fid]=Decision(flight_id=fid,option_id="BOUNDARY",aircraft_id=f.original_aircraft,cancelled=False,dep=f.sched_dep,arr=f.sched_arr)
    through_partner={a:b for a,b in data.connected_pairs}|{b:a for a,b in data.connected_pairs}
    first_parts={a for a,b in data.connected_pairs}
    cancelled_in=Counter()
    failed_in=Counter()
    incoming_count=Counter()
    for t in data.transfers:
        incoming_count[t.outbound]+=t.count
        a,b=chosen[t.inbound],chosen[t.outbound]
        if a.cancelled:
            cancelled_in[t.outbound]+=t.count
        elif b.dep-a.arr < timedelta(minutes=t.minimum_minutes):
            failed_in[t.outbound]+=t.count
    sign_in=Counter()
    for d in decisions:
        f=flights[d.flight_id]
        for target,count in d.rebook.items():
            if target not in flights or count<=0 or int(count)!=count:
                errors.append(f"invalid rebook {d.flight_id}/{target}")
                continue
            h=chosen[target]
            hf=flights[target]
            if h.cancelled or h.rebook or h.dep<f.sched_dep or (hf.origin,hf.destination)!=(f.origin,f.destination):
                errors.append(f"illegal rebook target {d.flight_id}/{target}")
            sign_in[target]+=count
    breakdown={k:0.0 for k in ("empty_flight","cancel_flight","type_change","swap_flight","straighten",
        "flight_delay","flight_ahead","passenger_cancel","passenger_delay","sign_change_delay")}
    air={"schedule":0.0,"aircraft":0.0,"passenger":0.0}
    ledger=[]
    operated_by_tail=defaultdict(list)
    for d in decisions:
        f=flights[d.flight_id]
        if d.aircraft_id not in tails:
            errors.append(f"unknown tail {d.aircraft_id}")
            continue
        a=tails[d.aircraft_id]
        delay=(d.dep-f.sched_dep).total_seconds()/60
        if not adjustable(data,f) and (d.cancelled or delay or d.arr!=f.sched_arr or d.aircraft_id!=f.original_aircraft or d.rebook):
            errors.append(f"frozen flight changed {f.flight_id}")
        if d.cancelled:
            breakdown["cancel_flight"]+=f.importance*1200
            air["schedule"]+=request.air_objective.flight_cancellation
        else:
            operated_by_tail[d.aircraft_id].append(d)
            if d.arr-d.dep!=f.sched_arr-f.sched_dep or delay<0 or delay>(1440 if f.domestic else 2160):
                errors.append(f"invalid timing {f.flight_id}")
            if a.equipment!=f.equipment or (f.origin,f.destination,a.tail_id) in set(data.route_prohibitions):
                errors.append(f"incompatible assignment {f.flight_id}")
            if closed(data,f.origin,d.dep) or closed(data,f.destination,d.arr):
                errors.append(f"closure {f.flight_id}")
            for s in data.scenes:
                if (s.kind=="departure" and s.airport==f.origin and s.start<d.dep<s.end) or (s.kind=="arrival" and s.airport==f.destination and s.start<d.arr<s.end):
                    errors.append(f"typhoon {f.flight_id}/{s.source.row}")
            breakdown["flight_delay"]+=f.importance*delay*100/60
            boundary=data.adjustment_start.replace(hour=16,minute=0,second=0,microsecond=0)
            swap=f.importance*(15 if f.sched_dep<=boundary else 5) if d.aircraft_id!=f.original_aircraft else 0
            breakdown["swap_flight"]+=swap
            air["schedule"]+=delay*request.air_objective.flight_delay_per_minute
            air["aircraft"]+=(d.aircraft_id!=f.original_aircraft)*request.air_objective.aircraft_reassignment
        sign_out=sum(d.rebook.values())
        through_loss=f.through_passengers if f.flight_id in through_partner and chosen[through_partner[f.flight_id]].cancelled else 0
        if d.cancelled:
            loss=f.passengers+(f.through_passengers if f.flight_id in first_parts else 0)
            resident=0
            if sign_out and sign_out>f.passengers-incoming_count[f.flight_id]-cancelled_in[f.flight_id]:
                errors.append(f"cancelled-flight rebook exceeds ordinary passengers {f.flight_id}")
        elif not adjustable(data,f):
            overflow=max(0,f.passengers+f.through_passengers-a.seats)
            resident=f.passengers+f.through_passengers-overflow
            loss=overflow
            if sign_out:
                errors.append(f"frozen sign change {f.flight_id}")
        else:
            available=f.passengers+f.through_passengers-cancelled_in[f.flight_id]-failed_in[f.flight_id]-through_loss
            overflow=max(0,available-a.seats)
            resident=available-overflow
            loss=cancelled_in[f.flight_id]+failed_in[f.flight_id]+overflow+(through_loss if f.flight_id in first_parts else 0)
            if sign_out>failed_in[f.flight_id]+overflow:
                errors.append(f"operated-flight rebook exceeds disrupted passengers {f.flight_id}")
        unserved=loss-sign_out
        if unserved<0:
            errors.append(f"negative unserved {f.flight_id}")
        if not d.cancelled and resident+sign_in[f.flight_id]>a.seats:
            errors.append(f"seat capacity {f.flight_id}")
        breakdown["passenger_cancel"]+=max(0,unserved)*4
        if adjustable(data,f) and not d.cancelled:
            breakdown["passenger_delay"]+=resident*normal_delay_cost(delay/60)
        air["passenger"]+=max(0,unserved)*request.air_objective.unserved_passenger
        if not d.cancelled:
            air["passenger"]+=resident*delay*request.air_objective.passenger_delay_per_pax_minute
        ledger.append({"flight_id":f.flight_id,"cancelled_in":cancelled_in[f.flight_id],"failed_in":failed_in[f.flight_id],
            "resident":resident,"sign_out":sign_out,"sign_in":sign_in[f.flight_id],"unserved":unserved,
            "physical_seats":a.seats if not d.cancelled else 0,"occupied_seats":resident+sign_in[f.flight_id] if not d.cancelled else 0})
    for d in decisions:
        for target,count in d.rebook.items():
            if target not in flights:
                continue
            delay=(chosen[target].dep-flights[d.flight_id].sched_dep).total_seconds()/60
            if adjustable(data,flights[target]):
                breakdown["sign_change_delay"]+=count*rebook_delay_cost(delay/60)
            air["passenger"]+=count*delay*request.air_objective.passenger_delay_per_pax_minute
    terminal=Counter()
    parking=Counter()
    movement=Counter()
    affected={s.airport for s in data.scenes if s.kind in ("arrival","departure")}
    for tail,rotation in operated_by_tail.items():
        rotation.sort(key=lambda d:(d.dep,d.flight_id))
        if flights[rotation[0].flight_id].origin!=tails[tail].initial_station:
            errors.append(f"initial station {tail}")
        terminal[tails[tail].equipment,flights[rotation[-1].flight_id].destination]+=1
        for left,right in zip(rotation,rotation[1:]):
            lf,rf=flights[left.flight_id],flights[right.flight_id]
            turn=min(50,data.original_turn_minutes.get(f"{left.flight_id}#{right.flight_id}",50))
            if lf.destination!=rf.origin or right.dep-left.arr<timedelta(minutes=turn):
                errors.append(f"aircraft connection {left.flight_id}/{right.flight_id}")
            for s in data.scenes:
                if s.kind=="parking" and rf.origin==s.airport and left.arr<=s.start and right.dep>=s.end:
                    parking[s.airport]+=1
        for d in rotation:
            f=flights[d.flight_id]
            for airport,time in ((f.origin,d.dep),(f.destination,d.arr)):
                if airport in affected:
                    for start,end in data.movement_windows:
                        if start<=time<=end:
                            bucket=int((time-data.movement_windows[0][0]).total_seconds()/60)//data.movement_bucket_minutes
                            movement[airport,bucket]+=1
    expected=Counter((a.equipment,a.original_terminal) for a in data.aircraft)
    if terminal!=expected:
        errors.append("fleet terminal balance")
    for a,b in data.connected_pairs:
        da,db=chosen[a],chosen[b]
        if not da.cancelled and not db.cancelled:
            rot=sorted(operated_by_tail[da.aircraft_id],key=lambda d:(d.dep,d.flight_id))
            ids=[d.flight_id for d in rot]
            if a not in ids or da.aircraft_id!=db.aircraft_id or ids.index(a)+1>=len(ids) or ids[ids.index(a)+1]!=b:
                errors.append(f"connected pair adjacency {a}/{b}")
        if (not adjustable(data,flights[a]) or not adjustable(data,flights[b])) and (da.cancelled or db.cancelled):
            errors.append(f"frozen connected partner {a}/{b}")
    for s in data.scenes:
        if s.kind=="parking" and parking[s.airport]>s.parking_limit:
            errors.append(f"parking {s.airport}")
    for airport in affected:
        if any(count>data.movement_limit for (station,_),count in movement.items() if station==airport):
            errors.append(f"movement capacity {airport}")
    raw=sum(breakdown.values())
    penalty=(50_000_000 if errors else 0)+10*len(errors)
    objective=raw if request.objective_profile=="tianchi_2017" else sum(air.values())
    return {"valid":not errors,"violations":errors,"score":raw+penalty,"raw_score":raw,"penalty":penalty,
        "breakdown":breakdown,"air_breakdown":air,"objective":objective,"passenger_ledger":ledger,
        "penalty_semantics":"Source constants; violation granularity is independently diagnosed, JAR is authoritative for invalid results."}


def export_csv(request: XmaSolveRequest, decisions: list[Decision]) -> str:
    flights={f.flight_id:f for f in request.dataset.flights}
    output=io.StringIO(newline="")
    writer=csv.writer(output,lineterminator="\n")
    for d in sorted(decisions,key=lambda d:d.flight_id):
        f=flights[d.flight_id]
        writer.writerow([d.flight_id,f.origin,f.destination,d.dep.astimezone(timezone(timedelta(hours=8))).strftime("%Y/%m/%d %H:%M"),d.arr.astimezone(timezone(timedelta(hours=8))).strftime("%Y/%m/%d %H:%M"),
            d.aircraft_id,int(d.cancelled),0,0,int(bool(d.rebook)),"&".join(f"{k}:{v}" for k,v in sorted(d.rebook.items()))])
    return output.getvalue()
