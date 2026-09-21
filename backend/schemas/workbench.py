from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import AwareDatetime, Field, model_validator

from .common import SchemaModel


class CapacitySemantics(str, Enum):
    EFFECTIVE_LEGACY = "effective_legacy"
    BASELINE_COMPILED = "baseline_compiled"


class DisruptionRuleType(str, Enum):
    ARRIVAL_CAPACITY_DELTA = "arrival_capacity_delta"
    DEPARTURE_CAPACITY_DELTA = "departure_capacity_delta"
    BOTH_CAPACITY_DELTA = "both_capacity_delta"
    AIRPORT_CLOSURE = "airport_closure"
    CURFEW = "curfew"


class DisruptionRule(SchemaModel):
    rule_id: str = Field(min_length=1)
    rule_type: DisruptionRuleType
    airport_id: str = Field(min_length=1)
    start_time: AwareDatetime
    end_time: AwareDatetime
    capacity_delta: int | None = None
    enabled: bool = True
    source: str = "user"
    notes: str = ""

    @model_validator(mode="after")
    def validate_rule(self):
        if self.start_time >= self.end_time:
            raise ValueError("start_time must be before end_time")
        delta_types = {
            DisruptionRuleType.ARRIVAL_CAPACITY_DELTA,
            DisruptionRuleType.DEPARTURE_CAPACITY_DELTA,
            DisruptionRuleType.BOTH_CAPACITY_DELTA,
        }
        if self.rule_type in delta_types and self.capacity_delta in (None, 0):
            raise ValueError("capacity delta rules require a non-zero capacity_delta")
        if self.rule_type not in delta_types and self.capacity_delta is not None:
            raise ValueError("closure and curfew rules cannot declare capacity_delta")
        return self


class CandidateGenerationPolicy(SchemaModel):
    regenerate_flight_options: bool = False
    include_unchanged: bool = True
    include_cancel: bool = True
    delay_step_minutes: int = Field(default=10, ge=1, le=360)
    maximum_delay_minutes: int = Field(default=60, ge=0, le=1440)
    residual_capacity_by_flight_id: dict[str, int] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_capacity(self):
        invalid = [key for key, value in self.residual_capacity_by_flight_id.items() if value < 0]
        if invalid:
            raise ValueError("residual capacities must be non-negative")
        return self


class DraftDocument(SchemaModel):
    schema_version: Literal["2.0.0"] = "2.0.0"
    name: str = Field(min_length=1)
    source_case_id: str | None = None
    capacity_semantics: CapacitySemantics = CapacitySemantics.EFFECTIVE_LEGACY
    scenario: dict[str, Any]
    solve_bundle: dict[str, Any] | None = None
    typed_disruptions: list[DisruptionRule] = Field(default_factory=list)
    candidate_policy: CandidateGenerationPolicy = Field(
        default_factory=CandidateGenerationPolicy
    )
    manual_flight_options: list[dict[str, Any]] = Field(default_factory=list)
    manual_passenger_itineraries: list[dict[str, Any]] = Field(default_factory=list)
    expected: dict[str, Any] | None = None
    notes: list[str] = Field(default_factory=list)


class WorkbenchIssue(SchemaModel):
    code: str
    message: str
    severity: Literal["error", "warning", "info"] = "error"
    path: str = "$"
    entity_id: str | None = None


class CapacityChange(SchemaModel):
    airport_id: str
    start_time: AwareDatetime
    end_time: AwareDatetime
    baseline_arrival: int
    effective_arrival: int
    baseline_departure: int
    effective_departure: int
    applied_rule_ids: list[str] = Field(default_factory=list)


class FlightImpact(SchemaModel):
    flight_id: str
    status: Literal["normal", "direct", "downstream"]
    direct_rule_ids: list[str] = Field(default_factory=list)
    propagation_sources: list[dict[str, str]] = Field(default_factory=list)


class CompilePreview(SchemaModel):
    valid: bool
    draft_hash: str
    compiled_hash: str | None = None
    issues: list[WorkbenchIssue] = Field(default_factory=list)
    effective_scenario: dict[str, Any] | None = None
    solve_request: dict[str, Any] | None = None
    capacity_changes: list[CapacityChange] = Field(default_factory=list)
    flight_impacts: list[FlightImpact] = Field(default_factory=list)
    candidate_counts: dict[str, int] = Field(default_factory=dict)
    readiness: dict[str, Any] | None = None


class DraftSummary(SchemaModel):
    draft_id: str
    name: str
    source_case_id: str | None
    working_hash: str
    revision_count: int
    created_at: AwareDatetime
    updated_at: AwareDatetime


class DraftPayload(DraftSummary):
    document: DraftDocument


class DraftCreateRequest(SchemaModel):
    name: str | None = None
    source_case_id: str | None = None
    document: DraftDocument | None = None


class DraftUpdateRequest(SchemaModel):
    base_hash: str
    document: DraftDocument


class RevisionCreateRequest(SchemaModel):
    base_hash: str
    note: str = ""


class SnapshotCreateRequest(SchemaModel):
    base_hash: str
    note: str = ""


class SnapshotRecord(SchemaModel):
    schema_version: Literal["2.0.0"] = "2.0.0"
    snapshot_id: str
    draft_id: str
    revision_id: str
    content_hash: str
    created_at: AwareDatetime
    solve_request: dict[str, Any]
    compile_preview: CompilePreview
    draft_document: DraftDocument
    environment: dict[str, Any] = Field(default_factory=dict)


class JobStatus(str, Enum):
    QUEUED = "queued"
    PREPARING = "preparing"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"


class RunCreateRequest(SchemaModel):
    snapshot_id: str
    trace_level: Literal["summary", "detailed"] = "detailed"
    runtime_profile_id: str = "default-exact"


class RuntimeProfileParameters(SchemaModel):
    time_limit_seconds: float | None = Field(default=None, gt=0, le=86400)
    max_benders_iterations: int | None = Field(default=None, ge=1, le=100000)
    max_branch_nodes: int | None = Field(default=None, ge=1, le=1000000)
    absolute_gap_tolerance: float | None = Field(default=None, ge=0, le=1e9)
    relative_gap_tolerance: float | None = Field(default=None, ge=0, le=1)


class RuntimeProfile(SchemaModel):
    profile_id: str
    name: str
    base_profile_id: str | None = None
    parameters: RuntimeProfileParameters = Field(default_factory=RuntimeProfileParameters)
    builtin: bool = False
    created_at: AwareDatetime
    updated_at: AwareDatetime


class RuntimeProfileCloneRequest(SchemaModel):
    profile_id: str = Field(min_length=1, pattern=r"^[A-Za-z0-9_.-]+$")
    name: str = Field(min_length=1)


class RuntimeProfileUpdateRequest(SchemaModel):
    name: str = Field(min_length=1)
    parameters: RuntimeProfileParameters


class RunEvent(SchemaModel):
    run_id: str
    seq: int = Field(ge=1)
    emitted_at: AwareDatetime
    elapsed_seconds: float = Field(ge=0)
    stage: str
    event_type: str
    message: str = ""
    lower_bound: float | None = None
    upper_bound: float | None = None
    absolute_gap: float | None = None
    relative_gap: float | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)
    artifact_refs: list[str] = Field(default_factory=list)


class RunRecord(SchemaModel):
    run_id: str
    snapshot_id: str
    draft_id: str
    input_hash: str
    job_status: JobStatus
    optimization_status: str | None = None
    trace_level: Literal["summary", "detailed"] = "detailed"
    runtime_profile_id: str = "default-exact"
    cancel_requested: bool = False
    created_at: AwareDatetime
    started_at: AwareDatetime | None = None
    finished_at: AwareDatetime | None = None
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None


class ProblemIssue(SchemaModel):
    code: str
    path: str = "$"
    message: str
    severity: Literal["error", "warning", "info"] = "error"
    entity_id: str | None = None


class ProblemDetails(SchemaModel):
    code: str
    message: str
    issues: list[ProblemIssue] = Field(default_factory=list)
    run_id: str | None = None
    retryable: bool = False


def utc_now() -> datetime:
    from datetime import timezone

    return datetime.now(timezone.utc)
