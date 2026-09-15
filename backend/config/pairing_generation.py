from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Annotated, Any

from pydantic import ConfigDict, Field

from backend.schemas.common import SchemaModel


NonNegativeMinutes = Annotated[int, Field(ge=0, strict=True)]
PositiveMinutes = Annotated[int, Field(gt=0, strict=True)]


class PairingGenerationSource(str, Enum):
    IMPLEMENTATION_ASSUMPTION = "implementation_assumption"
    TEST_FIXTURE = "test_fixture"


class CrewPairingGenerationConfig(SchemaModel):
    """Versioned, immutable Phase 6 crew-legality boundary."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        frozen=True,
    )

    schema_version: str = Field(pattern=r"^1\.0\.0$")
    profile_id: str = Field(min_length=1)
    default_min_connection_minutes: NonNegativeMinutes
    max_duty_minutes: PositiveMinutes
    max_deadhead_legs: int | None = Field(default=None, ge=0, strict=True)
    allow_deadhead: bool
    allow_idle: bool
    source: PairingGenerationSource
    notes: tuple[str, ...] = ()


class CrewPairingGenerationConfigError(ValueError):
    """A Phase 6 pairing-generation profile is invalid or unreadable."""


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CrewPairingGenerationConfigError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def load_crew_pairing_generation_config(
    path: str | Path,
) -> CrewPairingGenerationConfig:
    try:
        raw = json.loads(
            Path(path).read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_json_keys,
        )
    except json.JSONDecodeError as exc:
        raise CrewPairingGenerationConfigError(
            f"invalid pairing-generation profile JSON: {exc}"
        ) from exc
    return CrewPairingGenerationConfig.model_validate(raw)
