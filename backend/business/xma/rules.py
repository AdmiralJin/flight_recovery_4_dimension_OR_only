from __future__ import annotations

from bisect import bisect_left
from collections import defaultdict
from datetime import timedelta, timezone

from .schema import Option, XmaDataset, XmaFlight, XmaSolveRequest


def adjustable(data: XmaDataset, flight: XmaFlight) -> bool:
    return data.adjustment_start <= flight.sched_dep <= data.adjustment_end


def closed(data: XmaDataset, airport: str, time) -> bool:
    time=time.astimezone(timezone(timedelta(hours=8)))
    for c in data.closures:
        if c.airport != airport or not (c.effective_date <= time.date().isoformat() < c.expiration_date):
            continue
        minute = time.hour*60+time.minute
        if c.close_minutes < minute < c.open_minutes:
            return True
    return False


def option_legal(data: XmaDataset, option: Option, flight: XmaFlight) -> bool:
    if option.cancelled:
        return adjustable(data, flight)
    if closed(data, flight.origin, option.dep) or closed(data, flight.destination, option.arr):
        return False
    return not any(s.start < (option.dep if s.kind == "departure" else option.arr) < s.end
        for s in data.scenes if (s.kind == "departure" and s.airport == flight.origin)
        or (s.kind == "arrival" and s.airport == flight.destination))


def generate_options(request: XmaSolveRequest) -> list[Option]:
    data = request.dataset
    options = []
    for f in data.flights:
        delays = {0}
        if adjustable(data,f):
            maximum = min(request.maximum_delay_minutes,1440 if f.domestic else 2160)
            delays.update(range(request.delay_step_minutes,maximum+1,request.delay_step_minutes))
            delays.add(maximum)
            # Exact source boundaries supplement the reproducible uniform grid.
            for s in data.scenes:
                base = f.sched_dep if s.kind == "departure" else f.sched_arr
                if (s.kind=="departure" and s.airport==f.origin) or (s.kind=="arrival" and s.airport==f.destination):
                    for edge in (s.start,s.end):
                        delay=int((edge-base).total_seconds()/60)
                        if 0<=delay<=maximum:
                            delays.add(delay)
            for c in data.closures:
                for base,airport in ((f.sched_dep,f.origin),(f.sched_arr,f.destination)):
                    if c.airport!=airport:
                        continue
                    day=base.replace(hour=0,minute=0,second=0,microsecond=0)
                    for n in range(maximum//1440+2):
                        for minute in (c.close_minutes,c.open_minutes):
                            edge=day+timedelta(days=n,minutes=minute)
                            delay=int((edge-base).total_seconds()/60)
                            if 0<=delay<=maximum:
                                delays.add(delay)
        for delay in sorted(delays):
            o=Option(option_id=f"XMA_{f.flight_id}_D{delay}",flight_id=f.flight_id,cancelled=False,
                dep=f.sched_dep+timedelta(minutes=delay),arr=f.sched_arr+timedelta(minutes=delay),delay=delay)
            if option_legal(data,o,f):
                options.append(o)
        if adjustable(data,f):
            options.append(Option(option_id=f"XMA_{f.flight_id}_C",flight_id=f.flight_id,cancelled=True,
                dep=f.sched_dep,arr=f.sched_arr,delay=0))
    return options


def movement_buckets(data: XmaDataset, options: list[Option]) -> dict[tuple, list[str]]:
    flights={f.flight_id:f for f in data.flights}
    affected={s.airport for s in data.scenes if s.kind in ("arrival","departure")}
    result=defaultdict(list)
    for o in options:
        if o.cancelled:
            continue
        f=flights[o.flight_id]
        for airport,time in ((f.origin,o.dep),(f.destination,o.arr)):
            if airport not in affected:
                continue
            for start,end in data.movement_windows:
                if start<=time<=end:
                    # The bundled evaluator anchors both windows at the first start.
                    bucket=int((time-data.movement_windows[0][0]).total_seconds()/60)//data.movement_bucket_minutes
                    result[airport,bucket].append(o.option_id)
    return dict(result)


def parking_coefficients(data: XmaDataset, left: Option, right: Option) -> tuple[int,...]:
    flights={f.flight_id:f for f in data.flights}
    airport=flights[right.flight_id].origin
    return tuple(i for i,s in enumerate(data.scenes) if s.kind=="parking" and s.airport==airport
        and left.arr<=s.start and right.dep>=s.end)


def build_networks(data: XmaDataset, options: list[Option], *, connect=True) -> dict[str,dict]:
    flights={f.flight_id:f for f in data.flights}
    forbidden=set(data.route_prohibitions)
    by_origin=defaultdict(list)
    for o in options:
        if not o.cancelled:
            by_origin[flights[o.flight_id].origin].append(o)
    for values in by_origin.values():
        values.sort(key=lambda o:(o.dep,o.option_id))
    origin_times={a:[o.dep for o in values] for a,values in by_origin.items()}
    result={}
    for tail in data.aircraft:
        rotation=[flights[fid] for fid in tail.original_rotation]
        before=[f for f in rotation if f.sched_dep<data.adjustment_start]
        after=[f for f in rotation if f.sched_dep>data.adjustment_end]
        prefix=before[-1] if before else None
        suffix=after[0] if after else None
        def within_fixed_context(o):
            f=flights[o.flight_id]
            if not adjustable(data,f):
                return f.original_aircraft==tail.tail_id
            if prefix and o.dep<prefix.sched_arr+timedelta(minutes=min(50,data.original_turn_minutes.get(f"{prefix.flight_id}#{f.flight_id}",50))):
                return False
            if suffix and o.arr>suffix.sched_dep-timedelta(minutes=min(50,data.original_turn_minutes.get(f"{f.flight_id}#{suffix.flight_id}",50))):
                return False
            return True
        eligible={o.option_id:o for o in options if not o.cancelled
            and flights[o.flight_id].equipment==tail.equipment
            and (flights[o.flight_id].origin,flights[o.flight_id].destination,tail.tail_id) not in forbidden
            and within_fixed_context(o)}
        ordered=sorted(eligible,key=lambda oid:(eligible[oid].dep,oid))
        earliest={tail.initial_station:min(f.sched_dep for f in data.flights)}
        reachable=[]
        for oid in ordered:
            o=eligible[oid]
            f=flights[o.flight_id]
            if f.origin not in earliest or o.dep<earliest[f.origin]:
                continue
            reachable.append(oid)
            earliest[f.destination]=min(earliest.get(f.destination,o.arr),o.arr)
        ordered=reachable
        eligible={oid:eligible[oid] for oid in ordered}
        starts=[oid for oid in ordered if flights[eligible[oid].flight_id].origin==tail.initial_station]
        edges=defaultdict(list)
        for oid in ordered if connect else []:
            left=eligible[oid]
            station=flights[left.flight_id].destination
            values=by_origin[station]
            if not values:
                continue
            for right in values[bisect_left(origin_times[station],left.arr):]:
                if right.option_id not in eligible or right.flight_id==left.flight_id:
                    continue
                turn=min(50,data.original_turn_minutes.get(f"{left.flight_id}#{right.flight_id}",50))
                if right.dep>=left.arr+timedelta(minutes=turn):
                    edges[oid].append(right.option_id)
        result[tail.tail_id]={"options":eligible,"ordered":ordered,"starts":starts,"edges":dict(edges)}
    return result


def enumerate_paths(network: dict, limit: int) -> list[tuple[str,...]]:
    paths=[]
    def visit(path):
        paths.append(tuple(path))
        if len(paths)>limit:
            raise ValueError("oracle_path_limit exceeded; use joint_arc_flow or column generation")
        for nxt in network["edges"].get(path[-1],[]):
            visit([*path,nxt])
    for start in network["starts"]:
        visit([start])
    return paths
