from __future__ import annotations

import math
from collections.abc import Mapping
from types import MappingProxyType
from uuid import uuid4

from .base import (
    ConstraintHandle,
    ConstraintSense,
    ObjectiveSense,
    SolverAdapter,
    SolverCapabilities,
    SolverCapabilityError,
    SolverContractError,
    SolverOutcome,
    SolverParameterValue,
    SolverStatus,
    SolverUnavailableError,
    VariableHandle,
    VariableType,
)

try:
    import gurobipy as gp
except ImportError:  # pragma: no cover - exercised only in an uninstalled environment
    gp = None  # type: ignore[assignment]


_STATUS_NAMES = {
    1: "loaded",
    2: "optimal",
    3: "infeasible",
    4: "infeasible_or_unbounded",
    5: "unbounded",
    6: "cutoff",
    7: "iteration_limit",
    8: "node_limit",
    9: "time_limit",
    10: "solution_limit",
    11: "interrupted",
    12: "numeric_error",
    13: "suboptimal",
    14: "in_progress",
    15: "user_objective_limit",
    16: "work_limit",
    17: "memory_limit",
    18: "locally_optimal",
    19: "locally_infeasible",
}

_NO_SOLUTION_STATUSES = {1, 6, 7, 8, 9, 10, 11, 14, 15, 16, 17}
_ERROR_STATUSES = {12, 19}


def normalize_gurobi_status(raw_status: int, solution_count: int) -> SolverStatus:
    """Map Gurobi status integers without exposing them to model code."""

    if raw_status == 2:
        return SolverStatus.OPTIMAL
    if raw_status == 3:
        return SolverStatus.INFEASIBLE
    if raw_status == 4:
        return SolverStatus.INFEASIBLE_OR_UNBOUNDED
    if raw_status == 5:
        return SolverStatus.UNBOUNDED
    if solution_count > 0:
        return SolverStatus.FEASIBLE
    if raw_status in _NO_SOLUTION_STATUSES:
        return SolverStatus.NO_SOLUTION
    if raw_status in _ERROR_STATUSES or raw_status not in _STATUS_NAMES:
        return SolverStatus.ERROR
    return SolverStatus.NO_SOLUTION


def _finite_or_none(value: object) -> float | None:
    try:
        result = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _model_float_or_none(model: object, attribute: str) -> float | None:
    try:
        return _finite_or_none(getattr(model, attribute))
    except (AttributeError, gp.GurobiError):
        return None


class GurobiAdapter(SolverAdapter):
    """Gurobi implementation of the Phase 2.1 solver contract."""

    _CAPABILITIES = SolverCapabilities(
        supports_mip=True,
        supports_lp_duals=True,
        supports_reduced_costs=True,
        supports_mip_gap=True,
        supports_objective_bound=True,
    )

    def __init__(self, *, output_flag: bool = False) -> None:
        self._output_flag = output_flag
        self._environment = None
        self._model = None
        self._model_token = ""
        self._variables: dict[str, object] = {}
        self._constraints: dict[str, object] = {}
        self._last_outcome: SolverOutcome | None = None

    @property
    def solver_name(self) -> str:
        return "Gurobi"

    @property
    def solver_version(self) -> str:
        if gp is None:
            return "unavailable"
        return ".".join(str(part) for part in gp.gurobi.version())

    @property
    def capabilities(self) -> SolverCapabilities:
        return self._CAPABILITIES

    @classmethod
    def availability(cls) -> tuple[bool, str | None]:
        if gp is None:
            return False, "gurobipy is not installed"
        environment = None
        model = None
        try:
            environment = gp.Env(empty=True)
            environment.setParam("OutputFlag", 0)
            environment.start()
            model = gp.Model("availability_probe", env=environment)
            return True, None
        except gp.GurobiError as exc:
            return False, f"Gurobi unavailable ({exc.errno}): {exc}"
        finally:
            if model is not None:
                model.dispose()
            if environment is not None:
                environment.dispose()

    def create_model(self, model_name: str) -> None:
        if not model_name.strip():
            raise ValueError("model_name must be non-empty")
        self.close()
        if gp is None:
            raise SolverUnavailableError("gurobipy is not installed")
        try:
            self._environment = gp.Env(empty=True)
            self._environment.setParam("OutputFlag", int(self._output_flag))
            self._environment.start()
            self._model = gp.Model(model_name, env=self._environment)
            self._model.Params.OutputFlag = int(self._output_flag)
        except gp.GurobiError as exc:
            self.close()
            raise SolverUnavailableError(
                f"Gurobi model creation failed ({exc.errno}): {exc}"
            ) from exc
        self._model_token = uuid4().hex
        self._variables = {}
        self._constraints = {}
        self._last_outcome = None

    def add_variable(
        self,
        name: str,
        *,
        lower_bound: float | None = 0.0,
        upper_bound: float | None = None,
        variable_type: VariableType = VariableType.CONTINUOUS,
    ) -> VariableHandle:
        model = self._require_model()
        if not name.strip():
            raise ValueError("variable name must be non-empty")
        if name in self._variables:
            raise ValueError(f"duplicate variable name: {name!r}")
        lb = -gp.GRB.INFINITY if lower_bound is None else self._finite(lower_bound, "lower_bound")
        ub = gp.GRB.INFINITY if upper_bound is None else self._finite(upper_bound, "upper_bound")
        if lb > ub:
            raise ValueError("lower_bound must not exceed upper_bound")
        variable_types = {
            VariableType.CONTINUOUS: gp.GRB.CONTINUOUS,
            VariableType.INTEGER: gp.GRB.INTEGER,
            VariableType.BINARY: gp.GRB.BINARY,
        }
        variable = model.addVar(lb=lb, ub=ub, vtype=variable_types[variable_type], name=name)
        self._variables[name] = variable
        return VariableHandle(name=name, _model_token=self._model_token)

    def add_linear_constraint(
        self,
        coefficients: Mapping[VariableHandle, float],
        sense: ConstraintSense,
        rhs: float,
        *,
        name: str,
    ) -> ConstraintHandle:
        model = self._require_model()
        if not name.strip():
            raise ValueError("constraint name must be non-empty")
        if name in self._constraints:
            raise ValueError(f"duplicate constraint name: {name!r}")
        expression = gp.LinExpr()
        for handle, coefficient in coefficients.items():
            expression.addTerms(
                self._finite(coefficient, "constraint coefficient"),
                self._variable(handle),
            )
        finite_rhs = self._finite(rhs, "constraint rhs")
        if sense is ConstraintSense.LESS_EQUAL:
            constraint = model.addConstr(expression <= finite_rhs, name=name)
        elif sense is ConstraintSense.EQUAL:
            constraint = model.addConstr(expression == finite_rhs, name=name)
        else:
            constraint = model.addConstr(expression >= finite_rhs, name=name)
        self._constraints[name] = constraint
        return ConstraintHandle(name=name, _model_token=self._model_token)

    def set_objective(
        self,
        coefficients: Mapping[VariableHandle, float],
        sense: ObjectiveSense = ObjectiveSense.MINIMIZE,
        *,
        constant: float = 0.0,
    ) -> None:
        model = self._require_model()
        expression = gp.LinExpr(self._finite(constant, "objective constant"))
        for handle, coefficient in coefficients.items():
            expression.addTerms(
                self._finite(coefficient, "objective coefficient"),
                self._variable(handle),
            )
        model.setObjective(
            expression,
            gp.GRB.MINIMIZE
            if sense is ObjectiveSense.MINIMIZE
            else gp.GRB.MAXIMIZE,
        )

    def solve(
        self,
        parameters: Mapping[str, SolverParameterValue] | None = None,
    ) -> SolverOutcome:
        model = self._require_model()
        try:
            for name, value in (parameters or {}).items():
                model.setParam(name, value)
            model.optimize()
            raw_status = int(model.Status)
            solution_count = int(model.SolCount)
            status = normalize_gurobi_status(raw_status, solution_count)
            has_solution = status in {SolverStatus.OPTIMAL, SolverStatus.FEASIBLE}
            is_mip = bool(model.IsMIP)
            objective = _finite_or_none(model.ObjVal) if has_solution else None
            best_bound = _model_float_or_none(model, "ObjBound")
            mip_gap = (
                _model_float_or_none(model, "MIPGap")
                if is_mip and has_solution
                else None
            )
            diagnostics = MappingProxyType(
                {
                    "solution_count": solution_count,
                    "is_mip": is_mip,
                    "node_count": _model_float_or_none(model, "NodeCount"),
                    "simplex_iterations": _model_float_or_none(model, "IterCount"),
                    "barrier_iterations": _model_float_or_none(model, "BarIterCount"),
                }
            )
            outcome = SolverOutcome(
                model_name=model.ModelName,
                status=status,
                raw_status=raw_status,
                termination_reason=_STATUS_NAMES.get(raw_status, "unknown_status"),
                runtime_seconds=float(model.Runtime),
                objective_value=objective,
                best_bound=best_bound,
                mip_gap=mip_gap,
                diagnostics=diagnostics,
            )
        except gp.GurobiError as exc:
            outcome = SolverOutcome(
                model_name=getattr(model, "ModelName", "unknown_model"),
                status=SolverStatus.ERROR,
                raw_status=None,
                termination_reason="solver_error",
                runtime_seconds=_finite_or_none(getattr(model, "Runtime", 0.0)) or 0.0,
                objective_value=None,
                best_bound=None,
                mip_gap=None,
                diagnostics=MappingProxyType(
                    {"error_code": exc.errno, "error_message": str(exc)}
                ),
            )
        self._last_outcome = outcome
        return outcome

    def get_variable_value(self, variable: VariableHandle) -> float:
        self._require_solution()
        return float(self._variable(variable).X)

    def get_objective_value(self) -> float | None:
        return self._require_outcome().objective_value

    def get_status(self) -> SolverStatus:
        return self._require_outcome().status

    def get_runtime_seconds(self) -> float:
        return self._require_outcome().runtime_seconds

    def get_best_bound(self) -> float | None:
        return self._require_outcome().best_bound

    def get_mip_gap(self) -> float | None:
        return self._require_outcome().mip_gap

    def get_constraint_dual(self, constraint: ConstraintHandle) -> float:
        model = self._require_continuous_solution("LP dual")
        del model
        return float(self._constraint(constraint).Pi)

    def get_reduced_cost(self, variable: VariableHandle) -> float:
        model = self._require_continuous_solution("reduced cost")
        del model
        return float(self._variable(variable).RC)

    def close(self) -> None:
        if self._model is not None:
            self._model.dispose()
        if self._environment is not None:
            self._environment.dispose()
        self._model = None
        self._environment = None
        self._model_token = ""
        self._variables = {}
        self._constraints = {}
        self._last_outcome = None

    def __enter__(self) -> GurobiAdapter:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _require_model(self):
        if self._model is None:
            raise SolverContractError("create_model() must be called first")
        return self._model

    def _require_outcome(self) -> SolverOutcome:
        if self._last_outcome is None:
            raise SolverContractError("solve() must complete before reading results")
        return self._last_outcome

    def _require_solution(self) -> SolverOutcome:
        outcome = self._require_outcome()
        if not outcome.has_solution:
            raise SolverContractError(
                f"model has no solution; normalized status is {outcome.status.value}"
            )
        return outcome

    def _require_continuous_solution(self, capability: str):
        model = self._require_model()
        outcome = self._require_solution()
        if model.IsMIP:
            raise SolverCapabilityError(f"{capability} is unavailable for a MIP solution")
        if outcome.status is not SolverStatus.OPTIMAL:
            raise SolverCapabilityError(
                f"{capability} requires an optimal continuous solution"
            )
        return model

    def _variable(self, handle: VariableHandle):
        if handle._model_token != self._model_token or handle.name not in self._variables:
            raise SolverContractError(f"unknown variable handle: {handle.name!r}")
        return self._variables[handle.name]

    def _constraint(self, handle: ConstraintHandle):
        if handle._model_token != self._model_token or handle.name not in self._constraints:
            raise SolverContractError(f"unknown constraint handle: {handle.name!r}")
        return self._constraints[handle.name]

    @staticmethod
    def _finite(value: float, label: str) -> float:
        result = float(value)
        if not math.isfinite(result):
            raise ValueError(f"{label} must be finite")
        return result
