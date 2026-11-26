from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from backend.schemas.columns import RecoveryColumns
from backend.schemas.scenario import Scenario

from .incidence import BinaryIncidence, build_recovery_incidence
from .indices import RecoveryIndices, build_recovery_indices


@dataclass(frozen=True)
class CrewRecoveryIncidence:
    """Deterministic, immutable traversals for fixed Crew Pairings."""

    crew_to_pairings: BinaryIncidence[str, str]
    operated_option_to_pairings: BinaryIncidence[str, str]
    deadhead_option_to_pairings: BinaryIncidence[str, str]
    pairing_to_operated_options: Mapping[str, tuple[str, ...]]
    pairing_to_deadhead_options: Mapping[str, tuple[str, ...]]


def build_crew_recovery_incidence(
    scenario: Scenario,
    columns: RecoveryColumns,
    indices: RecoveryIndices | None = None,
) -> CrewRecoveryIncidence:
    """Build CRM views once, reusing the Phase 2.0 incidence source of truth."""

    resolved_indices = indices or build_recovery_indices(scenario, columns)
    incidence = build_recovery_incidence(scenario, columns, resolved_indices)
    pairing_ids = resolved_indices.crew_pairings.ids
    return CrewRecoveryIncidence(
        crew_to_pairings=incidence.crew_to_pairings,
        operated_option_to_pairings=incidence.option_to_operating_pairings,
        deadhead_option_to_pairings=incidence.option_to_deadhead_pairings,
        pairing_to_operated_options=MappingProxyType(
            {
                pairing_id: incidence.option_to_operating_pairings.rows_for_column(
                    pairing_id
                )
                for pairing_id in pairing_ids
            }
        ),
        pairing_to_deadhead_options=MappingProxyType(
            {
                pairing_id: incidence.option_to_deadhead_pairings.rows_for_column(
                    pairing_id
                )
                for pairing_id in pairing_ids
            }
        ),
    )
