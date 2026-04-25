from app.schemas.common import APIModel, JsonDict


class CountryRead(APIModel):
    iso3: str
    iso2: str | None = None
    iso_numeric: str | None = None
    name: str
    region: str | None = None
    subregion: str | None = None
    centroid: JsonDict | None = None
    bbox: JsonDict | None = None
    population: int | None = None
    metadata_json: JsonDict = {}

