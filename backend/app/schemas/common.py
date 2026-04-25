from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


def to_camel(value: str) -> str:
    parts = value.split("_")
    return parts[0] + "".join(part.capitalize() for part in parts[1:])


class APIModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


JsonDict = dict[str, Any]
JsonList = list[Any]


class DateRange(APIModel):
    start_date: date | None = None
    end_date: date | None = None


class Message(APIModel):
    message: str


class WarningMessage(APIModel):
    code: str
    message: str
    severity: str = Field(default="info")
    provenance: JsonDict | None = None

