"""Memory-admitted, nested HiGHS joint MIPs; restricted bounds stay local."""
from __future__ import annotations

from bisect import bisect_left
from collections import Counter, defaultdict
from datetime import timedelta
from time import perf_counter
import gc
import os

from .algorithms import Budget, Outcome, direct, schedule_precheck, interruptible
from .rules import adjustable, iter_networks, tail_pools
from backend.solver.runtime import check_budget, SolveBudget, use_budget

GIB=1024**3


def estimate_size(request,options):
    """Stream tail networks; deliberately never construct the whole MIP to size it.

    Counts are structural upper estimates, not a mathematical RAM guarantee.
    A calibrated multiplier and an OS process-tree hard limit are both required.
    """
    data=request.dataset
    flights={f.flight_id:f for f in data.flights}
    links=defaultdict(set)
    for key,turn in data.original_turn_minutes.items():
        if turn<50:
            a,b=key.split('#'); links[a].add(b)
    for a,b in data.connected_pairs:
        links[a].add(b)
    assignments=events=channel_vars=channel_rows=0
    for tail,net in iter_networks(data,options,connect=False,pools=tail_pools(data,request.tail_pool_size)):
        check_budget()
        assignments+=len(net['ordered'])
        local=defaultdict(list)
        station_times=defaultdict(set)
        for o in net['options'].values():
            f=flights[o.flight_id]
            local[o.flight_id].append(o)
            station_times[f.origin].add(o.dep)
            station_times[f.destination].add(o.arr+timedelta(minutes=50))
        events+=sum(len(times) for times in station_times.values())+1
        for left,lefts in list(local.items()):
            for right in links[left]:
                rights=local.get(right,[])
                if not rights or flights[left].destination!=flights[right].origin:
                    continue
                turn=min(50,data.original_turn_minutes.get(left+'#'+right,50))
                latest=max(o.dep for o in rights)
                releases=[o.arr+timedelta(minutes=turn) for o in lefts if o.arr+timedelta(minutes=turn)<=latest]
                if not releases:
                    continue
                departures=[o.dep for o in rights if o.dep>=min(releases)]
                nodes=len(set(releases)|set(departures))
                channel_vars+=len(releases)+len(departures)+max(0,nodes-1)
                channel_rows+=nodes
    by_route=defaultdict(list)
    own=Counter()
    for o in options:
        if not o.cancelled:
            f=flights[o.flight_id]
            by_route[f.origin,f.destination].append(o.dep)
            own[f.flight_id]+=1
    for values in by_route.values():
        values.sort()
    signs=0
    for f in data.flights:
        if adjustable(data,f):
            deps=by_route[f.origin,f.destination]
            signs+=len(deps)-bisect_left(deps,f.sched_dep)-own[f.flight_id]
    operated=sum(not o.cancelled for o in options)
    parking=sum(s.kind=='parking' for s in data.scenes)*len(data.aircraft)
    variables=len(options)+4*assignments+events+channel_vars+signs+operated+16*len(flights)+4*parking
    constraints=4*assignments+events+channel_rows+signs+operated+32*len(flights)+11*parking+len(data.transfers)*3
    # Python objects, native model copies and LP factorization all matter.
    # Pilot runs calibrate this forecast upward; the supervisor is authoritative.
    factor=max(1.0,float(os.environ.get('XMA_MEMORY_CALIBRATION','1')))
    estimated=int((256*1024**2+variables*1800+constraints*1200)*factor)
    return dict(flight_options=len(options),assignment_options=assignments,station_events=events,
                shortcut_variables=channel_vars,rebooking_variables=signs,
                estimated_variables=variables,estimated_constraints=constraints,
                estimated_peak_bytes=estimated,calibration_factor=factor,
                estimator_version='xma-compact-structural-v1',tail_pool_size=request.tail_pool_size)


def solve_stage(request,options,child):
    control=SolveBudget(child.remaining(),child.cancel_check)
    control.reserve=0
    with use_budget(control):
        return direct(request,options,child,skip_precheck=True)


@interruptible
def first_solution(request,options,budget):
    stages=[]
    conflict=schedule_precheck(request,options,budget)
    if conflict:
        return Outcome('infeasible',reason='certified_master_infeasible',statistics={'schedule_precheck':conflict})
    largest=max(Counter(a.equipment for a in request.dataset.aircraft).values())
    sizes=[]
    size=1
    while size<largest:
        sizes.append(size);size*=2
    sizes.append(None)
    memory_limit=6*GIB*.8
    full_lower=None
    last_outcome=None
    for size in sizes:
        if budget.stopped():
            break
        scope='full' if size is None else f'tail_pool_{size}'
        budget.search_scope=scope
        current=request.model_copy(update={'tail_pool_size':size,'first_solution_search':False})
        sizing_started=perf_counter()
        scale=estimate_size(current,options)
        stage={'scope':scope,'scale':scale,'sizing_seconds':perf_counter()-sizing_started}
        stages.append(stage)
        budget.emit('sizing','model_size_estimate','联合模型资源预测',metrics={**scale,'search_scope':scope,'bound_scope':'restricted' if size else 'global'})
        if scale['estimated_peak_bytes']>memory_limit:
            stage.update(status='resource_limited',reason='predicted_memory_exceeds_admission')
            budget.emit('resource','resource_limited','该搜索范围超过内存准入预测，保留已有合法方案',metrics=stage)
            # Larger neighborhoods contain this one and cannot be admitted by
            # this monotone structural estimator. Do not build them speculatively.
            break
        cap=min(600,request.time_limit_seconds*.1) if size==1 else min(1800,budget.remaining()/2)
        if size is None:
            cap=budget.remaining()
        child=Budget(min(cap,budget.remaining()),event_sink=lambda event:budget.event_sink({**event,
            'metrics':{**event.get('metrics',{}),'search_scope':scope}}),cancel_check=budget.stopped)
        child.start_decisions=budget.best.decisions if budget.best else None
        child.incumbent_sink=lambda outcome:budget.audited(outcome.decisions,outcome.objective,outcome.lower)
        last_outcome=solve_stage(current,options,child)
        stage.update(status=last_outcome.status,reason=last_outcome.reason,statistics=last_outcome.statistics,
                     elapsed_seconds=perf_counter()-child.started,objective=last_outcome.objective)
        if last_outcome.decisions:
            budget.audited(last_outcome.decisions,last_outcome.objective,last_outcome.lower)
        if size is None:
            full_lower=last_outcome.lower
            if last_outcome.status in ('optimal','infeasible'):
                last_outcome.statistics['search_stages']=stages
                return last_outcome
        gc.collect()
    # If expansion was rejected, spend the remaining time on the largest
    # admitted neighborhood, not repeatedly rebuilding impossible models.
    admitted=[s for s in stages if s.get('reason')!='predicted_memory_exceeds_admission']
    if admitted and not budget.stopped() and (not last_outcome or last_outcome.reason!='restricted_optimal'):
        stage=admitted[-1]
        size=stage['scale']['tail_pool_size']
        budget.search_scope=stage['scope']
        current=request.model_copy(update={'tail_pool_size':size,'first_solution_search':False})
        child=Budget(budget.remaining(),event_sink=lambda event:budget.event_sink({**event,
            'metrics':{**event.get('metrics',{}),'search_scope':budget.search_scope}}),cancel_check=budget.stopped)
        child.start_decisions=budget.best.decisions if budget.best else None
        child.incumbent_sink=lambda outcome:budget.audited(outcome.decisions,outcome.objective,outcome.lower)
        last_outcome=solve_stage(current,options,child)
        stages.append(dict(scope=stage['scope'],continuation=True,status=last_outcome.status,reason=last_outcome.reason,
                           statistics=last_outcome.statistics,elapsed_seconds=perf_counter()-child.started))
        if last_outcome.decisions:
            budget.audited(last_outcome.decisions,last_outcome.objective,last_outcome.lower)
        if size is None:
            full_lower=last_outcome.lower
            if last_outcome.status in ('optimal','infeasible'):
                last_outcome.statistics['search_stages']=stages
                return last_outcome
    best=budget.best
    reason='cancelled' if budget.cancel_check() else 'total_time_limit' if budget.stopped() else 'resource_limited_search_scope'
    return Outcome('aborted' if budget.cancel_check() else 'not_converged',best.objective if best else None,
                   full_lower,best.upper if best else None,list(best.decisions) if best else [],reason,
                   {'search_stages':stages,'full_model_built':any(s['scope']=='full' and s.get('status')!='resource_limited' for s in stages),
                    'bound_scope':'global','memory_limit_gib':6})
