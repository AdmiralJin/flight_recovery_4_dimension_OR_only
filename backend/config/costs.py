from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import ClassVar

from pydantic import Field, FiniteFloat, model_validator

from backend.schemas.columns import (
    FlightChangeType,
    FlightOperationType,
    FlightOption,
)
from backend.schemas.common import SchemaModel
from backend.schemas.scenario import Scenario


class CostOwner(str, Enum):
    SRM = "SRM"
    ARM = "ARM"
    CRM = "CRM"
    PRM = "PRM"


class CostSource(str, Enum):
    PETERSEN_2010_TABLE_2 = "petersen_2010_table_2"
    IMPLEMENTATION_ASSUMPTION = "implementation_assumption"


class CostUnit(str, Enum):
    PER_FLIGHT_MINUTE = "cost_unit_per_flight_minute"
    PER_CANCELLED_FLIGHT = "cost_unit_per_cancelled_flight"
    PER_AIRCRAFT_REASSIGNMENT = "cost_unit_per_aircraft_reassignment"
    PER_CREW_REASSIGNMENT = "cost_unit_per_crew_reassignment"
    PER_PASSENGER_MINUTE = "cost_unit_per_passenger_minute"
    PER_UNSERVED_PASSENGER = "cost_unit_per_unserved_passenger"
    PER_ORIGIN_CHANGE = "cost_unit_per_origin_change"
    PER_DESTINATION_CHANGE = "cost_unit_per_destination_change"
    PER_FERRY_MINUTE = "cost_unit_per_ferry_minute"
    PER_DEADHEAD_MINUTE = "cost_unit_per_deadhead_minute"


class CostCoefficient(SchemaModel):
    value: FiniteFloat = Field(ge=0)
    unit: CostUnit
    owner: CostOwner
    source: CostSource
    source_reference: str = Field(min_length=1)
    notes: str = ""


class CostCoefficients(SchemaModel):
    flight_delay_per_minute: CostCoefficient
    flight_cancellation: CostCoefficient
    aircraft_reassignment: CostCoefficient
    crew_reassignment: CostCoefficient
    passenger_delay_per_pax_minute: CostCoefficient
    unserved_passenger: CostCoefficient
    origin_change: CostCoefficient
    destination_change: CostCoefficient
    ferry_per_minute: CostCoefficient
    deadhead_per_minute: CostCoefficient

    _EXPECTED_METADATA: ClassVar[dict[str, tuple[CostUnit, CostOwner]]] = {
        "flight_delay_per_minute": (CostUnit.PER_FLIGHT_MINUTE, CostOwner.SRM),
        "flight_cancellation": (CostUnit.PER_CANCELLED_FLIGHT, CostOwner.SRM),
        "aircraft_reassignment": (
            CostUnit.PER_AIRCRAFT_REASSIGNMENT,
            CostOwner.ARM,
        ),
        "crew_reassignment": (CostUnit.PER_CREW_REASSIGNMENT, CostOwner.CRM),
        "passenger_delay_per_pax_minute": (
            CostUnit.PER_PASSENGER_MINUTE,
            CostOwner.PRM,
        ),
        "unserved_passenger": (CostUnit.PER_UNSERVED_PASSENGER, CostOwner.PRM),
        "origin_change": (CostUnit.PER_ORIGIN_CHANGE, CostOwner.SRM),
        "destination_change": (CostUnit.PER_DESTINATION_CHANGE, CostOwner.SRM),
        "ferry_per_minute": (CostUnit.PER_FERRY_MINUTE, CostOwner.ARM),
        "deadhead_per_minute": (CostUnit.PER_DEADHEAD_MINUTE, CostOwner.CRM),
    }

    @model_validator(mode="after")
    def validate_metadata(self):
        for field_name, (expected_unit, expected_owner) in self._EXPECTED_METADATA.items():
            coefficient = getattr(self, field_name)
            if coefficient.unit is not expected_unit:
                raise ValueError(
                    f"{field_name} unit must be {expected_unit.value!r}"
                )
            if coefficient.owner is not expected_owner:
                raise ValueError(
                    f"{field_name} owner must be {expected_owner.value!r}"
                )
        return self


class FixedColumnCostConfig(SchemaModel):
    schema_version: str = Field(pattern=r"^1\.0\.0$")
    cost_profile_id: str = Field(min_length=1)
    source: str = Field(min_length=1)
    units: str = Field(pattern=r"^abstract_cost_units$")
    coefficients: CostCoefficients
    notes: list[str] = Field(default_factory=list)


def load_cost_config(path: str | Path) -> FixedColumnCostConfig:
    return FixedColumnCostConfig.model_validate_json(
        Path(path).read_text(encoding="utf-8")
    )


def schedule_flight_option_cost(
    scenario: Scenario,
    option: FlightOption,
    costs: FixedColumnCostConfig,
) -> float:
    """Evaluate the Phase 2 SRM-owned portion of a validated flight option."""

    coefficients = costs.coefficients
    if option.operation_type is FlightOperationType.CANCEL:
        if option.base_flight_id not in {flight.flight_id for flight in scenario.flights}:
            raise ValueError(f"unknown base flight: {option.base_flight_id!r}")
        return float(coefficients.flight_cancellation.value)
    if option.operation_type is FlightOperationType.FERRY:
        return 0.0  # Ferry is owned and charged by ARM, not SRM.
    if option.base_flight_id not in {flight.flight_id for flight in scenario.flights}:
        raise ValueError(f"unknown base flight: {option.base_flight_id!r}")

    total = (
        float(option.departure_delay_minutes or 0)
        * float(coefficients.flight_delay_per_minute.value)
    )
    if FlightChangeType.ORIGIN_CHANGE in option.change_types:
        total += float(coefficients.origin_change.value)
    if FlightChangeType.DESTINATION_CHANGE in option.change_types:
        total += float(coefficients.destination_change.value)
    return total
