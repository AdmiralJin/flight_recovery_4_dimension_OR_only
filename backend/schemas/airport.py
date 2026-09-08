from pydantic import Field

from .common import IdentifiedModel


class Airport(IdentifiedModel):
    airport_id: str = Field(min_length=1)
    name: str = Field(min_length=1)

