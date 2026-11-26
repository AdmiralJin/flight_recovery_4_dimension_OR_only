from __future__ import annotations

from enum import Enum

from pydantic import AwareDatetime, Field, model_validator

from .common import SchemaModel


class FlightOperationType(str, Enum):
    OPERATE = "operate"
    CANCEL = "cancel"
    FERRY = "ferry"


class FlightChangeType(str, Enum):
    UNCHANGED = "unchanged"
    DELAY = "delay"
    CANCEL = "cancel"
    ORIGIN_CHANGE = "origin_change"
    DESTINATION_CHANGE = "destination_change"
    BLOCK_TIME_CHANGE = "block_time_change"
    POSITIONING = "positioning"


class CrewSegmentType(str, Enum):
    OPERATE = "operate"
    DEADHEAD = "deadhead"
    GROUND_TRANSFER = "ground_transfer"
    REST = "rest"


class PassengerItineraryStatus(str, Enum):
    TRANSPORTED = "transported"
    UNSERVED = "unserved"


class PassengerSegmentType(str, Enum):
    FLIGHT = "flight"
    SURFACE = "surface"


CostComponents = dict[str, float | None]


class FlightOption(SchemaModel):
    option_id: str = Field(min_length=1)
    base_flight_id: str | None
    operation_type: FlightOperationType
    change_types: list[FlightChangeType]
    origin: str | None
    destination: str | None
    dep_time: AwareDatetime | None
    arr_time: AwareDatetime | None
    block_minutes: int | None = Field(ge=1)
    departure_delay_minutes: int | None = Field(ge=0)
    arrival_delay_minutes: int | None = Field(ge=0)
    notes: str = ""

    @model_validator(mode="after")
    def validate_operation_shape(self):
        if len(self.change_types) != len(set(self.change_types)):
            raise ValueError("change_types must contain unique values")
        actual_fields = (self.origin, self.destination, self.dep_time, self.arr_time, self.block_minutes)
        if self.operation_type is FlightOperationType.CANCEL:
            if self.base_flight_id is None:
                raise ValueError("cancel option requires base_flight_id")
            if any(value is not None for value in actual_fields + (self.departure_delay_minutes, self.arrival_delay_minutes)):
                raise ValueError("cancel option cannot contain operated-flight fields")
            if self.change_types != [FlightChangeType.CANCEL]:
                raise ValueError("cancel option requires change_types=['cancel']")
        else:
            if any(value is None for value in actual_fields):
                raise ValueError("operated and ferry options require route, times, and block_minutes")
            assert self.dep_time is not None and self.arr_time is not None
            if self.dep_time >= self.arr_time:
                raise ValueError("dep_time must be before arr_time")
            if self.operation_type is FlightOperationType.OPERATE:
                if self.base_flight_id is None:
                    raise ValueError("operate option requires base_flight_id")
                if self.departure_delay_minutes is None or self.arrival_delay_minutes is None:
                    raise ValueError("operate option requires departure and arrival delay")
                if FlightChangeType.CANCEL in self.change_types or FlightChangeType.POSITIONING in self.change_types:
                    raise ValueError("operate option has incompatible change_types")
            else:
                if self.base_flight_id is not None:
                    raise ValueError("ferry option cannot have base_flight_id")
                if FlightChangeType.POSITIONING not in self.change_types:
                    raise ValueError("ferry option requires positioning change type")
                if self.departure_delay_minutes is not None or self.arrival_delay_minutes is not None:
                    raise ValueError("ferry option cannot declare delay against a base flight")
            if FlightChangeType.UNCHANGED in self.change_types and len(self.change_types) != 1:
                raise ValueError("unchanged cannot be combined with another change type")
        return self


class AircraftString(SchemaModel):
    string_id: str = Field(min_length=1)
    aircraft_id: str = Field(min_length=1)
    leg_option_ids: list[str]
    start_station: str = Field(min_length=1)
    end_station: str = Field(min_length=1)
    maintenance_satisfied: bool
    cost_components: CostComponents = Field(default_factory=dict)
    notes: str = ""


class CrewSegment(SchemaModel):
    segment_type: CrewSegmentType
    flight_option_id: str | None
    origin: str | None
    destination: str | None
    start_time: AwareDatetime | None
    end_time: AwareDatetime | None
    notes: str = ""

    @model_validator(mode="after")
    def validate_segment_shape(self):
        if self.segment_type in {CrewSegmentType.OPERATE, CrewSegmentType.DEADHEAD}:
            if self.flight_option_id is None:
                raise ValueError("flight segment requires flight_option_id")
        else:
            if self.flight_option_id is not None:
                raise ValueError("ground/rest segment cannot reference a flight option")
            if None in (self.origin, self.destination, self.start_time, self.end_time):
                raise ValueError("ground/rest segment requires route and times")
            assert self.start_time is not None and self.end_time is not None
            if self.start_time >= self.end_time:
                raise ValueError("start_time must be before end_time")
        return self


class CrewDuty(SchemaModel):
    duty_id: str = Field(min_length=1)
    segments: list[CrewSegment]


class CrewPairing(SchemaModel):
    pairing_id: str = Field(min_length=1)
    crew_id: str = Field(min_length=1)
    duties: list[CrewDuty]
    start_station: str = Field(min_length=1)
    end_station: str = Field(min_length=1)
    cost_components: CostComponents = Field(default_factory=dict)
    notes: str = ""


class PassengerSegment(SchemaModel):
    segment_type: PassengerSegmentType
    flight_option_id: str | None
    origin: str | None
    destination: str | None
    dep_time: AwareDatetime | None
    arr_time: AwareDatetime | None

    @model_validator(mode="after")
    def validate_segment_shape(self):
        if self.segment_type is PassengerSegmentType.FLIGHT:
            if self.flight_option_id is None:
                raise ValueError("flight segment requires flight_option_id")
        else:
            if self.flight_option_id is not None:
                raise ValueError("surface segment cannot reference a flight option")
            if None in (self.origin, self.destination, self.dep_time, self.arr_time):
                raise ValueError("surface segment requires route and times")
            assert self.dep_time is not None and self.arr_time is not None
            if self.dep_time >= self.arr_time:
                raise ValueError("dep_time must be before arr_time")
        return self


class PassengerItinerary(SchemaModel):
    itinerary_id: str = Field(min_length=1)
    pax_group_id: str = Field(min_length=1)
    status: PassengerItineraryStatus
    segments: list[PassengerSegment]
    final_destination: str | None
    arrival_time: AwareDatetime | None
    arrival_delay_minutes: int | None = Field(ge=0)
    cost_components: CostComponents = Field(default_factory=dict)
    notes: str = ""

    @model_validator(mode="after")
    def validate_status_shape(self):
        if self.status is PassengerItineraryStatus.TRANSPORTED:
            if not self.segments:
                raise ValueError("transported itinerary requires at least one segment")
            if None in (self.final_destination, self.arrival_time, self.arrival_delay_minutes):
                raise ValueError("transported itinerary requires destination, arrival, and delay")
        elif self.segments or any(
            value is not None
            for value in (self.final_destination, self.arrival_time, self.arrival_delay_minutes)
        ):
            raise ValueError("unserved itinerary cannot contain travel or arrival fields")
        return self


class RecoveryColumns(SchemaModel):
    schema_version: str = Field(pattern=r"^1\.0\.0$")
    scenario_id: str = Field(min_length=1)
    time_unit: str = Field(pattern=r"^minute$")
    notes: list[str] = Field(default_factory=list)
    flight_options: list[FlightOption]
    aircraft_strings: list[AircraftString]
    crew_pairings: list[CrewPairing]
    passenger_itineraries: list[PassengerItinerary]
