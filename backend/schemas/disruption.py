from pydantic import AwareDatetime, Field, model_validator

from .common import SchemaModel


class Disruption(SchemaModel):
    airport: str = Field(min_length=1)
    start_time: AwareDatetime
    end_time: AwareDatetime
    capacity_change: int
    restriction_type: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_interval(self):
        if self.start_time >= self.end_time:
            raise ValueError("start_time must be before end_time")
        if self.capacity_change == 0:
            raise ValueError("capacity_change must be non-zero")
        return self
