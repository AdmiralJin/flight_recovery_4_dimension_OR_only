"""Linear Gurobi model with a license-independent SciPy/HiGHS solve fallback."""
from __future__ import annotations

import math

import gurobipy as gp
import numpy as np
from gurobipy import GRB
from scipy.optimize import Bounds, LinearConstraint, linprog, milp
from scipy.sparse import coo_array


class ScalableModel:
    def __init__(self,name,env):
        self.native=gp.Model(name,env=env)
        self.highs=False
        self.state={}
        self.primal={}
        self.duals={}

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
        self._solve_highs()

    def _solve_highs(self):
        self.native.update()
        variables=self.native.getVars()
        rows=self.native.getConstrs()
        index={v.VarName:i for i,v in enumerate(variables)}
        ri,ci,values=[],[],[]
        lower=np.full(len(rows),-np.inf)
        upper=np.full(len(rows),np.inf)
        for i,row in enumerate(rows):
            expression=self.native.getRow(row)
            for j in range(expression.size()):
                ri.append(i)
                ci.append(index[expression.getVar(j).VarName])
                values.append(expression.getCoeff(j))
            if row.Sense in ("=",">"):
                lower[i]=row.RHS
            if row.Sense in ("=","<"):
                upper[i]=row.RHS
        matrix=coo_array((np.array(values,dtype=float),(np.array(ri,dtype=np.int32),np.array(ci,dtype=np.int32))),
            shape=(len(rows),len(variables))).tocsc()
        cost=np.array([v.Obj for v in variables])
        bounds=Bounds([v.LB if v.LB>-1e90 else -np.inf for v in variables],
            [v.UB if v.UB<1e90 else np.inf for v in variables])
        integrality=np.array([int(v.VType!=GRB.CONTINUOUS) for v in variables])
        options={"time_limit":float(self.native.Params.TimeLimit),"presolve":True}
        is_mip=bool(np.any(integrality))
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


def value(model,variable):
    return model.value(variable)
