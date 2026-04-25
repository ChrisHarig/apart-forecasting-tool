from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db, models
from app.schemas.location import LocationRead

router = APIRouter(tags=["locations"])


def _list_locations(
    db: Session,
    *,
    country_iso3: str | None = None,
    location_type: str | None = None,
) -> list[models.Location]:
    query = select(models.Location)
    if country_iso3:
        query = query.where(models.Location.country_iso3 == country_iso3.upper())
    if location_type:
        query = query.where(models.Location.location_type == location_type)
    return db.execute(query.order_by(models.Location.name)).scalars().all()


@router.get("/locations", response_model=list[LocationRead], response_model_by_alias=False)
def list_locations(
    country_iso3: str | None = Query(default=None, alias="countryIso3"),
    type_: str | None = Query(default=None, alias="type"),
    db: Session = Depends(get_db),
) -> list[models.Location]:
    return _list_locations(db, country_iso3=country_iso3, location_type=type_)


@router.get("/ports", response_model=list[LocationRead], response_model_by_alias=False)
def list_ports(country_iso3: str | None = Query(default=None, alias="countryIso3"), db: Session = Depends(get_db)):
    return _list_locations(db, country_iso3=country_iso3, location_type="port")


@router.get("/airports", response_model=list[LocationRead], response_model_by_alias=False)
def list_airports(country_iso3: str | None = Query(default=None, alias="countryIso3"), db: Session = Depends(get_db)):
    return _list_locations(db, country_iso3=country_iso3, location_type="airport")


@router.get("/wastewater-sites", response_model=list[LocationRead], response_model_by_alias=False)
def list_wastewater_sites(
    country_iso3: str | None = Query(default=None, alias="countryIso3"),
    db: Session = Depends(get_db),
):
    return _list_locations(db, country_iso3=country_iso3, location_type="wastewater_site")
