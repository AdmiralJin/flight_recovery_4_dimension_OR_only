from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import TypeAlias


SolverParameterValue: TypeAlias = bool | int | float | str


class SolverStatus(str, Enum):
    OPTIMAL = "optimal"
    FEASIBLE = "feasible"
    INFEASIBLE = "infeasible"
    UNBOUNDED = "unbounded"
    INFEASIBLE_OR_UNBOUNDED = "infeasible_or_unbounded"
    NO_SOLUTION = "no_solution"
    ERROR = "error"


class VariableType(str, Enum):
    CONTINUOUS = "continuous"
    INTEGER = "integer"
    BINARY = "binary"


class ConstraintSense(str, Enum):
    LESS_EQUAL = "less_equal"
    EQUAL = "equal"
    GREATER_EQUAL = "greater_equal"


class ObjectiveSense(str, Enum):
    MINIMIZE = "minimize"
    MAXIMIZE = "maximize"


class SolverContractError(RuntimeError):
    """Base error for invalid solver-adapter use."""


class SolverUnavailableError(SolverContractError):
    """The configured solver package or license is unavailable."""


class SolverCapabilityError(SolverContractError):
    """The requested operation is unsupported for this backend or model class."""


@dataclass(frozen=True)
class SolverCapabilities:
    supports_mip: bool
    supports_lp_duals: bool
    supports_reduced_costs: bool
    supports_mip_gap: bool
    supports_objective_bound: bool


@dataclass(frozen=True)
class VariableHandle:
    name: str
    _model_token: str


@dataclass(frozen=True)
class ConstraintHandle:
    name: str
    _model_token: str


@dataclass(frozen=True)
class SolverOutcome:
    model_name: str
    status: SolverStatus
    raw_status: int | str | None
    termination_reason: str
    runtime_seconds: float
    objective_value: float | None
    best_bound: float | None
    mip_gap: float | None
    diagnostics: Mapping[str, bool | int | float | str | None]

    @property
    def has_solution(self) -> bool:
        return self.status in {SolverStatus.OPTIMAL, SolverStatus.FEASIBLE}


class SolverAdapter(ABC):
    """Minimal common contract used by all fixed-column recovery models."""

    @property
    @abstractmethod
    def solver_name(self) -> str: ...

    @property
    @abstractmethod
    def solver_version(self) -> str: ...

    @property
    @abstractmethod
    def capabilities(self) -> SolverCapabilities: ...

    @abstractmethod
    def create_model(self, model_name: str) -> None: ...

    @abstractmethod
    def add_variable(
        self,
        name: str,
        *,
        lower_bound: float | None = 0.0,
        upper_bound: float | None = None,
        variable_type: VariableType = VariableType.CONTINUOUS,
    ) -> VariableHandle: ...

    @abstractmethod
    def add_linear_constraint(
        self,
        coefficients: Mapping[VariableHandle, float],
        sense: ConstraintSense,
        rhs: float,
        *,
        name: str,
    ) -> ConstraintHandle: ...

    @abstractmethod
    def set_objective(
        self,
        coefficients: Mapping[VariableHandle, float],
        sense: ObjectiveSense = ObjectiveSense.MINIMIZE,
        *,
        constant: float = 0.0,
    ) -> None: ...

    @abstractmethod
    def solve(
        self,
        parameters: Mapping[str, SolverParameterValue] | None = None,
    ) -> SolverOutcome: ...

    @abstractmethod
    def get_variable_value(self, variable: VariableHandle) -> float: ...

    @abstractmethod
    def get_objective_value(self) -> float | None: ...

    @abstractmethod
    def get_status(self) -> SolverStatus: ...

    @abstractmethod
    def get_runtime_seconds(self) -> float: ...

    @abstractmethod
    def get_best_bound(self) -> float | None: ...

    @abstractmethod
    def get_mip_gap(self) -> float | None: ...

    @abstractmethod
    def get_constraint_dual(self, constraint: ConstraintHandle) -> float: ...

    @abstractmethod
    def get_reduced_cost(self, variable: VariableHandle) -> float: ...

    @abstractmethod
    def close(self) -> None: ...
