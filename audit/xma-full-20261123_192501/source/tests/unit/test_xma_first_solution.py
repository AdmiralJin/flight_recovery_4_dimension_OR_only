from datetime import datetime, timedelta, timezone

import pytest

from backend.business.xma import algorithms
from backend.business.xma.algorithms import Budget, direct
from backend.business.xma.evaluator import evaluate
from backend.business.xma.model import build_joint, decisions_from_model
from backend.business.xma.rules import generate_options, tail_pools
from backend.business.xma.schema import XmaSolveRequest, XmaDataset, XmaFlight, XmaAircraft, SourceRef, Scene
from backend.business.xma.service import solve, study_signature
from backend.business.xma.solver import EXPLICIT_BACKEND, ScalableModel, SolutionAuditError


def sample():
    t=datetime(2017,5,6,8,tzinfo=timezone(timedelta(hours=8)))
    flights=[XmaFlight(flight_id=str(i+1),date='2017-05-06',flight_no=str(i+1),domestic=True,
        origin=a,destination=b,sched_dep=t+timedelta(minutes=m),sched_arr=t+timedelta(minutes=m+60),
        original_aircraft='T',equipment='E',passengers=5,through_passengers=1,seats=8,importance=1,
        source=SourceRef(sheet='航班',row=i+2)) for i,(a,b,m) in enumerate([('A','B',0),('B','A',90)])]
    data=XmaDataset(dataset_id='first-solution-test',source_sha256='fixture',
        adjustment_start=t-timedelta(hours=1),adjustment_end=t+timedelta(days=1),flights=flights,
        aircraft=[XmaAircraft(tail_id='T',equipment='E',seats=8,initial_station='A',original_terminal='A',original_rotation=['1','2'])],
        airports={'A':True,'B':True},route_prohibitions=[],closures=[],scenes=[],travel_minutes={},transfers=[],
        connected_pairs=[('1','2')],original_turn_minutes={'1#2':30},movement_windows=[])
    return XmaSolveRequest(dataset=data,solver_backend='highs',maximum_delay_minutes=60,time_limit_seconds=15)


@pytest.fixture(autouse=True)
def explicit_highs():
    token=EXPLICIT_BACKEND.set('highs')
    yield
    EXPLICIT_BACKEND.reset(token)


def test_official_delay_caps_and_deadline_without_artificial_cap():
    req=sample().model_copy(update={'maximum_delay_minutes':None,'delay_step_minutes':70})
    req.dataset.flights[1].domestic=False
    options=generate_options(req)
    assert max(o.delay for o in options if o.flight_id=='1')==1440
    assert max(o.delay for o in options if o.flight_id=='2')==2160
    end=req.dataset.flights[0].sched_arr+timedelta(minutes=137)
    req.recovery_end=end
    options=generate_options(req)
    assert max(o.delay for o in options if o.flight_id=='1')==137
    assert all(o.cancelled or o.arr<=end for o in options)
    assert XmaSolveRequest.model_validate(req.model_dump()).maximum_delay_minutes is None


@pytest.mark.parametrize('connected',[True,False])
def test_compressed_channel_matches_legacy_and_oracle(connected):
    req=sample().model_copy(update={'maximum_delay_minutes':300})
    if not connected:
        req.dataset.connected_pairs=[]
        for f in req.dataset.flights:f.through_passengers=0
    options=generate_options(req)
    results=[]
    counts=[]
    for compact in (False,True):
        joint=build_joint(req,options,compact_connections=compact)
        try:
            Budget(15).optimize(joint.model,mip=True)
            decisions=decisions_from_model(joint)
            audit=evaluate(req,decisions)
            assert audit['valid']
            results.append(audit['objective'])
            counts.append(joint.model.NumVars)
        finally:joint.close()
    oracle=direct(req,options,Budget(15),oracle=True)
    assert results[0]==pytest.approx(results[1])==pytest.approx(oracle.objective)
    assert counts[1]<counts[0]


def test_live_checkpoint_exists_before_native_solve_returns(monkeypatch):
    running=False
    original=ScalableModel._run_highs
    def wrapped(*args,**kwargs):
        nonlocal running
        running=True
        try:return original(*args,**kwargs)
        finally:running=False
    monkeypatch.setattr(ScalableModel,'_run_highs',wrapped)
    checkpoints=[]
    def save(value):
        if value.get('checkpoint'):
            assert value['independent_audit']['valid']
            checkpoints.append((running,value))
    result=solve(sample(),solution_artifact_sink=save)
    assert checkpoints and checkpoints[0][0] and result['independent_audit']['valid']
    assert checkpoints[-1][1]['objective']==pytest.approx(result['objective']['total'])


def test_cancellation_retains_live_audited_solution():
    stop=False
    checkpoints=[]
    def save(value):
        nonlocal stop
        if value.get('checkpoint'):
            checkpoints.append(value);stop=True
    result=solve(sample(),cancel_check=lambda:stop,solution_artifact_sink=save)
    assert checkpoints and result['business_decisions']
    assert result['independent_audit']['valid']
    assert result['status']=='aborted'


def test_failed_live_audit_is_not_retried_or_published(monkeypatch):
    monkeypatch.setattr(algorithms,'evaluate',lambda *a,**k:{'valid':False,'violations':['injected audit failure']})
    saved=[]
    with pytest.raises(SolutionAuditError,match='injected audit failure'):
        solve(sample(),solution_artifact_sink=saved.append)
    assert not saved


def test_restricted_optimum_does_not_become_global_optimum():
    req=sample().model_copy(update={'tail_pool_size':1})
    result=solve(req)
    assert result['independent_audit']['valid']
    assert result['status']=='not_converged'
    assert result['diagnostics']['lower_bound'] is None
    assert result['diagnostics']['relative_gap'] is None
    assert result['diagnostics']['statistics']['restricted_optimal']


def test_necessary_condition_infeasibility_has_no_zero_solution_metrics():
    req=sample()
    req.dataset.adjustment_start=req.dataset.flights[0].sched_dep+timedelta(minutes=1)
    f=req.dataset.flights[1]
    req.dataset.scenes=[Scene(airport=f.origin,kind='departure',start=f.sched_dep-timedelta(minutes=1),
        end=f.sched_dep+timedelta(days=2),source=SourceRef(sheet='台风场景',row=2))]
    result=solve(req)
    assert result['status']=='infeasible'
    assert result['objective'] is None
    assert result['metrics']['operated_flights'] is None
    assert not result['business_decisions']


def test_audit_enforces_configured_delay_and_recovery_deadline():
    req=sample()
    result=solve(req)
    from backend.business.xma.schema import Decision
    decisions=[Decision.model_validate(d) for d in result['business_decisions']]
    first=decisions[0]
    first.dep+=timedelta(minutes=90);first.arr+=timedelta(minutes=90)
    req.recovery_end=first.arr-timedelta(minutes=1)
    violations=evaluate(req,decisions)['violations']
    assert any('configured delay limit' in e for e in violations)
    assert any('recovery deadline' in e for e in violations)


def test_signature_hashes_problem_data_and_not_algorithm_budget():
    req=sample()
    original=study_signature(req)
    assert original==study_signature(req.model_copy(update={'time_limit_seconds':99,'algorithm':'joint_path_oracle'}))
    assert original!=study_signature(req.model_copy(update={'tail_pool_size':1}))
    req.dataset.movement_limit+=1
    assert original!=study_signature(req)


def test_first_solution_route_can_prove_small_full_model():
    req=sample().model_copy(update={'first_solution_search':True,'max_assignment_options':None})
    result=solve(req)
    assert result['status']=='optimal' and result['independent_audit']['valid']
    assert result['diagnostics']['lower_bound']==pytest.approx(result['objective']['total'])


def test_pool_growth_is_nested():
    req=sample()
    req.dataset.aircraft=[req.dataset.aircraft[0].model_copy(update={'tail_id':str(i)}) for i in range(9)]
    for size in (1,2,4,8):
        a,b=tail_pools(req.dataset,size),tail_pools(req.dataset,size*2)
        assert all(a[tid]<=b[tid] for tid in a)


def two_tail_sample():
    req=sample()
    third=req.dataset.flights[1].model_copy(update={'flight_id':'3','flight_no':'3','original_aircraft':'U',
        'through_passengers':0,'origin':'B','destination':'C'})
    req.dataset.flights.append(third)
    req.dataset.aircraft.append(XmaAircraft(tail_id='U',equipment='E',seats=8,initial_station='B',original_terminal='C',original_rotation=['3']))
    req.dataset.airports['C']=True
    return req.model_copy(update={'first_solution_search':True})


def test_nested_search_submits_previous_audited_solution_as_highs_start():
    events=[]
    result=solve(two_tail_sample(),event_sink=events.append)
    assert result['status']=='optimal' and result['independent_audit']['valid']
    starts=[e for e in events if e['type']=='mip_start']
    assert starts and starts[0]['metrics']['start_columns']>0
    assert starts[0]['metrics']['start_status']=='HighsStatus.kOk'


def test_memory_rejection_keeps_restricted_ub_and_no_global_lb(monkeypatch):
    from backend.business.xma import search
    monkeypatch.setenv('XMA_MEMORY_GIB','12')
    original=search.estimate_size
    def size(req,options):
        result=original(req,options)
        if req.tail_pool_size is None:result['estimated_peak_bytes']=9*1024**3
        return result
    monkeypatch.setattr(search,'estimate_size',size)
    result=solve(two_tail_sample())
    assert result['status']=='not_converged' and result['independent_audit']['valid']
    assert result['diagnostics']['lower_bound'] is None
    assert result['diagnostics']['relative_gap'] is None
    stats=result['diagnostics']['statistics']
    assert stats['memory_limit_gib']==12
    assert stats['admission_bytes']==int(12*1024**3*.70)
    assert not stats['full_model_built']
    assert stats['search_stages'][-1]['status']=='resource_limited'
