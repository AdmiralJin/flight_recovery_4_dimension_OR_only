from __future__ import annotations

import json
from collections.abc import Mapping
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Annotated, Any

from pydantic import ConfigDict, Field, field_serializer, field_validator

from backend.schemas.common import SchemaModel


NonNegativeMinutes = Annotated[int, Field(ge=0, strict=True)]


class StringGenerationSource(str, Enum):
    IMPLEMENTATION_ASSUMPTION = "implementation_assumption"
    TEST_FIXTURE = "test_fixture"


class FlightStringGenerationConfig(SchemaModel):
    """Versioned, immutable aircraft turn-time contract for Phase 5."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        frozen=True,
        arbitrary_types_allowed=True,
    )

    schema_version: str = Field(pattern=r"^1\.0\.0$")
    profile_id: str = Field(min_length=1)
    default_min_turn_minutes: NonNegativeMinutes
    equipment_overrides: Mapping[str, NonNegativeMinutes]
    source: StringGenerationSource
    notes: tuple[str, ...] = ()

    @field_validator("equipment_overrides", mode="before")
    @classmethod
    def validate_override_keys(cls, value: Any):
        if not isinstance(value, Mapping):
            raise TypeError("equipment_overrides must be a mapping")
        for equipment_type in value:
            if not isinstance(equipment_type, str) or not equipment_type.strip():
                raise ValueError("equipment override keys must be non-empty strings")
        return value

    @field_validator("equipment_overrides")
    @classmethod
    def freeze_overrides(cls, value: Mapping[str, int]):
        return MappingProxyType(dict(value))

    @field_serializer("equipment_overrides")
    def serialize_overrides(self, value: Mapping[str, int]):
        return dict(value)

    def min_turn_minutes(self, equipment_type: str) -> int:
        return self.equipment_overrides.get(
            equipment_type, self.default_min_turn_minutes
        )


class FlightStringGenerationConfigError(ValueError):
    """A Phase 5 string-generation profile is invalid or unreadable."""


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise FlightStringGenerationConfigError(
                f"duplicate JSON key: {key!r}"
            )
        result[key] = value
    return result


def load_flight_string_generation_config(
    path: str | Path,
) -> FlightStringGenerationConfig:
    try:
        raw = json.loads(
            Path(path).read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_json_keys,
        )
    except json.JSONDecodeError as exc:
        raise FlightStringGenerationConfigError(
            f"invalid string-generation profile JSON: {exc}"
        ) from exc
    return FlightStringGenerationConfig.model_validate(raw)
