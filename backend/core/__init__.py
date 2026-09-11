"""Deterministic model-input structures shared by fixed-column recovery models."""

from .incidence import BinaryIncidence, RecoveryIncidence, build_recovery_incidence
from .gate_inventory import (
    GateCheckpoint,
    GateInventoryBuildError,
    GateInventoryData,
    build_gate_inventory_data,
)
from .indices import (
    CapacityIntervalKey,
    OrderedIndex,
    RecoveryIndices,
    build_recovery_indices,
)
from .srm import (
    FixedColumnSrmModel,
    SrmBuildError,
    build_fixed_column_srm,
    recompute_srm_diagnostics,
    solve_fixed_column_srm,
)

__all__ = [
    "BinaryIncidence",
    "CapacityIntervalKey",
    "FixedColumnSrmModel",
    "GateCheckpoint",
    "GateInventoryBuildError",
    "GateInventoryData",
    "OrderedIndex",
    "RecoveryIncidence",
    "RecoveryIndices",
    "SrmBuildError",
    "build_fixed_column_srm",
    "build_gate_inventory_data",
    "build_recovery_incidence",
    "build_recovery_indices",
    "recompute_srm_diagnostics",
    "solve_fixed_column_srm",
]
