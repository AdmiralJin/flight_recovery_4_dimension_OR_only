from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import AwareDatetime, Field, model_validator

from .columns import FlightChangeType, PassengerItineraryStatus
from .common import SchemaModel


class ReferenceType(str, Enum):
    MANUAL_REFERENCE = "manual_reference"
    SOLVER_FEASIBLE = "solver_feasible"
    SOLVER_OPTIMAL = "solver_optimal"


class SolutionStatus(str, Enum):
    FEASIBLE = "feasible"
    OPTIMAL = "optimal"
    INFEASIBLE = "infeasible"


class ResolvedFlightStatus(str, Enum):
    OPERATED = "operated"
    CANCELLED = "cancelled"


class RecoveryActionType(str, Enum):
    DELAY = "delay"
    CANCEL = "cancel"
    ORIGIN_CHANGE = "origin_change"
    DESTINATION_CHANGE = "destination_change"
    AIRCRAFT_REASSIGNMENT = "aircraft_reassignment"
    CREW_REASSIGNMENT = "crew_reassignment"
    PASSENGER_REACCOMMODATION = "passenger_reaccommodation"
    PASSENGER_UNSERVED = "passenger_unserved"
    FERRY = "ferry"
    GROUND_TRANSFER = "ground_transfer"


class RecoveryEntityType(str, Enum):
    FLIGHT = "flight"
    AIRCRAFT = "aircraft"
    CREW = "crew"
    PASSENGER_GROUP = "passenger_group"


class ObjectiveStatus(str, Enum):
    NOT_DEFINED = "not_defined"
    DEFINED = "defined"


class ResolvedFlight(SchemaModel):
    flight_id: str = Field(min_length=1)
    selected_option_id: str = Field(min_length=1)
    status: ResolvedFlightStatus
    change_types: list[FlightChangeType]
    recovered_origin: str | None
    recovered_destination: str | None
    recovered_dep: AwareDatetime | None
    recovered_arr: AwareDatetime | None
    departure_delay_minutes: int | None = Field(ge=0)
    arrival_delay_minutes: int | None = Field(ge=0)
    aircraft_id: str | None
    crew_id: str | None

    @model_validator(mode="after")
    def validate_status_shape(self):
        values = (
            self.recovered_origin,
            self.recovered_destination,
            self.recovered_dep,
            self.recovered_arr,
            self.departure_delay_minutes,
            self.arrival_delay_minutes,
            self.aircraft_id,
            self.crew_id,
        )
        if self.status is ResolvedFlightStatus.OPERATED and any(value is None for value in values):
            raise ValueError("operated resolved flight requires route, times, delays, aircraft, and crew")
        if self.status is ResolvedFlightStatus.CANCELLED and any(value is not None for value in values):
            raise ValueError("cancelled resolved flight cannot contain operation assignments")
        return self


class RecoveryAction(SchemaModel):
    action_type: RecoveryActionType
    entity_type: RecoveryEntityType
    entity_id: str = Field(min_length=1)
    from_: dict[str, Any] | None = Field(alias="from")
    to: dict[str, Any] | None
    reason: str


class PassengerOutcome(SchemaModel):
    pax_group_id: str = Field(min_length=1)
    selected_itinerary_id: str | None
    status: PassengerItineraryStatus
    arrival_time: AwareDatetime | None
    arrival_delay_minutes: int | None = Field(ge=0)
    unserved_count: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_status_shape(self):
        if self.status is PassengerItineraryStatus.TRANSPORTED:
            if self.selected_itinerary_id is None or self.arrival_time is None or self.arrival_delay_minutes is None:
                raise ValueError("transported outcome requires itinerary and arrival fields")
            if self.unserved_count != 0:
                raise ValueError("transported outcome must have unserved_count=0")
        elif self.arrival_time is not None or self.arrival_delay_minutes is not None:
            raise ValueError("unserved outcome cannot contain arrival fields")
        return self


class RecoveryMetrics(SchemaModel):
    operated_flights: int = Field(ge=0)
    cancelled_flights: int = Field(ge=0)
    delayed_flights: int = Field(ge=0)
    origin_changed_flights: int = Field(ge=0)
    destination_changed_flights: int = Field(ge=0)
    aircraft_reassignments: int = Field(ge=0)
    crew_reassignments: int = Field(ge=0)
    passenger_reaccommodated_groups: int = Field(ge=0)
    passenger_reaccommodated_count: int = Field(ge=0)
    total_flight_departure_delay_minutes: int = Field(ge=0)
    passenger_delay_minutes_weighted: int = Field(ge=0)
    unserved_passengers: int = Field(ge=0)


class ReferenceSolution(SchemaModel):
    selected_flight_option_by_flight: dict[str, str]
    selected_aircraft_string_by_aircraft: dict[str, str]
    selected_crew_pairing_by_crew: dict[str, str]
    selected_passenger_itinerary_by_group: dict[str, str]
    resolved_flights: list[ResolvedFlight]
    recovery_actions: list[RecoveryAction]
    passenger_outcomes: list[PassengerOutcome]
    metrics: RecoveryMetrics


class OracleInvariants(SchemaModel):
    required_flight_option_by_flight: dict[str, str]
    expected_cancelled_flights: list[str]
    required_metrics: RecoveryMetrics
    resource_assignment_invariants: list[str]
    passenger_invariants: list[str]


class ComparisonPolicy(SchemaModel):
    require_exact_selected_columns: bool
    require_exact_aircraft_assignment: bool
    require_exact_crew_assignment: bool
    require_exact_passenger_itinerary: bool
    compare_objective_when_defined: bool
    notes: list[str]


class RecoveryObjective(SchemaModel):
    status: ObjectiveStatus
    value: float | None
    components: dict[str, float | None]
    notes: str

    @model_validator(mode="after")
    def validate_value(self):
        if self.status is ObjectiveStatus.NOT_DEFINED and self.value is not None:
            raise ValueError("objective value must be null when status is not_defined")
        if self.status is ObjectiveStatus.DEFINED and self.value is None:
            raise ValueError("objective value is required when status is defined")
        return self


class EquivalentPattern(SchemaModel):
    name: str = Field(min_length=1)
    description: str


class RecoveryExpected(SchemaModel):
    schema_version: str = Field(pattern=r"^1\.0\.0$")
    scenario_id: str = Field(min_length=1)
    reference_type: ReferenceType
    solution_status: SolutionStatus
    assumptions: list[str]
    reference_solution: ReferenceSolution
    oracle_invariants: OracleInvariants
    comparison_policy: ComparisonPolicy
    objective: RecoveryObjective
    known_equivalent_patterns: list[EquivalentPattern]
    notes: list[str]
