from pydantic import AwareDatetime, Field, model_validator

from .common import IdentifiedModel, minutes_between


class Flight(IdentifiedModel):
    flight_id: str = Field(min_length=1)
    origin: str = Field(min_length=1)
    destination: str = Field(min_length=1)
    sched_dep: AwareDatetime
    sched_arr: AwareDatetime
    duration: int = Field(gt=0, description="Scheduled block time in minutes")
    original_aircraft: str = Field(min_length=1)
    original_equipment: str = Field(min_length=1)
    original_crew: str = Field(min_length=1)
    strategic_flag: bool = False
    market_flag: bool = False
    min_seats: int = Field(default=0, ge=0)
    max_delay: int = Field(ge=0, description="Maximum recovery delay in minutes")

    @model_validator(mode="after")
    def validate_schedule(self):
        if self.origin == self.destination:
            raise ValueError("origin and destination must differ")
        if self.sched_dep >= self.sched_arr:
            raise ValueError("sched_dep must be before sched_arr")
        if minutes_between(self.sched_dep, self.sched_arr) != self.duration:
            raise ValueError("duration must equal sched_arr - sched_dep in whole minutes")
        if not self.market_flag and self.min_seats != 0:
            raise ValueError("min_seats must be 0 when market_flag is false")
        return self
