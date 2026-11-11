from pydantic import AwareDatetime, Field, model_validator, model_serializer

from .common import IdentifiedModel, SchemaModel


class AircraftUnavailableInterval(SchemaModel):
    start: AwareDatetime
    end: AwareDatetime

    @model_validator(mode="after")
    def validate_interval(self):
        if self.start >= self.end:
            raise ValueError("unavailability start must precede end")
        return self


class Aircraft(IdentifiedModel):
    tail_id: str = Field(min_length=1)
    equipment_type: str = Field(min_length=1)
    initial_station_at_t: str = Field(min_length=1)
    required_station_at_T_end: str = Field(min_length=1)
    maintenance_required: bool = False
    maintenance_stations: list[str] = Field(default_factory=list)
    original_rotation: list[str] = Field(default_factory=list)
    ready_at: AwareDatetime | None = None
    available_until: AwareDatetime | None = None
    unavailable: list[AircraftUnavailableInterval] = Field(default_factory=list)
    boundary_from_fixed_context: bool = False

    @model_serializer(mode="wrap")
    def serialize_legacy_compatible(self, handler):
        data = handler(self)
        for key in ("ready_at", "available_until", "unavailable"):
            if not data.get(key):
                data.pop(key, None)
        if not self.boundary_from_fixed_context:
            data.pop("boundary_from_fixed_context", None)
        return data

    @model_validator(mode="after")
    def validate_maintenance(self):
        if self.maintenance_required and not self.maintenance_stations:
            raise ValueError("maintenance_stations is required when maintenance_required is true")
        if len(self.original_rotation) != len(set(self.original_rotation)):
            raise ValueError("original_rotation cannot contain duplicate flights")
        return self

