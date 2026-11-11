"""Globally valid LP cuts on a fixed, unpruned XMA option universe."""
import math

import gurobipy as gp
import numpy as np
from gurobipy import GRB

from .model import build_joint


class GlobalRecourseLP:
    def __init__(self, request, options):
        # x stays in the model. Only these equality RHS values vary by schedule;
        # every other matrix coefficient and bound remains schedule independent.
        self.joint = build_joint(request, options, relax=True)
        self.model = self.joint.model
        self.fix = {oid: self.model.addConstr(v == 0, name="parameter:"+oid)
                    for oid, v in self.joint.x.items()}
        self.model.update()
        self.artificial = []
        self.artificial_bounds = []
        fixed_names = {r.ConstrName for r in self.fix.values()}
        for row in self.model.getConstrs():
            if row.ConstrName in fixed_names:
                continue
            signs = (1, -1) if row.Sense == "=" else (-1,) if row.Sense == "<" else (1,)
            expression = self.model.getRow(row)
            bound = 1 + abs(row.RHS) + sum(abs(expression.getCoeff(i)) * max(
                abs(expression.getVar(i).LB), abs(expression.getVar(i).UB)) for i in range(expression.size()))
            for sign in signs:
                self.artificial_bounds.append(bound)
                self.artificial.append(self.model.addVar(lb=0, ub=bound, column=gp.Column([sign], [row]),
                                                        name="global_art:"+str(len(self.artificial))))
        self.phase_one = gp.quicksum(self.artificial)

    def solve(self, schedule, budget):
        for oid, row in self.fix.items():
            row.RHS = float(oid in schedule)
        for var, bound in zip(self.artificial, self.artificial_bounds):
            var.UB = bound
        self.model.setObjective(self.phase_one)
        if not budget.optimize(self.model, scope="auxiliary_lp") or self.model.Status != GRB.OPTIMAL:
            return None
        phase = "feasibility" if self.model.ObjVal > 1e-6 else "optimality"
        if phase == "optimality":
            for var in self.artificial:
                var.UB = 0
            self.model.setObjective(self.joint.objective)
            if not budget.optimize(self.model, scope="auxiliary_lp") or self.model.Status != GRB.OPTIMAL:
                return None
        native = self.model.native
        rows = native.getConstrs()
        pi = np.asarray([self.model.dual(row) for row in rows])
        senses = np.asarray(native.getAttr("Sense", rows))
        pi = np.where(senses == "<", np.minimum(pi, 0), np.where(senses == ">", np.maximum(pi, 0), pi))
        rc = np.asarray(native.getAttr("Obj")) - native.getA().T @ pi
        lb, ub = np.asarray(native.getAttr("LB")), np.asarray(native.getAttr("UB"))
        # Lagrangian lower bound includes every finite bound contribution.
        # Clipping row signs and accounting for residual reduced costs keeps
        # cuts valid even if the LP dual has numerical feasibility residuals.
        value = float(pi @ np.asarray(native.getAttr("RHS", rows)) + np.minimum(rc*lb, rc*ub).sum() + native.ObjCon)
        value -= max(1e-7, abs(value)*1e-10)
        gradient = {oid: float(pi[row.index]) for oid, row in self.fix.items()}
        if not math.isfinite(value) or not all(math.isfinite(v) for v in gradient.values()):
            raise ValueError("nonfinite global recourse certificate")
        return {"kind": phase, "value": value, "gradient": gradient,
                "schedule": frozenset(schedule)}

    def close(self):
        self.joint.close()
