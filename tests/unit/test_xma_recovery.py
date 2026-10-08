from datetime import datetime, timedelta, timezone

import pytest

from backend.business.xma.algorithms import Budget, benders, direct
from backend.business.xma.evaluator import evaluate, export_csv
from backend.business.xma.importer import load_workbook, preview
from backend.business.xma.objectives import normal_delay_cost, rebook_delay_cost
from backend.business.xma.rules import generate_options
from backend.business.xma.schema import Decision, SourceRef, XmaAircraft, XmaDataset, XmaFlight, XmaSolveRequest
from backend.business.xma.schema import Scene


def micro_request(objective="tianchi_2017"):
    time=datetime(2017,5,6,8,tzinfo=timezone(timedelta(hours=8)))
    def flight(fid,origin,destination,minute):
        return XmaFlight(flight_id=fid,date="2017-05-06",flight_no=fid,domestic=True,origin=origin,destination=destination,
            sched_dep=time+timedelta(minutes=minute),sched_arr=time+timedelta(minutes=minute+60),
            original_aircraft="T",equipment="E",passengers=5,through_passengers=0,seats=8,importance=1,
            source=SourceRef(sheet="航班",row=int(fid)+1))
    data=XmaDataset(dataset_id="micro",source_sha256="test",adjustment_start=time-timedelta(hours=1),adjustment_end=time+timedelta(days=1),
        flights=[flight("1","A","B",0),flight("2","B","A",90)],
        aircraft=[XmaAircraft(tail_id="T",equipment="E",seats=8,initial_station="A",original_terminal="A",original_rotation=["1","2"])],
        airports={"A":True,"B":True},route_prohibitions=[],closures=[],scenes=[],travel_minutes={},transfers=[],connected_pairs=[],
        original_turn_minutes={"1#2":30},movement_windows=[])
    return XmaSolveRequest(dataset=data,objective_profile=objective,maximum_delay_minutes=30,delay_step_minutes=30,time_limit_seconds=30)


def test_real_workbook_structure():
    data=load_workbook()
    counts=preview(data)["counts"]
    assert counts=={"flights":2364,"aircraft":142,"airports":79,"equipment_types":4,"route_prohibitions":8693,
        "closures":6,"scenes":11,"travel_times":8703,"transfers":773,"connected_pairs":616,
        "oversold_flights":48,"short_original_turns":212}
    assert data.flights[0].source.row==2
    assert data.flights[0].sched_dep.utcoffset()==timedelta(hours=8)


@pytest.mark.parametrize("hours,value",[(0,0),(2,1),(2.01,1.5),(4,1.5),(8,2),(36,3),(36.01,1e9)])
def test_normal_cost_boundaries(hours,value):
    assert normal_delay_cost(hours)==value


@pytest.mark.parametrize("hours,value",[(0,0),(6,6/24),(12,12/24),(24,24/18),(36,36/16),(48,3),(48.01,1e9)])
def test_sign_cost_boundaries(hours,value):
    assert rebook_delay_cost(hours)==value


@pytest.mark.parametrize("objective",["tianchi_2017","air_linear_v1"])
def test_all_architectures_agree(objective):
    req=micro_request(objective)
    options=generate_options(req)
    outcomes=[direct(req,options,Budget(30)),direct(req,options,Budget(30),oracle=True),
        benders(req,options,Budget(30)),benders(req,options,Budget(30),use_cg=True)]
    assert [r.status for r in outcomes]==["optimal"]*4
    assert [r.objective for r in outcomes]==pytest.approx([0]*4)
    for result in outcomes:
        assert evaluate(req,result.decisions)["valid"]
        assert all(len(row.split(","))==11 for row in export_csv(req,result.decisions).splitlines())


def test_objectives_are_independent():
    req=micro_request()
    req.dataset.flights[0].passengers=12
    # Overflow is an explicit passenger cancellation, not invalid source data.
    options=generate_options(req)
    result=direct(req,options,Budget(30))
    assert result.status=="optimal"
    assert result.objective==16
    air=req.model_copy(update={"objective_profile":"air_linear_v1"})
    other=direct(air,generate_options(air),Budget(30))
    assert other.objective==10000
    assert evaluate(req,result.decisions)["passenger_ledger"][0]["occupied_seats"]==8


def test_disruption_nonzero_cost_all_algorithms():
    req=micro_request()
    first=req.dataset.flights[0]
    req.dataset.scenes=[Scene(airport="B",kind="arrival",start=first.sched_arr-timedelta(minutes=30),
        end=first.sched_arr+timedelta(minutes=30),source=SourceRef(sheet="台风场景",row=2))]
    options=generate_options(req)
    outcomes=[direct(req,options,Budget(30)),direct(req,options,Budget(30),oracle=True),
        benders(req,options,Budget(30)),benders(req,options,Budget(30),use_cg=True)]
    assert [o.status for o in outcomes]==["optimal"]*4
    assert [o.objective for o in outcomes]==pytest.approx([110]*4)
    assert outcomes[-1].statistics["cg_iterations"]>0


def test_split_rebooking():
    req=micro_request()
    a,b=req.dataset.flights
    a.passengers=12
    third=a.model_copy(update={"flight_id":"3","flight_no":"3","original_aircraft":"U","seats":12,"passengers":0,
        "sched_dep":a.sched_dep+timedelta(hours=2),"sched_arr":a.sched_arr+timedelta(hours=2)})
    fourth=b.model_copy(update={"flight_id":"4","flight_no":"4","original_aircraft":"U","seats":12,"passengers":0,
        "sched_dep":b.sched_dep+timedelta(hours=2),"sched_arr":b.sched_arr+timedelta(hours=2)})
    req.dataset.flights.extend([third,fourth])
    req.dataset.aircraft.append(XmaAircraft(tail_id="U",equipment="E",seats=12,initial_station="A",original_terminal="A",original_rotation=["3","4"]))
    req.dataset.original_turn_minutes["3#4"]=30
    req.maximum_delay_minutes=0
    options=generate_options(req)
    results=[direct(req,options,Budget(30)),benders(req,options,Budget(30),use_cg=True)]
    assert [r.objective for r in results]==pytest.approx([4*2/30]*2)
    for result in results:
        audit=evaluate(req,result.decisions)
        assert audit["valid"]
        assert next(d for d in result.decisions if d.flight_id=="1").rebook=={"3":4}
        assert sum(x["unserved"] for x in audit["passenger_ledger"])==0


def test_highs_fallback_matches_gurobi(monkeypatch):
    import backend.business.xma.model as module
    original=module.new_model
    def highs_model(name):
        model,env=original(name)
        model.highs=True
        return model,env
    monkeypatch.setattr(module,"new_model",highs_model)
    req=micro_request()
    req.dataset.flights[0].passengers=12
    options=generate_options(req)
    outcome=direct(req,options,Budget(30))
    cg=benders(req,options,Budget(30),use_cg=True)
    assert outcome.status==cg.status=="optimal"
    assert outcome.objective==cg.objective==16
    assert outcome.statistics["solver"]=="HiGHS"


def test_branch_and_price_reprices_fractional_assignment_nodes():
    from backend.business.xma.algorithms import branch_and_price
    req=micro_request('air_linear_v1')
    req.air_objective.aircraft_reassignment=10
    req.dataset.flights[0].passengers=11
    a,b=req.dataset.flights
    req.dataset.flights.extend([f.model_copy(update={'flight_id':str(i),'flight_no':str(i),'original_aircraft':'U',
        'seats':12,'passengers':0,'sched_dep':f.sched_dep+timedelta(hours=2),'sched_arr':f.sched_arr+timedelta(hours=2)})
        for i,f in ((3,a),(4,b))])
    req.dataset.aircraft.append(XmaAircraft(tail_id='U',equipment='E',seats=12,initial_station='A',original_terminal='A',original_rotation=['3','4']))
    req.dataset.original_turn_minutes['3#4']=30
    req.maximum_delay_minutes=0
    options=generate_options(req)
    schedule={o.option_id for o in options if not o.cancelled}
    benchmark=direct(req,options,Budget(30),schedule=schedule,oracle=True)
    outcome=branch_and_price(req,options,schedule,Budget(30))
    assert outcome.status==benchmark.status=='optimal'
    assert outcome.objective==pytest.approx(benchmark.objective)
    assert outcome.statistics['bp_nodes']>1
    assert outcome.statistics['root_lp_bound']<outcome.objective
    req.max_bp_nodes=1
    limited=branch_and_price(req,options,schedule,Budget(30))
    assert limited.status=='not_converged'
    assert limited.lower<=outcome.objective


def test_connected_shortcut_boards_its_own_flight():
    req=micro_request()
    req.dataset.connected_pairs=[('1','2')]
    a,b=req.dataset.flights
    a.through_passengers=b.through_passengers=1
    # Competing departure at the exact connected leg time must not use its shortcut.
    third=b.model_copy(update={'flight_id':'3','flight_no':'3','original_aircraft':'U','through_passengers':0,
        'sched_dep':b.sched_dep,'sched_arr':b.sched_arr,'origin':'B','destination':'C'})
    req.dataset.flights.append(third)
    req.dataset.aircraft.append(XmaAircraft(tail_id='U',equipment='E',seats=8,initial_station='B',original_terminal='C',original_rotation=['3']))
    req.dataset.airports['C']=True
    options=generate_options(req)
    arc=direct(req,options,Budget(30))
    oracle=direct(req,options,Budget(30),oracle=True)
    assert arc.status==oracle.status=='optimal'
    assert arc.objective==oracle.objective
    assert evaluate(req,arc.decisions)['valid']


def test_input_rejects_stale_original_turn_exception():
    from backend.business.xma.service import precheck
    req=micro_request()
    req.dataset.original_turn_minutes['1#2']=10
    assert not precheck(req)['solve_ready']


def test_budget_exhausted_during_build_is_not_optimal():
    req=micro_request()
    outcome=direct(req,generate_options(req),Budget(0))
    assert outcome.status=='not_converged'
    assert outcome.lower is None and not outcome.decisions
