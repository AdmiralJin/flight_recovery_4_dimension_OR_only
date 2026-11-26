from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import ConfigDict, Field

from backend.schemas.common import SchemaModel


class CrewPairingColumnGenerationSource(str, Enum):
    IMPLEMENTATION_ASSUMPTION = "implementation_assumption"
    TEST_FIXTURE = "test_fixture"


class CrewPairingColumnGenerationConfig(SchemaModel):
    """Immutable numerical and iteration contract for Phase 10."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, frozen=True)

    schema_version: str = Field(pattern=r"^1\.0\.0$")
    profile_id: str = Field(min_length=1)
    pricing_epsilon: float = Field(gt=0.0, strict=True)
    feasibility_epsilon: float = Field(gt=0.0, strict=True)
    reduced_cost_audit_tolerance: float = Field(gt=0.0, strict=True)
    max_iterations: int = Field(ge=1, strict=True)
    max_columns_per_crew_per_iteration: int = Field(ge=1, strict=True)
    source: CrewPairingColumnGenerationSource
    notes: tuple[str, ...] = ()


class CrewPairingColumnGenerationConfigError(ValueError):
    """A Phase 10 column-generation profile is invalid or unreadable."""


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CrewPairingColumnGenerationConfigError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def load_crew_pairing_column_generation_config(
    path: str | Path,
) -> CrewPairingColumnGenerationConfig:
    try:
        raw = json.loads(
            Path(path).read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_json_keys,
        )
    except json.JSONDecodeError as exc:
        raise CrewPairingColumnGenerationConfigError(
            f"invalid crew-pairing CG profile JSON: {exc}"
        ) from exc
    return CrewPairingColumnGenerationConfig.model_validate(raw)
