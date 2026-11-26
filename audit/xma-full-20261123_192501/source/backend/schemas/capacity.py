from pydantic import AwareDatetime, Field, model_validator

from .common import SchemaModel


class AirportInterval(SchemaModel):
    airport: str = Field(min_length=1)
    start_time: AwareDatetime
    end_time: AwareDatetime
    arr_capacity: int = Field(ge=0)
    dep_capacity: int = Field(ge=0)
    gate_capacity: int = Field(ge=0)
    curfew_flag: bool = False
    weather_restrictions: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_interval(self):
        if self.start_time >= self.end_time:
            raise ValueError("start_time must be before end_time")
        return self
