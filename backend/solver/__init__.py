"""Solver-independent contracts and supported backend adapters."""

from .base import (
    ConstraintHandle,
    ConstraintSense,
    ObjectiveSense,
    SolverAdapter,
    SolverCapabilities,
    SolverCapabilityError,
    SolverOutcome,
    SolverStatus,
    SolverUnavailableError,
    VariableHandle,
    VariableType,
)
from .gurobi import GurobiAdapter

__all__ = [
    "ConstraintHandle",
    "ConstraintSense",
    "GurobiAdapter",
    "ObjectiveSense",
    "SolverAdapter",
    "SolverCapabilities",
    "SolverCapabilityError",
    "SolverOutcome",
    "SolverStatus",
    "SolverUnavailableError",
    "VariableHandle",
    "VariableType",
]
