from pydantic import AwareDatetime, Field, model_validator, model_serializer

from .aircraft import Aircraft
from .airport import Airport
from .capacity import AirportInterval
from .common import IdentifiedModel, SchemaModel
from .crew import Crew
from .disruption import Disruption
from .flight import Flight
from .passenger import PassengerCommodity


class RecoveryWindow(SchemaModel):
    start_time: AwareDatetime
    end_time: AwareDatetime

    @model_validator(mode="after")
    def validate_window(self):
        if self.start_time >= self.end_time:
            raise ValueError("start_time must be before end_time")
        return self


class Scenario(IdentifiedModel):
    scenario_id: str = Field(min_length=1)
    recovery_window: RecoveryWindow
    crew_enabled: bool = True
    airports: list[Airport] = Field(min_length=1)
    flights: list[Flight] = Field(default_factory=list)
    aircraft: list[Aircraft] = Field(default_factory=list)
    crew: list[Crew] = Field(default_factory=list)
    passengers: list[PassengerCommodity] = Field(default_factory=list)
    airport_intervals: list[AirportInterval] = Field(default_factory=list)
    disruptions: list[Disruption] = Field(default_factory=list)

    @model_serializer(mode="wrap")
    def serialize_legacy_compatible(self, handler):
        data = handler(self)
        if self.crew_enabled:
            data.pop("crew_enabled", None)
        return data
