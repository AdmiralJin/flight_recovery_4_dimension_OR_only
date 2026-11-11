from __future__ import annotations

import heapq
import math
from dataclasses import dataclass, field
from time import perf_counter
from functools import wraps
from backend.solver.runtime import ACTIVE_BUDGET, SolveBudget, SolveStopped, check_budget, use_budget

import gurobipy as gp
from gurobipy import GRB

from .evaluator import evaluate
from .model import add_path, add_schedule_rows, build_joint, decisions_from_model, new_model, path_coefficients
from .objectives import schedule_cost
from .schema import Decision, Option, XmaSolveRequest
from .solver import value

TOL=1e-6


@dataclass
class Outcome:
    status: str
    objective: float | None = None
    lower: float | None = None
    upper: float | None = None
    decisions: list[Decision] = field(default_factory=list)
    reason: str = "unknown"
    statistics: dict = field(default_factory=dict)


class Budget:
    def __init__(self, seconds, event_sink=None, cancel_check=None):
        self.started=perf_counter()
        self.seconds=seconds
        self.event_sink=event_sink or (lambda event:None)
        self.cancel_check=cancel_check or (lambda:False)
        self.best=None
        self.incumbent_sink=None

    def remaining(self):
        return max(0,self.seconds-(perf_counter()-self.started))

    def stopped(self):
        return self.remaining()<=0 or self.cancel_check()

    def emit(self,stage,event_type,message,**kw):
        lower,upper=kw.get("lower_bound"),kw.get("upper_bound")
        if lower is not None and upper is not None and math.isfinite(lower) and math.isfinite(upper):
            kw.setdefault("absolute_gap",max(0,upper-lower))
            kw.setdefault("relative_gap",max(0,upper-lower)/max(1,abs(upper)))
        self.event_sink({"stage":stage,"type":event_type,"message":message,**kw})

    def optimize(self,model, *, mip=False, gap=0, scope="subproblem"):
        if self.stopped():
            return False
        model.Params.TimeLimit=max(0.001,self.remaining())
        if mip:
            model.Params.MIPGap=gap
        self.emit("optimization","solver_selected","Gurobi selected as the primary solver.",metrics={"solver":"Gurobi","live_bounds_available":bool(mip)})
        model.cancel_check=self.stopped
        model.progress_sink=lambda event_type,message,metrics,lower_bound=None,upper_bound=None:self.emit(
            "optimization",event_type,message,metrics={**metrics,"bound_scope":scope},lower_bound=lower_bound,upper_bound=upper_bound)
        def callback(m,where):
            if self.stopped():
                m.terminate()
            if where==GRB.Callback.MIP:
                lb=m.cbGet(GRB.Callback.MIP_OBJBND)
                ub=m.cbGet(GRB.Callback.MIP_OBJBST)
                now=perf_counter()
                if now-getattr(self,"last_trace",0)>1:
                    self.last_trace=now
                    self.emit("optimization","mip_progress","联合模型求解",lower_bound=lb if abs(lb)<1e90 else None,
                        upper_bound=ub if abs(ub)<1e90 else None,metrics={"solver":"Gurobi",
                            "node_count":m.cbGet(GRB.Callback.MIP_NODCNT),"solver_runtime_seconds":m.cbGet(GRB.Callback.RUNTIME),
                            "live_bounds_available":True,"has_incumbent":abs(ub)<1e90,"bound_scope":scope})
        model.optimize(callback if mip else lambda m,w: m.terminate() if self.stopped() else None)
        return True

    def audited(self,decisions,objective,lower=None):
        if self.best is not None and objective>=self.best.objective-TOL:
            return
        self.best=Outcome("not_converged",objective,lower,objective,list(decisions),"audited_incumbent_checkpoint")
        if self.incumbent_sink:
            self.incumbent_sink(self.best)
        self.emit("audit","incumbent_audited","完整方案已通过独立审计",upper_bound=objective,lower_bound=lower)


def original_tail_candidate(request,options,schedule=None):
    """Cheap primal heuristic; a complete independent audit is mandatory."""
    from collections import defaultdict
    from datetime import timedelta
    by_flight=defaultdict(list)
    for option in options:
        if schedule is None or option.option_id in schedule:
            by_flight[option.flight_id].append(option)
    flights={f.flight_id:f for f in request.dataset.flights}
    decisions=[]
    for aircraft in request.dataset.aircraft:
        station=aircraft.initial_station
        last=None
        for fid in aircraft.original_rotation:
            check_budget()
            flight=flights[fid]
            allowed=[]
            for option in by_flight[fid]:
                turn=min(50,request.dataset.original_turn_minutes.get(f"{last.flight_id}#{fid}",50)) if last else 0
                if option.cancelled or (flight.origin==station and (last is None or option.dep>=last.arr+timedelta(minutes=turn))):
                    allowed.append(option)
            if not allowed:
                return None
            option=min(allowed,key=lambda o:(o.cancelled,o.delay,o.option_id))
            decisions.append(Decision(flight_id=fid,option_id=option.option_id,aircraft_id=aircraft.tail_id,
                                      cancelled=option.cancelled,dep=option.dep,arr=option.arr,rebook={}))
            if not option.cancelled:
                station=flight.destination
                last=option
    audit=evaluate(request,decisions)
    if not audit["valid"]:
        return None
    return Outcome("not_converged",audit["objective"],None,audit["objective"],decisions,"audited_original_tail_heuristic")


def interruptible(fn):
    @wraps(fn)
    def run(request,options,budget,*args,**kwargs):
        active=ACTIVE_BUDGET.get()
        control=active or SolveBudget(budget.remaining(),budget.cancel_check)
        # XMA's own budget already reserves no extra solver time.
        if active is None:
            control.reserve=0
        resource_start=len(control.resources)
        with use_budget(control):
            try:
                check_budget()
                return fn(request,options,budget,*args,**kwargs)
            except SolveStopped as exc:
                best=budget.best
                if best:
                    return Outcome("aborted" if str(exc)=="cancelled" else "not_converged",best.objective,
                                   best.lower,best.upper,best.decisions,str(exc))
                return Outcome("aborted" if str(exc)=="cancelled" else "not_converged",reason=str(exc))
            finally:
                for close in reversed(control.resources[resource_start:]):
                    close()
                del control.resources[resource_start:]
    return run


def schedule_precheck(request,options,budget):
    """Necessary schedule constraints only; feasibility does not certify recourse."""
    model,env=new_model("xma_necessary_schedule")
    try:
        x={o.option_id:model.addVar(vtype=GRB.BINARY,name="x:"+o.option_id) for o in options}
        add_schedule_rows(model,request,options,x)
        model.setObjective(0)
        if not budget.optimize(model,mip=True,scope="necessary_conditions"):
            return None
        if model.Status==GRB.INFEASIBLE:
            return {"certificate":"necessary_schedule_master_infeasible", "constraints":model.NumConstrs,
                    "variables":model.NumVars,"conflict_rows":model.conflict_rows(),
                    "full_resource_model_built":False}
        return None
    finally:
        model.dispose(); env.dispose()


@interruptible
def direct(request: XmaSolveRequest,options:list[Option],budget:Budget, *, schedule=None,oracle=False) -> Outcome:
    if schedule is None:
        conflict=schedule_precheck(request,options,budget)
        if conflict:
            return Outcome("infeasible",reason="certified_master_infeasible",statistics={"schedule_precheck":conflict})
    budget.emit("model","building_model","建立显式航班串基准" if oracle else "建立飞机网络流联合模型")
    build_started=perf_counter()
    joint=build_joint(request,options,representation="path" if oracle else "arc",schedule=schedule,enumerate_all=oracle)
    try:
        budget.emit("model","model_built","联合约束已建立",metrics={"variables":joint.model.NumVars,"constraints":joint.model.NumConstrs,"build_seconds":perf_counter()-build_started})
        optimized=budget.optimize(joint.model,mip=True,gap=request.mip_gap,scope="global" if schedule is None else "subproblem")
        m=joint.model
        stats={"variables":m.NumVars,"constraints":m.NumConstrs,"nodes":m.NodeCount if optimized and m.IsMIP else 0,
            "aircraft_columns":len(joint.paths),"representation":"path" if oracle else "arc",
            "solver":m.solver_name if m.highs else "Gurobi"}
        if not optimized:
            return Outcome("aborted" if budget.cancel_check() else "not_converged",reason="budget_exhausted_during_build",statistics=stats)
        if m.SolCount:
            decisions=decisions_from_model(joint)
            audit=evaluate(request,decisions)
            if not audit["valid"] or abs(audit["objective"]-m.ObjVal)>max(TOL,abs(m.ObjVal)*1e-8):
                raise ValueError(f"independent joint audit failed: {audit['violations']}; score={audit.get('objective')} model={m.ObjVal}")
            exact=m.Status==GRB.OPTIMAL and m.ObjBound is not None and abs(m.ObjVal-m.ObjBound)<=max(TOL,abs(m.ObjVal)*1e-8)
            budget.audited(decisions,m.ObjVal,m.ObjBound if schedule is None else None)
            return Outcome("optimal" if exact else "not_converged",m.ObjVal,m.ObjBound,m.ObjVal,decisions,str(m.Status),stats)
        return Outcome("infeasible" if m.Status==GRB.INFEASIBLE else "aborted" if budget.cancel_check() else "not_converged",
            lower=m.ObjBound if m.IsMIP and m.Status not in (GRB.LOADED,GRB.INFEASIBLE) else None,reason=str(m.Status),statistics=stats)
    finally:
        joint.close()


def price(joint,tail,duals):
    """Exact shortest path on the fixed-schedule DAG; never enumerates paths."""
    net=joint.networks[tail]
    data=joint.request.dataset
    flights={f.flight_id:f for f in data.flights}
    aircraft=next(a for a in data.aircraft if a.tail_id==tail)
    distance={}
    predecessor={}
    for oid in net["starts"]:
        distance[oid]=-duals["select",tail]-duals["u",tail,oid]
        predecessor[oid]=None
    best=math.inf
    best_end=None
    for oid in net["ordered"]:
        check_budget()
        if oid not in distance:
            continue
        left=net["options"][oid]
        end=flights[left.flight_id].destination
        cost=distance[oid]-duals["terminal",aircraft.equipment,end]
        if cost<best:
            best,best_end=cost,oid
        for nxt in net["edges"].get(oid,[]):
            right=net["options"][nxt]
            cost=distance[oid]-duals["u",tail,nxt]
            key=("connected",left.flight_id,right.flight_id)
            cost-=duals.get(key,0)
            airport=flights[right.flight_id].origin
            for s in data.scenes:
                if s.kind=="parking" and s.airport==airport and left.arr<=s.start and right.dep>=s.end:
                    cost-=duals["parking",airport]
            if cost<distance.get(nxt,math.inf)-1e-10:
                distance[nxt]=cost
                predecessor[nxt]=oid
    path=[]
    while best_end is not None:
        path.append(best_end)
        best_end=predecessor[best_end]
    return best,tuple(reversed(path))


def column_generation(request,options,schedule,budget,branch_bounds=None):
    joint=build_joint(request,options,representation="path",schedule=schedule,relax=True,branch_bounds=branch_bounds)
    model=joint.model
    for tail,net in joint.networks.items():
        if net["starts"]:
            add_path(joint,tail,(net["starts"][0],))
    model.update()
    if any(v.LB>v.UB for v in model.getVars()):
        return joint,False,"infeasible_bounds",0
    artificial=[]
    for row in model.getConstrs():
        signs=(1,-1) if row.Sense=="=" else (-1,) if row.Sense=="<" else (1,)
        for sign in signs:
            artificial.append(model.addVar(lb=0,obj=0,column=gp.Column([sign],[row]),name=f"art:{len(artificial)}"))
    model.setObjective(gp.quicksum(artificial),GRB.MINIMIZE)
    phase=1
    for iteration in range(1,request.max_cg_iterations+1):
        if not budget.optimize(model) or model.Status!=GRB.OPTIMAL:
            return joint,False,"lp_not_optimal",iteration
        duals={key:model.dual(row) for key,row in joint.path_rows.items()}
        added=0
        minimum=0.0
        for tail in joint.networks:
            rc,path=price(joint,tail,duals)
            minimum=min(minimum,rc)
            if path and rc<-1e-7:
                if (tail,path) in joint.path_variables:
                    if rc<-1e-5:
                        raise ValueError("negative reduced cost on an existing unbounded column")
                    continue
                coeff=path_coefficients(joint,tail,path)
                independent_rc=-sum(duals[k]*v for k,v in coeff.items())
                if abs(independent_rc-rc)>TOL:
                    raise ValueError("DAG pricing coefficient audit failed")
                add_path(joint,tail,path)
                added+=1
        budget.emit("column_generation","pricing_iteration",f"Phase {phase} 定价，第 {iteration} 轮",
            metrics={"phase":phase,"columns":len(joint.paths),"added":added,"minimum_reduced_cost":minimum})
        if added:
            continue
        if phase==1:
            if model.ObjVal>TOL:
                return joint,True,"certified_lp_infeasible",iteration
            for v in artificial:
                v.UB=0
            model.setObjective(joint.objective,GRB.MINIMIZE)
            phase=2
            continue
        return joint,True,"pricing_certified",iteration
    return joint,False,"cg_iteration_limit",request.max_cg_iterations


def branch_and_price(request,options,schedule,budget):
    queue=[(-math.inf,0,{})]
    sequence=0
    incumbent=original_tail_candidate(request,options,schedule) if len(request.dataset.flights)>20 else None
    if incumbent:
        budget.audited(incumbent.decisions,incumbent.objective)
    lower=None
    visited=0
    columns=0
    iterations=0
    root_lb=None
    unresolved=[]
    while queue and visited<request.max_bp_nodes and not budget.stopped():
        node_lb,_,bounds=heapq.heappop(queue)
        if incumbent and node_lb>=incumbent.objective-TOL:
            continue
        joint,certified,reason,count=column_generation(request,options,schedule,budget,bounds)
        visited+=1
        columns+=len(joint.paths)
        iterations+=count
        try:
            if reason in ("certified_lp_infeasible","infeasible_bounds"):
                continue
            if not certified:
                unresolved.append(node_lb)
                break
            value=joint.model.ObjVal
            if root_lb is None:
                root_lb=value
            if incumbent and value>=incumbent.objective-TOL:
                continue
            fractional=[v for v in joint.integer_variables if abs(joint.model.value(v)-round(joint.model.value(v)))>TOL]
            if not fractional:
                decisions=decisions_from_model(joint)
                audit=evaluate(request,decisions)
                if not audit["valid"] or abs(audit["objective"]-value)>max(TOL,abs(value)*1e-8):
                    raise ValueError("branch-and-price integer audit failed: "+str(audit["violations"]))
                incumbent=Outcome("optimal",value,value,value,decisions)
                budget.audited(decisions,value)
            else:
                assignments=[v for v in fractional if v.VarName.startswith("u:")]
                v=max(assignments or fractional,key=lambda v:min(joint.model.value(v)-math.floor(joint.model.value(v)),math.ceil(joint.model.value(v))-joint.model.value(v)))
                for lb,ub in ((v.LB,math.floor(joint.model.value(v))),(math.ceil(joint.model.value(v)),v.UB)):
                    sequence+=1
                    child=dict(bounds)
                    child[v.VarName]=(lb,ub)
                    heapq.heappush(queue,(value,sequence,child))
            budget.emit("branch_and_price","branch_node",f"分支节点 {visited}",lower_bound=value,
                upper_bound=incumbent.objective if incumbent else None,metrics={"nodes":visited,"columns":columns})
        finally:
            joint.close()
    stats={"bp_nodes":visited,"aircraft_columns":columns,"cg_iterations":iterations,"root_lp_bound":root_lb,
        "pricing_uses_enumeration":False}
    if not queue and not unresolved:
        if incumbent:
            incumbent.status="optimal"
            incumbent.lower=incumbent.upper=incumbent.objective
            incumbent.statistics=stats
            incumbent.reason="exact_branch_and_price"
            return incumbent
        return Outcome("infeasible",reason="certified_integer_infeasible",statistics=stats)
    bounds=[x[0] for x in queue]+unresolved
    lower=min(bounds) if bounds else root_lb
    if lower is not None and not math.isfinite(lower):
        lower=None
    if incumbent:
        incumbent.status="aborted" if budget.cancel_check() else "not_converged"
        incumbent.lower=lower
        incumbent.reason="bp_budget_or_node_limit"
        incumbent.statistics=stats
        return incumbent
    return Outcome("aborted" if budget.cancel_check() else "not_converged",lower=lower,reason="bp_budget_or_node_limit",statistics=stats)


@interruptible
def benders(request,options,budget, *, use_cg=False, strengthen_master=True, global_cuts=False):
    # Lift the continuous resource/passenger relaxation into the master when
    # its size is moderate. Integer recourse is still solved independently by
    # direct fixed-schedule MIP or genuine CG/B&P, with no full integer shortcut.
    lifted=None
    if strengthen_master and len(options)*len(request.dataset.aircraft)<=50000:
        conflict=schedule_precheck(request,options,budget)
        if conflict:
            return Outcome("infeasible",reason="certified_master_infeasible",statistics={"schedule_precheck":conflict})
        lifted=build_joint(request,options,relax=True)
        model,env,x=lifted.model,lifted.environment,lifted.x
        for var in x.values():
            var.VType=GRB.BINARY
    else:
        model,env=new_model("xma_schedule_master")
        x={o.option_id:model.addVar(vtype=GRB.BINARY,name="x:"+o.option_id) for o in options}
        add_schedule_rows(model,request,options,x)
    theta=model.addVar(lb=0,name="joint_aircraft_passenger_recourse")
    flights={f.flight_id:f for f in request.dataset.flights}
    sched_cost=gp.quicksum(schedule_cost(request,flights[o.flight_id],o)*x[o.option_id] for o in options)
    if lifted is not None:
        model.addConstr(theta>=lifted.objective-sched_cost,name="global_recourse_lp_projection")
    model.setObjective(sched_cost+theta,GRB.MINIMIZE)
    incumbent=original_tail_candidate(request,options) if len(request.dataset.flights)>20 else None
    if incumbent:
        budget.audited(incumbent.decisions,incumbent.objective)
    lower=0.0
    cuts=0
    calls=0
    stats={"aircraft_columns":0,"cg_iterations":0,"bp_nodes":0,"visited_schedules":0,
           "master_variant":"lifted_resource_passenger_lp_v1" if lifted is not None else "global_lp_cuts_v1" if global_cuts else "conditional_schedule_master_v1",
           "global_feasibility_cuts":0,"global_optimality_cuts":0,"lifted_lp_variables":len(lifted.integer_variables) if lifted else 0}
    stats["initial_primal_heuristic"]="original_tail_greedy_with_independent_audit"
    stats["initial_audited_upper_bound"]=incumbent.objective if incumbent else None
    stats["strengthening_size_guard"]=lifted is None and strengthen_master
    recourse=None
    reason="benders_iteration_limit"
    try:
        for iteration in range(1,request.max_benders_iterations+1):
            if not budget.optimize(model,mip=True):
                reason="time_limit_or_cancel"
                break
            if model.Status==GRB.INFEASIBLE:
                if incumbent:
                    raise ValueError("Benders master infeasible despite a valid incumbent")
                return Outcome("infeasible",reason="certified_master_infeasible",statistics=stats)
            if model.ObjBound is not None:
                lower=max(lower,model.ObjBound)
            if incumbent and lower>=incumbent.objective-TOL:
                incumbent.status="optimal"
                incumbent.lower=incumbent.upper=incumbent.objective
                incumbent.reason="integer_recourse_and_global_master_bound_closed"
                incumbent.statistics={**stats,"benders_iterations":iteration,"cuts":cuts}
                return incumbent
            if model.Status!=GRB.OPTIMAL:
                reason="master_not_optimal"
                break
            schedule={oid for oid,v in x.items() if value(model,v)>0.5}
            match=gp.quicksum(x[oid] for oid in schedule)
            exact_schedule_cost=sum(schedule_cost(request,flights[o.flight_id],o) for o in options if o.option_id in schedule)
            if lifted is None and global_cuts and recourse is None and len(options)*len(request.dataset.aircraft)<=50000:
                from .recourse import GlobalRecourseLP
                recourse=GlobalRecourseLP(request,options)
            if recourse is not None:
                certificate=recourse.solve(schedule,budget)
                if certificate is not None:
                    affine=certificate["value"]+gp.quicksum(
                        coefficient*(x[oid]-float(oid in schedule)) for oid,coefficient in certificate["gradient"].items()
                        if abs(coefficient)>1e-14)
                    if certificate["kind"]=="feasibility" and certificate["value"]>TOL:
                        model.addConstr(affine<=0,name=f"global_feasibility:{iteration}")
                        cuts+=1; stats["global_feasibility_cuts"]+=1
                        budget.emit("benders","global_feasibility_cut","全候选 LP 认证跨计划可行性割",metrics=stats)
                        continue
                    if certificate["kind"]=="optimality":
                        model.addConstr(theta+sched_cost>=affine,name=f"global_value:{iteration}")
                        cuts+=1; stats["global_optimality_cuts"]+=1
            calls+=1
            sub=branch_and_price(request,options,schedule,budget) if use_cg else direct(request,options,budget,schedule=schedule)
            stats["visited_schedules"]=calls
            for name in ("aircraft_columns","cg_iterations","bp_nodes"):
                stats[name]+=sub.statistics.get(name,0)
            if sub.decisions and (incumbent is None or sub.objective<incumbent.objective-TOL):
                incumbent=Outcome("optimal",sub.objective,lower,sub.objective,sub.decisions)
            if sub.status=="infeasible":
                model.addConstr(match<=len(schedule)-1,name=f"exact_infeasible:{calls}")
                cuts+=1
            else:
                if sub.lower is not None:
                    q=max(0,sub.lower-exact_schedule_cost)
                    # Nonnegative recourse: outside this schedule the RHS is <= 0.
                    model.addConstr(theta>=q*(match-len(schedule)+1),name=f"certified_conditional_value:{calls}")
                    cuts+=1
                if sub.status!="optimal":
                    reason=sub.reason
                    break
            budget.emit("benders","benders_iteration",f"Benders 第 {iteration} 轮",lower_bound=lower,
                upper_bound=incumbent.objective if incumbent else None,metrics={**stats,"cuts":cuts})
        if incumbent:
            incumbent.status="aborted" if budget.cancel_check() else "not_converged"
            incumbent.lower=lower
            incumbent.reason=reason
            incumbent.statistics={**stats,"cuts":cuts,"benders_iterations":calls}
            return incumbent
        return Outcome("aborted" if budget.cancel_check() else "not_converged",lower=lower,reason=reason,statistics=stats)
    finally:
        if recourse is not None:
            recourse.close()
        model.dispose()
        env.dispose()
