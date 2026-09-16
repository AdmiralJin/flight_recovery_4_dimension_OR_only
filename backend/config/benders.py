from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Annotated, Any

from pydantic import ConfigDict, Field, StrictBool

from backend.schemas.common import SchemaModel


PositiveIterationCount = Annotated[int, Field(gt=0, strict=True)]
NonNegativeTolerance = Annotated[float, Field(ge=0.0, strict=True)]


class BendersImplementationSource(str, Enum):
    IMPLEMENTATION_ASSUMPTION = "implementation_assumption"
    TEST_FIXTURE = "test_fixture"


class FixedColumnBendersConfig(SchemaModel):
    """Immutable Phase 8 logic-based fixed-column Benders contract."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        frozen=True,
    )

    schema_version: str = Field(pattern=r"^1\.0\.0$")
    profile_id: str = Field(min_length=1)
    algorithm: str = Field(pattern=r"^logic_based_fixed_column_benders$")
    max_iterations: PositiveIterationCount
    absolute_gap_tolerance: NonNegativeTolerance
    relative_gap_tolerance: NonNegativeTolerance
    enable_arm: StrictBool
    enable_crm: StrictBool
    enable_prm: StrictBool
    source: BendersImplementationSource
    notes: tuple[str, ...] = ()


class FixedColumnBendersConfigError(ValueError):
    """A Phase 8 Benders profile is invalid or unreadable."""


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise FixedColumnBendersConfigError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def load_fixed_column_benders_config(
    path: str | Path,
) -> FixedColumnBendersConfig:
    try:
        raw = json.loads(
            Path(path).read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_json_keys,
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise FixedColumnBendersConfigError(
            f"invalid fixed-column Benders profile: {exc}"
        ) from exc
    try:
        return FixedColumnBendersConfig.model_validate(raw)
    except ValueError as exc:
        raise FixedColumnBendersConfigError(
            f"invalid fixed-column Benders profile: {exc}"
        ) from exc
