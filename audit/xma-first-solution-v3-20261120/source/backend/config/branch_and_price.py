from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import ConfigDict, Field

from backend.schemas.common import SchemaModel


PositiveCount = Annotated[int, Field(gt=0, strict=True)]
NonNegativeCount = Annotated[int, Field(ge=0, strict=True)]
NonNegativeTolerance = Annotated[float, Field(ge=0.0, strict=True)]


class BranchAndPriceSource(str, Enum):
    IMPLEMENTATION_ASSUMPTION = "implementation_assumption"
    TEST_FIXTURE = "test_fixture"


class BranchAndPriceConfig(SchemaModel):
    """Immutable deterministic tree contract for Phase 12."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, frozen=True)

    schema_version: str = Field(pattern=r"^1\.0\.0$")
    profile_id: str = Field(min_length=1)
    integrality_tolerance: NonNegativeTolerance
    bound_tolerance: NonNegativeTolerance
    max_nodes: PositiveCount
    max_depth: NonNegativeCount
    node_selection: Literal["best_bound"]
    source: BranchAndPriceSource
    notes: tuple[str, ...] = ()


class BranchAndPriceConfigError(ValueError):
    """A Phase 12 Branch-and-Price profile is invalid or unreadable."""


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise BranchAndPriceConfigError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def load_branch_and_price_config(path: str | Path) -> BranchAndPriceConfig:
    try:
        raw = json.loads(
            Path(path).read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_json_keys,
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise BranchAndPriceConfigError(
            f"invalid Branch-and-Price profile: {exc}"
        ) from exc
    try:
        return BranchAndPriceConfig.model_validate(raw)
    except ValueError as exc:
        raise BranchAndPriceConfigError(
            f"invalid Branch-and-Price profile: {exc}"
        ) from exc
