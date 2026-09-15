from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Annotated, Any

from pydantic import ConfigDict, Field

from backend.schemas.common import SchemaModel


NonNegativeMinutes = Annotated[int, Field(ge=0, strict=True)]
PositiveLegCount = Annotated[int, Field(gt=0, strict=True)]


class ItineraryGenerationSource(str, Enum):
    IMPLEMENTATION_ASSUMPTION = "implementation_assumption"
    TEST_FIXTURE = "test_fixture"


class PassengerItineraryGenerationConfig(SchemaModel):
    """Versioned, immutable Phase 7 passenger-path legality boundary."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        frozen=True,
    )

    schema_version: str = Field(pattern=r"^1\.0\.0$")
    profile_id: str = Field(min_length=1)
    default_mct_minutes: NonNegativeMinutes
    max_flight_legs: PositiveLegCount
    allow_unserved: bool
    allow_surface: bool
    source: ItineraryGenerationSource
    notes: tuple[str, ...] = ()


class PassengerItineraryGenerationConfigError(ValueError):
    """A Phase 7 itinerary-generation profile is invalid or unreadable."""


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise PassengerItineraryGenerationConfigError(
                f"duplicate JSON key: {key!r}"
            )
        result[key] = value
    return result


def load_passenger_itinerary_generation_config(
    path: str | Path,
) -> PassengerItineraryGenerationConfig:
    try:
        raw = json.loads(
            Path(path).read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_json_keys,
        )
    except json.JSONDecodeError as exc:
        raise PassengerItineraryGenerationConfigError(
            f"invalid itinerary-generation profile JSON: {exc}"
        ) from exc
    return PassengerItineraryGenerationConfig.model_validate(raw)
