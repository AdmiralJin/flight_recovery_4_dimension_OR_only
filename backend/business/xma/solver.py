"""Linear Gurobi model with native HiGHS and SciPy compatibility fallbacks."""
from __future__ import annotations

import math
import threading
from time import perf_counter

import gurobipy as gp
import highspy
import numpy as np
from gurobipy import GRB
from highspy import cb as highspy_cb
from scipy.optimize import Bounds, LinearConstraint, linprog, milp
from backend.solver.runtime import ACTIVE_BUDGET, check_budget


class ScalableModel:
    def __init__(self,name,env):
        self.native=gp.Model(name,env=env)
        self.highs=False
        self.solver_name="Gurobi"
        self.state={}
        self.primal={}
        self.duals={}
        self.progress_sink=lambda event_type,message,metrics,lower_bound=None,upper_bound=None:None
        self.cancel_check=lambda:False
        self._lp_solver=None
        self._lp_snapshot=None
        self.timings={}
        self.reuse_statistics={"lp_rebuilds":0,"lp_reuses":0,"lp_added_columns":0}
        self._infeasible_solver=None
        self._disposed=False

    def dispose(self):
        if self._disposed:
            return
        self._disposed=True
        if self._infeasible_solver is not None and self._infeasible_solver is not self._lp_solver:
            self._infeasible_solver.clear()
        self._infeasible_solver=None
        if self._lp_solver is not None:
            self._lp_solver.clear()
            self._lp_solver=None
            self._lp_snapshot=None
        self.native.dispose()

    def addVar(self,*args,**kwargs):
        check_budget()
        return self.native.addVar(*args,**kwargs)

    def addConstr(self,*args,**kwargs):
        check_budget()
        return self.native.addConstr(*args,**kwargs)

    def conflict_rows(self):
        """Best-effort IIS labels; the solver status remains the certificate."""
        if self.cancel_check():
            return []
        if self.highs:
            if self._infeasible_solver is None:
                return []
            status,iis=self._infeasible_solver.getIis()
            rows=self.native.getConstrs()
            return [rows[i].ConstrName for i in iis.row_index_] if status!=highspy.HighsStatus.kError and iis.valid_ else []
        try:
            self.native.computeIIS()
            return [r.ConstrName for r in self.native.getConstrs() if r.IISConstr]
        except gp.GurobiError:
            return []

    def __getattr__(self,name):
        if name in self.state:
            return self.state[name]
        return getattr(self.native,name)

    def value(self,variable):
        return self.primal[variable.VarName] if self.highs else variable.X

    def dual(self,row):
        return self.duals[row.ConstrName] if self.highs else row.Pi

    def optimize(self,callback=None):
        if not self.highs:
            try:
                self.native.optimize(callback)
                return
            except gp.GurobiError as exc:
                if exc.errno!=10010:
                    raise
                self.highs=True
                self.solver_name="HiGHS"
                self.progress_sink("solver_fallback","Gurobi license size limit reached; falling back to native HiGHS.",
                    {"from_solver":"Gurobi","to_solver":"HiGHS","solver":"HiGHS","backend":"highspy","gurobi_error":10010})
        self._solve_highs()

    def _problem(self):
        started=perf_counter()
        self.native.update()
        variables=self.native.getVars()
        rows=self.native.getConstrs()
        # No per-nonzero Python lists or variable-name lookups.
        matrix=self.native.getA().tocsc()
        senses=np.asarray(self.native.getAttr("Sense",rows))
        rhs=np.asarray(self.native.getAttr("RHS",rows),dtype=float)
        lower=np.where(senses!="<",rhs,-np.inf)
        upper=np.where(senses!=">",rhs,np.inf)
        cost=np.asarray(self.native.getAttr("Obj",variables),dtype=float)
        lb=np.asarray(self.native.getAttr("LB",variables),dtype=float)
        ub=np.asarray(self.native.getAttr("UB",variables),dtype=float)
        bounds=Bounds(np.where(lb>-1e90,lb,-np.inf),np.where(ub<1e90,ub,np.inf))
        integrality=np.asarray(np.asarray(self.native.getAttr("VType",variables))!=GRB.CONTINUOUS,dtype=np.int32)
        self.timings["matrix_extraction_seconds"]=self.timings.get("matrix_extraction_seconds",0)+perf_counter()-started
        return variables,rows,matrix,cost,bounds,lower,upper,integrality

    def _solve_highs(self):
        self.solver_name="HiGHS"
        self.primal={}; self.duals={}; self.state={}
        problem=self._problem()
        try:
            self._solve_highspy(problem)
        except MemoryError:
            raise
        except Exception as exc:
            if self.cancel_check() or any(s in str(exc).lower() for s in ("memory", "bad_alloc", "allocation")):
                raise
            self.solver_name="SciPy/HiGHS"
            self.progress_sink("solver_fallback","Native HiGHS failed; using the SciPy compatibility path.",
                {"from_solver":"HiGHS","to_solver":"SciPy/HiGHS","solver":"SciPy/HiGHS","reason":str(exc),"live_bounds_available":False})
            self._solve_scipy(problem)

    @staticmethod
    def _finite(value):
        return value is not None and math.isfinite(float(value)) and abs(float(value))<highspy.kHighsInf/2

    def _solve_highspy(self,problem):
        variables,rows,matrix,cost,bounds,lower,upper,integrality=problem
        is_mip=bool(np.any(integrality))
        update_started=perf_counter()
        names=(tuple(v.VarName for v in variables),tuple(r.ConstrName for r in rows))
        old=self._lp_snapshot
        reusable=not is_mip and old is not None and names[1]==old[1] and names[0][:len(old[0])]==old[0]
        if reusable:
            previous=old[2]
            prefix=matrix[:,:len(old[0])]
            reusable=(prefix.shape==previous.shape and np.array_equal(prefix.indptr,previous.indptr)
                      and np.array_equal(prefix.indices,previous.indices) and np.array_equal(prefix.data,previous.data))
        if reusable:
            solver=self._lp_solver
            first=len(old[0]); added=len(variables)-first
            if added:
                extra=matrix[:,first:]
                if solver.addCols(added,cost[first:],bounds.lb[first:],bounds.ub[first:],extra.nnz,
                                  extra.indptr,extra.indices,extra.data)==highspy.HighsStatus.kError:
                    raise RuntimeError("HiGHS rejected incremental columns")
            for outcome in (
                solver.changeColsCost(len(variables),np.arange(len(variables),dtype=np.int32),cost),
                solver.changeColsBounds(len(variables),np.arange(len(variables),dtype=np.int32),bounds.lb,bounds.ub),
                solver.changeRowsBounds(len(rows),np.arange(len(rows),dtype=np.int32),lower,upper),
                solver.changeObjectiveOffset(float(self.native.ObjCon)),
            ):
                if outcome==highspy.HighsStatus.kError:
                    raise RuntimeError("HiGHS rejected incremental model update")
            self.reuse_statistics["lp_reuses"]+=1
            self.reuse_statistics["lp_added_columns"]+=added
        else:
            if self._lp_solver is not None:
                self._lp_solver.clear()
                self._lp_solver=None; self._lp_snapshot=None
            solver=highspy.Highs()
            solver.setOptionValue("output_flag",False)
            self._pass_highs_model(solver,problem)
            if not is_mip:
                self._lp_solver=solver
                self.reuse_statistics["lp_rebuilds"]+=1
        if not is_mip:
            self._lp_snapshot=(*names,matrix)
        solver.setOptionValue("output_flag",False)
        solver.setOptionValue("threads",1)
        solver.setOptionValue("presolve","on")
        if not is_mip:
            solver.setOptionValue("solver","simplex")
        remaining=float(self.native.Params.TimeLimit)
        budget=ACTIVE_BUDGET.get()
        if budget:
            check_budget()
            remaining=min(remaining,budget.remaining())
        # HiGHS clocks are cumulative across run() calls on a persistent model.
        solver.setOptionValue("time_limit",solver.getRunTime()+max(.001,remaining))
        solver.setOptionValue("mip_rel_gap",float(self.native.Params.MIPGap))
        self.timings["solver_model_update_seconds"]=self.timings.get("solver_model_update_seconds",0)+perf_counter()-update_started
        self._run_highs(solver,variables,rows,is_mip)
        if is_mip and self._infeasible_solver is not solver:
            solver.clear()

    def _pass_highs_model(self,solver,problem):
        variables,rows,matrix,cost,bounds,lower,upper,integrality=problem
        lp=highspy.HighsLp()
        lp.num_col_=len(variables); lp.num_row_=len(rows)
        lp.col_cost_=cost; lp.col_lower_=bounds.lb; lp.col_upper_=bounds.ub
        lp.row_lower_=lower; lp.row_upper_=upper; lp.offset_=float(self.native.ObjCon)
        lp.integrality_=[highspy.HighsVarType.kInteger if value else highspy.HighsVarType.kContinuous for value in integrality]
        lp.a_matrix_.format_=highspy.MatrixFormat.kColwise
        lp.a_matrix_.start_=matrix.indptr.astype(np.int32,copy=False)
        lp.a_matrix_.index_=matrix.indices.astype(np.int32,copy=False)
        lp.a_matrix_.value_=matrix.data
        if solver.passModel(lp)==highspy.HighsStatus.kError:
            raise RuntimeError("HiGHS rejected the translated model")

    def _run_highs(self,solver,variables,rows,is_mip):
        started=perf_counter()
        lock=threading.Lock()
        telemetry={"last_emit":0.0,"last_activity":started,"seen_incumbent":False,"lower":None,"upper":None}
        stopped=threading.Event()

        def publish(data_out,force=False):
            now=perf_counter()
            lower_bound=float(data_out.mip_dual_bound) if self._finite(data_out.mip_dual_bound) else None
            upper_bound=float(data_out.mip_primal_bound) if self._finite(data_out.mip_primal_bound) else None
            first_incumbent=upper_bound is not None and not telemetry["seen_incumbent"]
            changed=(lower_bound,upper_bound)!=(telemetry["lower"],telemetry["upper"])
            telemetry.update({"lower":lower_bound,"upper":upper_bound})
            if upper_bound is not None:
                telemetry["seen_incumbent"]=True
            if not force and not first_incumbent and (not changed or now-telemetry["last_emit"]<1.0):
                return
            telemetry["last_emit"]=now; telemetry["last_activity"]=now
            self.progress_sink("mip_progress","HiGHS mixed-integer optimization progress.",{
                "solver":"HiGHS","backend":"highspy","live_bounds_available":True,
                "node_count":int(data_out.mip_node_count),"solver_runtime_seconds":float(data_out.running_time),
                "has_incumbent":upper_bound is not None,
            },lower_bound,upper_bound)

        def callback(callback_type,message,data_out,data_in,user_data):
            del message,user_data
            if callback_type in (highspy_cb.HighsCallbackType.kCallbackMipImprovingSolution,
                highspy_cb.HighsCallbackType.kCallbackMipLogging,highspy_cb.HighsCallbackType.kCallbackMipInterrupt):
                with lock:
                    publish(data_out)
            if self.cancel_check():
                data_in.user_interrupt=True

        solver.setCallback(callback,None)
        for callback_type in (highspy_cb.HighsCallbackType.kCallbackMipImprovingSolution,
            highspy_cb.HighsCallbackType.kCallbackMipLogging,highspy_cb.HighsCallbackType.kCallbackMipInterrupt,
            highspy_cb.HighsCallbackType.kCallbackSimplexInterrupt,highspy_cb.HighsCallbackType.kCallbackIpmInterrupt):
            solver.startCallback(callback_type)
        solver.HandleUserInterrupt=True

        def heartbeat():
            last_heartbeat=perf_counter()
            while not stopped.wait(0.1):
                if self.cancel_check():
                    solver.cancelSolve()
                if perf_counter()-last_heartbeat<5.0:
                    continue
                last_heartbeat=perf_counter()
                with lock:
                    silent=perf_counter()-telemetry["last_activity"]
                    telemetry["last_activity"]=perf_counter()
                    lower_bound=telemetry["lower"]
                    upper_bound=telemetry["upper"]
                self.progress_sink("solver_heartbeat","Native HiGHS is still solving.",{
                    "solver":"HiGHS","backend":"highspy","live_bounds_available":True,
                    "seconds_since_progress":silent,"has_incumbent":upper_bound is not None,
                    "last_lower_bound":lower_bound,"last_upper_bound":upper_bound,
                })
        monitor=threading.Thread(target=heartbeat,daemon=True)
        monitor.start()
        try:
            run_status=solver.run()
            if run_status==highspy.HighsStatus.kError:
                raise RuntimeError("HiGHS solve failed")
        finally:
            stopped.set(); monitor.join(timeout=1.0)
            self.timings["native_optimization_seconds"]=self.timings.get("native_optimization_seconds",0)+perf_counter()-started

        model_status=solver.getModelStatus()
        self._infeasible_solver=solver if model_status==highspy.HighsModelStatus.kInfeasible else None
        info=solver.getInfo()
        solution=solver.getSolution()
        status_map={
            highspy.HighsModelStatus.kOptimal:GRB.OPTIMAL,
            highspy.HighsModelStatus.kTimeLimit:GRB.TIME_LIMIT,
            highspy.HighsModelStatus.kInfeasible:GRB.INFEASIBLE,
            highspy.HighsModelStatus.kUnbounded:GRB.UNBOUNDED,
            highspy.HighsModelStatus.kInterrupt:GRB.INTERRUPTED,
            highspy.HighsModelStatus.kHighsInterrupt:GRB.INTERRUPTED,
        }
        has_solution=bool(solution.value_valid and info.primal_solution_status==highspy.SolutionStatus.kSolutionStatusFeasible
                          and len(solution.col_value)==len(variables) and np.all(np.isfinite(solution.col_value)))
        self.primal={v.VarName:float(value) for v,value in zip(variables,solution.col_value)} if has_solution else {}
        value=float(info.objective_function_value) if has_solution and self._finite(info.objective_function_value) else None
        bound=float(info.mip_dual_bound) if is_mip and self._finite(info.mip_dual_bound) else value if model_status==highspy.HighsModelStatus.kOptimal else None
        self.duals={r.ConstrName:float(v) for r,v in zip(rows,solution.row_dual)} if not is_mip and solution.dual_valid and model_status==highspy.HighsModelStatus.kOptimal else {}
        self.state={"Status":status_map.get(model_status,GRB.NUMERIC),"SolCount":int(has_solution),"ObjVal":value,"ObjBound":bound,
            "NodeCount":max(0,int(info.mip_node_count)),"IsMIP":is_mip}
        if is_mip and (value is not None or bound is not None):
            class FinalData:
                mip_dual_bound=bound if bound is not None else highspy.kHighsInf
                mip_primal_bound=value if value is not None else highspy.kHighsInf
                mip_node_count=info.mip_node_count
                running_time=perf_counter()-started
            with lock:
                publish(FinalData(),force=True)

    def _solve_scipy(self,problem):
        variables,rows,matrix,cost,bounds,lower,upper,integrality=problem
        is_mip=bool(np.any(integrality))
        stopped=threading.Event()
        def heartbeat():
            while not stopped.wait(5.0):
                self.progress_sink("solver_heartbeat","SciPy/HiGHS is solving; live MIP bounds are unavailable on this compatibility path.",
                    {"solver":"SciPy/HiGHS","live_bounds_available":False})
        monitor=threading.Thread(target=heartbeat,daemon=True) if is_mip else None
        if monitor:
            monitor.start()
        try:
            options={"time_limit":float(self.native.Params.TimeLimit),"presolve":True}
            if is_mip:
                result=milp(cost,integrality=integrality,bounds=bounds,constraints=LinearConstraint(matrix,lower,upper),
                    options={**options,"mip_rel_gap":float(self.native.Params.MIPGap)})
            else:
                equal=[i for i,row in enumerate(rows) if row.Sense=="="]
                inequalities=[i for i,row in enumerate(rows) if row.Sense!="="]
                signs=np.array([1 if rows[i].Sense=="<" else -1 for i in inequalities])
                result=linprog(cost,A_ub=matrix[inequalities].multiply(signs[:,None]).tocsr() if inequalities else None,
                    b_ub=np.array([rows[i].RHS for i in inequalities])*signs if inequalities else None,
                    A_eq=matrix[equal] if equal else None,b_eq=np.array([rows[i].RHS for i in equal]) if equal else None,
                    bounds=list(zip(bounds.lb,bounds.ub)),method="highs",options=options)
                if result.status==0:
                    self.duals={rows[i].ConstrName:float(v) for i,v in zip(equal,result.eqlin.marginals)}
                    self.duals.update({rows[i].ConstrName:float(v*s) for i,v,s in zip(inequalities,result.ineqlin.marginals,signs)})
            status={0:GRB.OPTIMAL,1:GRB.TIME_LIMIT,2:GRB.INFEASIBLE,3:GRB.UNBOUNDED}.get(result.status,GRB.NUMERIC)
            has_solution=result.x is not None and np.all(np.isfinite(result.x))
            self.primal={v.VarName:float(value) for v,value in zip(variables,result.x)} if has_solution else {}
            constant=self.native.ObjCon
            value=float(result.fun)+constant if has_solution else None
            bound=getattr(result,"mip_dual_bound",None)
            bound=float(bound)+constant if bound is not None and math.isfinite(bound) else value if result.status==0 else None
            self.state={"Status":status,"SolCount":int(has_solution),"ObjVal":value,"ObjBound":bound,
                "NodeCount":getattr(result,"mip_node_count",0) or 0,"IsMIP":is_mip}
        finally:
            stopped.set()
            if monitor:
                monitor.join(timeout=1.0)


def value(model,variable):
    return model.value(variable)
