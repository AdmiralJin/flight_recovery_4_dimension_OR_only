from pydantic import Field, model_validator

from .common import IdentifiedModel


class Aircraft(IdentifiedModel):
    tail_id: str = Field(min_length=1)
    equipment_type: str = Field(min_length=1)
    initial_station_at_t: str = Field(min_length=1)
    required_station_at_T_end: str = Field(min_length=1)
    maintenance_required: bool = False
    maintenance_stations: list[str] = Field(default_factory=list)
    original_rotation: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_maintenance(self):
        if self.maintenance_required and not self.maintenance_stations:
            raise ValueError("maintenance_stations is required when maintenance_required is true")
        if len(self.original_rotation) != len(set(self.original_rotation)):
            raise ValueError("original_rotation cannot contain duplicate flights")
        return self

