from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Literal

from pydantic import AwareDatetime, Field, model_validator

from backend.schemas.common import SchemaModel


class SourceRef(SchemaModel):
    sheet: str
    row: int = Field(ge=2)


class XmaFlight(SchemaModel):
    flight_id: str
    date: str
    flight_no: str
    domestic: bool
    origin: str
    destination: str
    sched_dep: AwareDatetime
    sched_arr: AwareDatetime
    original_aircraft: str
    equipment: str
    passengers: int = Field(ge=0)
    through_passengers: int = Field(ge=0)
    seats: int = Field(gt=0)
    importance: float = Field(gt=0, allow_inf_nan=False)
    source: SourceRef

    @model_validator(mode="after")
    def times(self):
        if self.sched_dep >= self.sched_arr:
            raise ValueError("invalid flight times or route")
        if (self.sched_arr - self.sched_dep).total_seconds() % 60:
            raise ValueError("block time must be whole minutes")
        if self.sched_dep.second or self.sched_dep.microsecond or self.sched_arr.second or self.sched_arr.microsecond:
            raise ValueError("source flight times must be minute-aligned")
        self.sched_dep=self.sched_dep.astimezone(timezone(timedelta(hours=8)))
        self.sched_arr=self.sched_arr.astimezone(timezone(timedelta(hours=8)))
        return self


class XmaAircraft(SchemaModel):
    tail_id: str
    equipment: str
    seats: int = Field(gt=0)
    initial_station: str
    original_terminal: str
    original_rotation: list[str]


class Transfer(SchemaModel):
    inbound: str
    outbound: str
    minimum_minutes: int = Field(ge=0)
    count: int = Field(gt=0)
    source: SourceRef


class Closure(SchemaModel):
    airport: str
    close_minutes: int = Field(ge=0, lt=1440)
    open_minutes: int = Field(ge=0, lt=1440)
    effective_date: str
    expiration_date: str
    source: SourceRef


class Scene(SchemaModel):
    airport: str
    kind: Literal["arrival", "departure", "parking"]
    start: AwareDatetime
    end: AwareDatetime
    parking_limit: int | None = Field(default=None, ge=0)
    flight_id: str | None = None
    tail_id: str | None = None
    source: SourceRef

    @model_validator(mode="after")
    def interval(self):
        if self.start >= self.end:
            raise ValueError("scene start must precede end")
        if self.kind == "parking" and self.parking_limit is None:
            raise ValueError("parking scene needs parking_limit")
        return self


class XmaDataset(SchemaModel):
    schema_version: Literal["xma-1.0"] = "xma-1.0"
    dataset_id: str
    source_sha256: str
    timezone: Literal["Asia/Shanghai"] = "Asia/Shanghai"
    adjustment_start: AwareDatetime
    adjustment_end: AwareDatetime
    flights: list[XmaFlight]
    aircraft: list[XmaAircraft]
    airports: dict[str, bool]
    route_prohibitions: list[tuple[str, str, str]]
    closures: list[Closure]
    scenes: list[Scene]
    travel_minutes: dict[str, int]
    transfers: list[Transfer]
    connected_pairs: list[tuple[str, str]]
    original_turn_minutes: dict[str, int]
    movement_windows: list[tuple[datetime, datetime]]
    movement_limit: int = Field(default=2, ge=0)
    movement_bucket_minutes: int = Field(default=5, gt=0)
    notes: list[str] = Field(default_factory=list)
    source_tables: dict[str, list[dict]] = Field(default_factory=dict)
    boundary_flights: dict[str, XmaFlight] = Field(default_factory=dict)


class AirObjective(SchemaModel):
    flight_delay_per_minute: float = Field(default=1, ge=0, allow_inf_nan=False)
    flight_cancellation: float = Field(default=25000, ge=0, allow_inf_nan=False)
    aircraft_reassignment: float = Field(default=0, ge=0, allow_inf_nan=False)
    passenger_delay_per_pax_minute: float = Field(default=10, ge=0, allow_inf_nan=False)
    unserved_passenger: float = Field(default=2500, ge=0, allow_inf_nan=False)


class XmaSolveRequest(SchemaModel):
    schema_version: Literal["xma-solve-1.0"] = "xma-solve-1.0"
    model_mode: Literal["xma_research"] = "xma_research"
    dataset: XmaDataset
    objective_profile: Literal["tianchi_2017", "air_linear_v1"] = "tianchi_2017"
    air_objective: AirObjective = Field(default_factory=AirObjective)
    algorithm: Literal["joint_arc_flow", "joint_path_oracle", "benders_joint", "benders_cg_bp"] = "joint_arc_flow"
    delay_step_minutes: int = Field(default=30, ge=1, le=360)
    maximum_delay_minutes: int = Field(default=1440, ge=0, le=2160)
    max_benders_iterations: int = Field(default=500, ge=1)
    max_bp_nodes: int = Field(default=1000, ge=1)
    max_cg_iterations: int = Field(default=1000, ge=1)
    oracle_path_limit: int = Field(default=100000, ge=1)
    time_limit_seconds: float = Field(default=300, gt=0, allow_inf_nan=False)
    mip_gap: float = Field(default=0, ge=0, le=1, allow_inf_nan=False)
    max_assignment_options: int = Field(default=100000, ge=1)
    crew_enabled: Literal[False] = False
    maintenance_enabled: Literal[False] = False


class Option(SchemaModel):
    option_id: str
    flight_id: str
    cancelled: bool
    dep: AwareDatetime
    arr: AwareDatetime
    delay: int = Field(ge=0)


class Decision(SchemaModel):
    flight_id: str
    option_id: str
    aircraft_id: str
    cancelled: bool
    dep: AwareDatetime
    arr: AwareDatetime
    rebook: dict[str, int] = Field(default_factory=dict)
