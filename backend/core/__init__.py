"""Deterministic model-input structures shared by fixed-column recovery models."""

from .arm import (
    AircraftRecoveryRequest,
    ArmBuildError,
    FixedColumnArmModel,
    analyze_arm_fixed_columns,
    build_fixed_column_arm,
    recompute_arm_diagnostics,
    solve_fixed_column_arm,
)
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
    "AircraftRecoveryRequest",
    "ArmBuildError",
    "BinaryIncidence",
    "CapacityIntervalKey",
    "FixedColumnArmModel",
    "FixedColumnSrmModel",
    "GateCheckpoint",
    "GateInventoryBuildError",
    "GateInventoryData",
    "OrderedIndex",
    "RecoveryIncidence",
    "RecoveryIndices",
    "SrmBuildError",
    "analyze_arm_fixed_columns",
    "build_fixed_column_arm",
    "build_fixed_column_srm",
    "build_gate_inventory_data",
    "build_recovery_incidence",
    "build_recovery_indices",
    "recompute_arm_diagnostics",
    "recompute_srm_diagnostics",
    "solve_fixed_column_arm",
    "solve_fixed_column_srm",
]
