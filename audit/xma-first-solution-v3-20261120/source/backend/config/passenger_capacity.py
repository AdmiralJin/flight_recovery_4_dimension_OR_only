from __future__ import annotations

import json
from collections.abc import Mapping
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Annotated, Any

from pydantic import ConfigDict, Field, field_serializer, field_validator

from backend.schemas.columns import FlightOperationType, RecoveryColumns
from backend.schemas.common import SchemaModel
from backend.schemas.scenario import Scenario


NonNegativeSeatCount = Annotated[int, Field(ge=0, strict=True)]


class PassengerCapacitySource(str, Enum):
    IMPLEMENTATION_ASSUMPTION = "implementation_assumption"
    TEST_FIXTURE = "test_fixture"


class PassengerCapacityProfile(SchemaModel):
    """Versioned external seat inventory for one fixed-column PRM run.

    Values are seats available to the modeled passenger commodities, not inferred
    aircraft capacities. The mapping is made read-only after validation.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        frozen=True,
        arbitrary_types_allowed=True,
    )

    schema_version: str = Field(pattern=r"^1\.0\.0$")
    capacity_profile_id: str = Field(min_length=1)
    scenario_id: str = Field(min_length=1)
    source: PassengerCapacitySource
    units: str = Field(pattern=r"^seats$")
    seat_capacity_by_option_id: Mapping[str, NonNegativeSeatCount]
    notes: tuple[str, ...] = ()

    @field_validator("seat_capacity_by_option_id", mode="before")
    @classmethod
    def validate_capacity_keys(cls, value: Any):
        if not isinstance(value, Mapping):
            raise TypeError("seat_capacity_by_option_id must be a mapping")
        for option_id in value:
            if not isinstance(option_id, str) or not option_id.strip():
                raise ValueError("capacity option IDs must be non-empty strings")
        return value

    @field_validator("seat_capacity_by_option_id")
    @classmethod
    def freeze_capacity_mapping(cls, value: Mapping[str, int]):
        return MappingProxyType(dict(value))

    @field_serializer("seat_capacity_by_option_id")
    def serialize_capacity_mapping(self, value: Mapping[str, int]):
        return dict(value)


class PassengerCapacityError(ValueError):
    """A capacity profile cannot be used for the requested PRM scenario."""


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise PassengerCapacityError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def load_passenger_capacity_profile(
    path: str | Path,
) -> PassengerCapacityProfile:
    try:
        raw = json.loads(
            Path(path).read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_json_keys,
        )
    except json.JSONDecodeError as exc:
        raise PassengerCapacityError(f"invalid capacity profile JSON: {exc}") from exc
    return PassengerCapacityProfile.model_validate(raw)


def validate_passenger_capacity_profile(
    profile: PassengerCapacityProfile,
    scenario: Scenario,
    columns: RecoveryColumns,
) -> None:
    if profile.scenario_id != scenario.scenario_id:
        raise PassengerCapacityError(
            "capacity profile scenario_id differs from Scenario: "
            f"{profile.scenario_id!r} != {scenario.scenario_id!r}"
        )

    options = {option.option_id: option for option in columns.flight_options}
    for option_id in profile.seat_capacity_by_option_id:
        option = options.get(option_id)
        if option is None:
            raise PassengerCapacityError(
                f"capacity profile references unknown flight option {option_id!r}"
            )
        if (
            option.operation_type is not FlightOperationType.OPERATE
            or option.base_flight_id is None
        ):
            raise PassengerCapacityError(
                "passenger capacity is allowed only for revenue OPERATE options; "
                f"got {option.operation_type.value} option {option_id!r}"
            )
