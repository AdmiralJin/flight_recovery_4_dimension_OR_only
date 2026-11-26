from pydantic import Field, model_validator

from .common import IdentifiedModel


class Crew(IdentifiedModel):
    crew_id: str = Field(min_length=1)
    rating: str = Field(min_length=1, description="Qualified equipment type for Phase 0")
    start_station_at_t: str = Field(min_length=1)
    required_station_at_T_end: str = Field(min_length=1)
    original_duties: list[list[str]] = Field(default_factory=list)
    original_pairing: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_pairing_shape(self):
        flattened = [flight_id for duty in self.original_duties for flight_id in duty]
        if len(flattened) != len(set(flattened)):
            raise ValueError("original_duties cannot contain duplicate flights")
        if flattened != self.original_pairing:
            raise ValueError("original_pairing must equal original_duties flattened in order")
        return self

