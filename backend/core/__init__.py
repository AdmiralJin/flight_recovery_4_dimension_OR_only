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
from .crm import (
    CrmBuildError,
    CrewRecoveryRequest,
    FixedColumnCrmModel,
    analyze_crm_fixed_columns,
    build_fixed_column_crm,
    recompute_crm_diagnostics,
    solve_fixed_column_crm,
)
from .crew_incidence import (
    CrewRecoveryIncidence,
    build_crew_recovery_incidence,
)
from .constraint_registry import (
    CONSTRAINT_REGISTRY,
    ConstraintImplementationStatus,
    ConstraintKind,
    ConstraintMetadata,
    ConstraintProvenance,
    list_constraint_metadata,
)
from .incidence import BinaryIncidence, RecoveryIncidence, build_recovery_incidence
from .passenger_incidence import (
    PassengerRecoveryIncidence,
    build_passenger_recovery_incidence,
)
from .prm import (
    FixedColumnPrmModel,
    PassengerRecoveryRequest,
    PrmBuildError,
    analyze_prm_fixed_columns,
    build_fixed_column_prm,
    recompute_prm_diagnostics,
    solve_fixed_column_prm,
)
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
from .integrated_oracle import (
    INTEGRATED_MODEL_NAME,
    LINKING_CONSTRAINTS,
    IntegratedFixedColumnModel,
    IntegratedOracleBuildError,
    IntegratedRecoveryRequest,
    audit_integrated_candidate,
    build_integrated_fixed_column_oracle,
    recompute_integrated_diagnostics,
    solve_integrated_fixed_column_oracle,
)
from .recovery_handoff import (
    RecoveryHandoffError,
    extract_required_operated_option_ids,
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
    "CrmBuildError",
    "CrewRecoveryIncidence",
    "CrewRecoveryRequest",
    "CONSTRAINT_REGISTRY",
    "ConstraintImplementationStatus",
    "ConstraintKind",
    "ConstraintMetadata",
    "ConstraintProvenance",
    "FixedColumnArmModel",
    "FixedColumnCrmModel",
    "FixedColumnPrmModel",
    "FixedColumnSrmModel",
    "GateCheckpoint",
    "GateInventoryBuildError",
    "GateInventoryData",
    "INTEGRATED_MODEL_NAME",
    "IntegratedFixedColumnModel",
    "IntegratedOracleBuildError",
    "IntegratedRecoveryRequest",
    "LINKING_CONSTRAINTS",
    "OrderedIndex",
    "PassengerRecoveryIncidence",
    "PassengerRecoveryRequest",
    "PrmBuildError",
    "RecoveryIncidence",
    "RecoveryHandoffError",
    "RecoveryIndices",
    "SrmBuildError",
    "analyze_arm_fixed_columns",
    "analyze_crm_fixed_columns",
    "analyze_prm_fixed_columns",
    "audit_integrated_candidate",
    "build_crew_recovery_incidence",
    "build_fixed_column_arm",
    "build_fixed_column_crm",
    "build_fixed_column_srm",
    "build_gate_inventory_data",
    "build_integrated_fixed_column_oracle",
    "build_fixed_column_prm",
    "build_passenger_recovery_incidence",
    "build_recovery_incidence",
    "build_recovery_indices",
    "extract_required_operated_option_ids",
    "list_constraint_metadata",
    "recompute_arm_diagnostics",
    "recompute_crm_diagnostics",
    "recompute_integrated_diagnostics",
    "recompute_prm_diagnostics",
    "recompute_srm_diagnostics",
    "solve_fixed_column_arm",
    "solve_fixed_column_crm",
    "solve_fixed_column_prm",
    "solve_fixed_column_srm",
    "solve_integrated_fixed_column_oracle",
]
