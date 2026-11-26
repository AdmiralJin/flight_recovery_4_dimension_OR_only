"""Native HiGHS implementation of the AIR solver contract.

No Gurobi conversion or implicit backend fallback is performed. Only certified
primal/dual information is exposed; interrupted LP vectors are not incumbents.
"""
from __future__ import annotations

import math
from types import MappingProxyType
from uuid import uuid4

import highspy
import numpy as np

from .base import (ConstraintHandle, ConstraintSense, ObjectiveSense, SolverAdapter,
                   SolverCapabilities, SolverCapabilityError, SolverContractError,
                   SolverOutcome, SolverStatus, VariableHandle, VariableType)
from .runtime import ACTIVE_BUDGET, check_budget, register_resource


class HighsAdapter(SolverAdapter):
    def __init__(self, *, output_flag=False, cancel_check=None):
        self._output_flag = output_flag
        self._cancel_check = cancel_check
        self._model = None
        self._variables = {}
        self._constraints = {}
        self._model_token = ""
        self._last_outcome = None
        self._is_mip = False

    @property
    def solver_name(self):
        return "HiGHS"

    @property
    def solver_version(self):
        return highspy.Highs().version()

    @property
    def capabilities(self):
        return SolverCapabilities(True, True, True, True, True)

    @classmethod
    def availability(cls):
        return True, None

    def create_model(self, model_name):
        check_budget()
        if not model_name.strip():
            raise ValueError("model_name must be non-empty")
        self.close()
        self._model = highspy.Highs()
        self._model.setOptionValue("output_flag", bool(self._output_flag))
        self._model.setOptionValue("threads", 1)
        self._name = model_name
        self._model_token = uuid4().hex
        self._objective_constant = 0.0
        register_resource(self.close)

    def _invalidate(self):
        self._last_outcome = None

    @staticmethod
    def _finite(value, label):
        value = float(value)
        if not math.isfinite(value):
            raise ValueError(f"{label} must be finite")
        return value

    def _require_model(self):
        if self._model is None:
            raise SolverContractError("create_model() must be called first")
        return self._model

    def _index(self, handle, mapping):
        if handle._model_token != self._model_token or handle.name not in mapping:
            raise SolverContractError(f"unknown handle: {handle.name!r}")
        return mapping[handle.name]

    def add_variable(self, name, *, lower_bound=0.0, upper_bound=None,
                     variable_type=VariableType.CONTINUOUS):
        check_budget()
        m = self._require_model()
        if not name.strip() or name in self._variables:
            raise ValueError(f"empty or duplicate variable name: {name!r}")
        lo = -highspy.kHighsInf if lower_bound is None else self._finite(lower_bound, "lower_bound")
        hi = highspy.kHighsInf if upper_bound is None else self._finite(upper_bound, "upper_bound")
        if variable_type == VariableType.BINARY:
            lo, hi = max(0, lo), min(1, hi)
        if lo > hi:
            raise ValueError("lower_bound must not exceed upper_bound")
        i = m.getNumCol()
        m.addVar(lo, hi)
        m.passColName(i, name)
        if variable_type != VariableType.CONTINUOUS:
            m.changeColIntegrality(i, highspy.HighsVarType.kInteger)
            self._is_mip = True
        self._variables[name] = i
        self._invalidate()
        return VariableHandle(name, self._model_token)

    def add_linear_constraint(self, coefficients, sense, rhs, *, name):
        check_budget()
        m = self._require_model()
        if not name.strip() or name in self._constraints:
            raise ValueError(f"empty or duplicate constraint name: {name!r}")
        rhs = self._finite(rhs, "rhs")
        items = [(self._index(h, self._variables), self._finite(v, "coefficient"))
                 for h, v in coefficients.items()]
        lo = rhs if sense != ConstraintSense.LESS_EQUAL else -highspy.kHighsInf
        hi = rhs if sense != ConstraintSense.GREATER_EQUAL else highspy.kHighsInf
        i = m.getNumRow()
        m.addRow(lo, hi, len(items), np.array([x[0] for x in items], dtype=np.int32),
                 np.array([x[1] for x in items], dtype=np.float64))
        m.passRowName(i, name)
        self._constraints[name] = i
        self._invalidate()
        return ConstraintHandle(name, self._model_token)

    def set_objective(self, coefficients, sense=ObjectiveSense.MINIMIZE, *, constant=0.0):
        m = self._require_model()
        costs = np.zeros(m.getNumCol(), dtype=np.float64)
        for h, v in coefficients.items():
            costs[self._index(h, self._variables)] = self._finite(v, "objective coefficient")
        m.changeColsCost(len(costs), np.arange(len(costs), dtype=np.int32), costs)
        m.changeObjectiveOffset(self._finite(constant, "objective constant"))
        self._objective_constant = float(constant)
        m.changeObjectiveSense(highspy.ObjSense.kMinimize if sense == ObjectiveSense.MINIMIZE
                               else highspy.ObjSense.kMaximize)
        self._invalidate()

    def solve(self, parameters=None):
        check_budget()
        m = self._require_model()
        self._invalidate()
        aliases = {"TimeLimit": "time_limit", "MIPGap": "mip_rel_gap", "Threads": "threads",
                   "OutputFlag": "output_flag", "Seed": "random_seed", "NodeLimit": "mip_max_nodes",
                   "FeasibilityTol": "primal_feasibility_tolerance", "OptimalityTol": "dual_feasibility_tolerance",
                   "IntFeasTol": "mip_feasibility_tolerance", "MIPGapAbs": "mip_abs_gap"}
        for k, v in (parameters or {}).items():
            if k not in aliases:
                raise SolverCapabilityError(f"unsupported HiGHS parameter: {k}")
            if k == "OutputFlag":
                v = bool(v)
            status = m.setOptionValue(aliases[k], v)
            if status == highspy.HighsStatus.kError:
                raise SolverContractError(f"invalid HiGHS parameter: {k}={v!r}")
        budget = ACTIVE_BUDGET.get()
        if budget and not budget.auditing:
            _, current = m.getOptionValue("time_limit")
            m.setOptionValue("time_limit", min(float(current), max(.001, budget.remaining())))
        def interrupted(event):
            if ((self._cancel_check and self._cancel_check()) or
                    (budget and not budget.auditing and budget.remaining() <= 0)):
                event.interrupt()
        callbacks = [m.cbSimplexInterrupt, m.cbIpmInterrupt, m.cbMipInterrupt]
        if budget or self._cancel_check:
            for cb in callbacks:
                cb.subscribe(interrupted)
        before = m.getRunTime()
        try:
            run_status = m.run()
        finally:
            for cb in callbacks:
                cb.clear()
        raw, info, solution = m.getModelStatus(), m.getInfo(), m.getSolution()
        optimal = raw == highspy.HighsModelStatus.kOptimal
        # HiGHS reports an empty feasible LP as kModelEmpty, with no vector.
        empty = raw == highspy.HighsModelStatus.kModelEmpty
        # Native kModelEmpty also occurs for contradictory constant rows such
        # as 0 = 1. Check these rows explicitly before issuing a certificate.
        lp = m.getLp()
        _, feasibility_tolerance = m.getOptionValue("primal_feasibility_tolerance")
        empty_infeasible = empty and any(lo > feasibility_tolerance or hi < -feasibility_tolerance
                                        for lo, hi in zip(lp.row_lower_, lp.row_upper_))
        empty = empty and not empty_infeasible
        feasible = bool(solution.value_valid and info.primal_solution_status == highspy.SolutionStatus.kSolutionStatusFeasible)
        if empty_infeasible:
            status = SolverStatus.INFEASIBLE
        elif optimal or empty:
            status = SolverStatus.OPTIMAL
        elif raw == highspy.HighsModelStatus.kInfeasible:
            status = SolverStatus.INFEASIBLE
        elif raw == highspy.HighsModelStatus.kUnbounded:
            status = SolverStatus.UNBOUNDED
        elif raw == highspy.HighsModelStatus.kUnboundedOrInfeasible:
            status = SolverStatus.INFEASIBLE_OR_UNBOUNDED
        elif feasible:
            status = SolverStatus.FEASIBLE
        elif run_status == highspy.HighsStatus.kError:
            status = SolverStatus.ERROR
        else:
            status = SolverStatus.NO_SOLUTION
        has = status in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE)
        objective = (self._objective_constant if empty else float(m.getObjectiveValue())) if has else None
        bound = info.mip_dual_bound if self._is_mip else objective if optimal or empty else None
        bound = float(bound) if bound is not None and math.isfinite(bound) else None
        gap = float(info.mip_gap) if self._is_mip and has and math.isfinite(info.mip_gap) else None
        self._last_outcome = SolverOutcome(
            self._name, status, int(raw), "Infeasible constant rows" if empty_infeasible else m.modelStatusToString(raw), m.getRunTime()-before,
            objective, bound, gap, MappingProxyType({"is_mip": self._is_mip,
                "solution_count": int(has), "node_count": info.mip_node_count,
                "simplex_iterations": info.simplex_iteration_count, "dual_valid": bool(solution.dual_valid)}))
        return self._last_outcome

    def _outcome(self):
        if self._last_outcome is None:
            raise SolverContractError("solve() must complete before reading results")
        return self._last_outcome

    def get_variable_value(self, variable):
        if not self._outcome().has_solution:
            raise SolverContractError("model has no feasible solution")
        return float(self._model.getSolution().col_value[self._index(variable, self._variables)])

    def get_objective_value(self): return self._outcome().objective_value
    def get_status(self): return self._outcome().status
    def get_runtime_seconds(self): return self._outcome().runtime_seconds
    def get_best_bound(self): return self._outcome().best_bound
    def get_mip_gap(self): return self._outcome().mip_gap

    def _dual(self):
        outcome = self._outcome()
        if self._is_mip or outcome.status != SolverStatus.OPTIMAL or not self._model.getSolution().dual_valid:
            raise SolverCapabilityError("dual information requires an optimal continuous solution")
        return self._model.getSolution()

    def get_constraint_dual(self, constraint):
        return float(self._dual().row_dual[self._index(constraint, self._constraints)])

    def get_reduced_cost(self, variable):
        return float(self._dual().col_dual[self._index(variable, self._variables)])

    def close(self):
        if self._model is not None:
            self._model.clear()
        self._model = None
        self._variables, self._constraints = {}, {}
        self._model_token = ""
        self._last_outcome = None
        self._is_mip = False

    def __enter__(self): return self
    def __exit__(self, *args): self.close()
