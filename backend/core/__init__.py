"""Deterministic model-input structures shared by fixed-column recovery models."""

from .incidence import BinaryIncidence, RecoveryIncidence, build_recovery_incidence
from .indices import (
    CapacityIntervalKey,
    OrderedIndex,
    RecoveryIndices,
    build_recovery_indices,
)

__all__ = [
    "BinaryIncidence",
    "CapacityIntervalKey",
    "OrderedIndex",
    "RecoveryIncidence",
    "RecoveryIndices",
    "build_recovery_incidence",
    "build_recovery_indices",
]
