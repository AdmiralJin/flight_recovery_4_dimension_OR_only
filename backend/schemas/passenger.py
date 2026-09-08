from pydantic import AwareDatetime, Field

from .common import IdentifiedModel


class PassengerCommodity(IdentifiedModel):
    pax_group_id: str = Field(min_length=1)
    count: int = Field(gt=0)
    origin: str = Field(min_length=1)
    destination: str = Field(min_length=1)
    original_departure: AwareDatetime
    scheduled_arrival: AwareDatetime
    original_itinerary: list[str] = Field(min_length=1)
