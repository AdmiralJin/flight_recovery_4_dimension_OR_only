from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import ConfigDict, Field

from backend.schemas.common import SchemaModel


PositiveIterationCount = Annotated[int, Field(gt=0, strict=True)]
NonNegativeTolerance = Annotated[float, Field(ge=0.0, strict=True)]


class BendersColumnGenerationSource(str, Enum):
    IMPLEMENTATION_ASSUMPTION = "implementation_assumption"
    TEST_FIXTURE = "test_fixture"


class BendersColumnGenerationConfig(SchemaModel):
    """Immutable Phase 11 Benders + column-generation contract."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, frozen=True)

    schema_version: str = Field(pattern=r"^1\.0\.0$")
    profile_id: str = Field(min_length=1)
    max_benders_iterations: PositiveIterationCount
    absolute_gap_tolerance: NonNegativeTolerance
    relative_gap_tolerance: NonNegativeTolerance
    integrality_tolerance: NonNegativeTolerance
    require_full_scope: Literal[True]
    source: BendersColumnGenerationSource
    notes: tuple[str, ...] = ()


class BendersColumnGenerationConfigError(ValueError):
    """A Phase 11 Benders + column-generation profile is invalid."""


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise BendersColumnGenerationConfigError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def load_benders_column_generation_config(
    path: str | Path,
) -> BendersColumnGenerationConfig:
    try:
        raw = json.loads(
            Path(path).read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_json_keys,
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise BendersColumnGenerationConfigError(
            f"invalid Benders column-generation profile: {exc}"
        ) from exc
    try:
        return BendersColumnGenerationConfig.model_validate(raw)
    except ValueError as exc:
        raise BendersColumnGenerationConfigError(
            f"invalid Benders column-generation profile: {exc}"
        ) from exc
