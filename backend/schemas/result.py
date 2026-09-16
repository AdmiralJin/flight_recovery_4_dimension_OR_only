from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import AwareDatetime, Field, model_validator

from .columns import CrewSegmentType
from .common import SchemaModel
from .expected import PassengerOutcome, RecoveryAction, RecoveryMetrics, ResolvedFlight


class RecoveredStatus(str, Enum):
    OPTIMAL = "optimal"
    INFEASIBLE = "infeasible"
    NOT_CONVERGED = "not_converged"
    ABORTED = "aborted"
    INVALID_INPUT = "invalid_input"


class SolveProfileIds(SchemaModel):
    flight_string_generation: str
    crew_pairing_generation: str
    aircraft_string_cg: str
    crew_pairing_cg: str
    benders_cg: str
    branch_and_price: str


class SolveRequest(SchemaModel):
    schema_version: Literal["1.0.0"]
    scenario: Any
    recovery_columns: Any | None = None
    capacity_profile: Any | None = None
    cost_profile_id: str
    cost_overrides: dict[str, float] = Field(default_factory=dict)
    algorithm: Literal["benders_branch_and_price_v1"]
    profile_ids: SolveProfileIds


class OriginalFlight(SchemaModel):
    origin: str
    destination: str
    dep: AwareDatetime
    arr: AwareDatetime


class FlightRecovery(SchemaModel):
    resolved: ResolvedFlight
    original: OriginalFlight


class AircraftOutcome(SchemaModel):
    aircraft_id: str
    selected_string_id: str
    ordered_flight_option_ids: list[str]
    original_flight_ids: list[str]
    recovered_flight_ids: list[str]
    reassignment_count: int = Field(ge=0)
    ferry_legs: list[str]
    final_station: str


class CrewOutcomeSegment(SchemaModel):
    segment_type: CrewSegmentType
    flight_option_id: str | None


class CrewOutcome(SchemaModel):
    crew_id: str
    selected_pairing_id: str
    original_flight_ids: list[str]
    segments: list[CrewOutcomeSegment]
    operated_flights: list[str]
    deadhead_flights: list[str]
    reassignment_count: int = Field(ge=0)
    final_station: str


class PassengerRecovery(SchemaModel):
    outcome: PassengerOutcome
    count: int = Field(ge=1)
    original_itinerary: list[str]
    recovered_itinerary: list[str]


class RecoveredObjective(SchemaModel):
    total: float
    schedule: float
    aircraft: float
    crew: float
    passenger: float

    @model_validator(mode="after")
    def components_match_total(self):
        if (
            abs(
                self.total
                - sum((self.schedule, self.aircraft, self.crew, self.passenger))
            )
            > 1e-5
        ):
            raise ValueError("objective components do not sum to total")
        return self


class RecoveredMetrics(SchemaModel):
    recovery: RecoveryMetrics
    mean_departure_delay_minutes: float = Field(ge=0)
    max_departure_delay_minutes: int = Field(ge=0)


class SolveDiagnostics(SchemaModel):
    algorithm: str
    runtime_seconds: float = Field(ge=0)
    objective: float | None
    lower_bound: float | None
    upper_bound: float | None
    gap: float | None
    benders_master_iterations: int = Field(ge=0)
    visited_schedules: int = Field(ge=0)
    lp_cuts: int = Field(ge=0)
    exact_integer_cuts: int = Field(ge=0)
    feasibility_cuts: int = Field(ge=0)
    aircraft_cg_calls: int = Field(ge=0)
    aircraft_generated_columns: int = Field(ge=0)
    aircraft_bp_nodes: int = Field(ge=0)
    crew_cg_calls: int = Field(ge=0)
    crew_generated_pairings: int = Field(ge=0)
    crew_bp_nodes: int = Field(ge=0)
    passenger_itinerary_count: int = Field(ge=0)
    formal_full_enumerators_used: bool
    integrated_audit_pass: bool | None
    terminal_reason: str


class RunMetadata(SchemaModel):
    run_id: str
    scenario_id: str
    git_commit: str | None
    application_version: str
    solver: str
    solver_version: str | None
    algorithm: str
    algorithm_profile_ids: SolveProfileIds
    cost_profile_id: str
    capacity_profile_id: str
    started_at: AwareDatetime
    finished_at: AwareDatetime
    runtime_seconds: float = Field(ge=0)


class SelectedDecisions(SchemaModel):
    flight_options: list[str]
    aircraft_strings: list[str]
    crew_pairings: list[str]
    passenger_itineraries: list[str]


class RecoveredResult(SchemaModel):
    schema_version: Literal["1.0.0"]
    run_id: str
    scenario_id: str
    status: RecoveredStatus
    algorithm: str
    objective: RecoveredObjective | None
    selected: SelectedDecisions
    resolved_flights: list[FlightRecovery]
    aircraft_outcomes: list[AircraftOutcome]
    crew_outcomes: list[CrewOutcome]
    passenger_outcomes: list[PassengerRecovery]
    recovery_actions: list[RecoveryAction]
    metrics: RecoveredMetrics | None
    diagnostics: SolveDiagnostics
    run_metadata: RunMetadata

    @model_validator(mode="after")
    def nonoptimal_has_no_fake_solution(self):
        if self.status is not RecoveredStatus.OPTIMAL and (
            self.objective is not None
            or self.resolved_flights
            or self.aircraft_outcomes
            or self.crew_outcomes
            or self.passenger_outcomes
            or self.recovery_actions
            or any(
                (
                    self.selected.flight_options,
                    self.selected.aircraft_strings,
                    self.selected.crew_pairings,
                    self.selected.passenger_itineraries,
                )
            )
        ):
            raise ValueError("nonoptimal result cannot contain recovered decisions")
        return self
