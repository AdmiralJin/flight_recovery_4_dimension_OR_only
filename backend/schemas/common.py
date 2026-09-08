from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator


class SchemaModel(BaseModel):
    """Strict base model used by every Phase 0 JSON entity."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class IdentifiedModel(SchemaModel):
    @field_validator("*", mode="before", check_fields=False)
    @classmethod
    def reject_blank_identifiers(cls, value: object, info):
        if info.field_name and info.field_name.endswith("_id"):
            if not isinstance(value, str) or not value.strip():
                raise ValueError("must be a non-empty string")
        return value


def minutes_between(start: datetime, end: datetime) -> int:
    return round((end - start).total_seconds() / 60)

