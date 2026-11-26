from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import ConfigDict, Field

from backend.schemas.common import SchemaModel


class AircraftStringColumnGenerationSource(str, Enum):
    IMPLEMENTATION_ASSUMPTION = "implementation_assumption"
    TEST_FIXTURE = "test_fixture"


class AircraftStringColumnGenerationConfig(SchemaModel):
    """Immutable numerical and iteration contract for Phase 9."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, frozen=True)

    schema_version: str = Field(pattern=r"^1\.0\.0$")
    profile_id: str = Field(min_length=1)
    pricing_epsilon: float = Field(gt=0.0)
    feasibility_epsilon: float = Field(gt=0.0)
    reduced_cost_audit_tolerance: float = Field(gt=0.0)
    max_iterations: int = Field(ge=1)
    max_columns_per_aircraft_per_iteration: int = Field(ge=1)
    source: AircraftStringColumnGenerationSource
    notes: tuple[str, ...] = ()


class AircraftStringColumnGenerationConfigError(ValueError):
    """A Phase 9 column-generation profile is invalid or unreadable."""


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise AircraftStringColumnGenerationConfigError(
                f"duplicate JSON key: {key!r}"
            )
        result[key] = value
    return result


def load_aircraft_string_column_generation_config(
    path: str | Path,
) -> AircraftStringColumnGenerationConfig:
    try:
        raw = json.loads(
            Path(path).read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_json_keys,
        )
    except json.JSONDecodeError as exc:
        raise AircraftStringColumnGenerationConfigError(
            f"invalid aircraft-string CG profile JSON: {exc}"
        ) from exc
    return AircraftStringColumnGenerationConfig.model_validate(raw)
