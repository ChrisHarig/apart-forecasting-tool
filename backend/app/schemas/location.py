from app.schemas.common import APIModel, JsonDict


class LocationRead(APIModel):
    id: int
    country_iso3: str
    name: str
    location_type: str
    latitude: float | None = None
    longitude: float | None = None
    admin1: str | None = None
    admin2: str | None = None
    source_id: str | None = None
    external_id: str | None = None
    metadata_json: JsonDict = {}

