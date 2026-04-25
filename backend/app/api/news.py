from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.utils import ensure_country
from app.db import get_db, models
from app.schemas.news import NewsEventCreate, NewsEventRead

router = APIRouter(tags=["news"])


def _dedupe_key(payload: NewsEventCreate) -> str:
    if payload.deduplication_key:
        return payload.deduplication_key
    return "|".join(
        [
            payload.country_iso3.upper(),
            payload.event_date.date().isoformat(),
            payload.source_name.lower().strip(),
            payload.headline.lower().strip(),
        ]
    )


@router.get("/countries/{iso3}/news/latest", response_model=list[NewsEventRead], response_model_by_alias=False)
def latest_country_news(iso3: str, limit: int = Query(default=10, ge=0, le=100), db: Session = Depends(get_db)):
    return db.execute(
        select(models.NewsEvent)
        .where(models.NewsEvent.country_iso3 == iso3.upper())
        .order_by(models.NewsEvent.event_date.desc(), models.NewsEvent.discovered_at.desc())
        .limit(limit)
    ).scalars().all()


@router.post("/ingest/news", response_model=NewsEventRead, response_model_by_alias=False, status_code=201)
def ingest_news(payload: NewsEventCreate, db: Session = Depends(get_db)):
    ensure_country(db, payload.country_iso3)
    event = models.NewsEvent(
        country_iso3=payload.country_iso3.upper(),
        event_date=payload.event_date,
        headline=payload.headline,
        summary=payload.summary,
        source_name=payload.source_name,
        source_url=str(payload.source_url) if payload.source_url else None,
        language=payload.language,
        related_pathogen=payload.related_pathogen,
        signal_category=payload.signal_category,
        severity=payload.severity,
        confidence=payload.confidence,
        location_name=payload.location_name,
        latitude=payload.latitude,
        longitude=payload.longitude,
        provenance=payload.provenance,
        deduplication_key=_dedupe_key(payload),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


@router.get("/news", response_model=list[NewsEventRead], response_model_by_alias=False)
def list_news(
    country_iso3: str | None = Query(default=None, alias="countryIso3"),
    start_date: datetime | None = Query(default=None, alias="startDate"),
    end_date: datetime | None = Query(default=None, alias="endDate"),
    signal_category: str | None = Query(default=None, alias="signalCategory"),
    db: Session = Depends(get_db),
):
    query = select(models.NewsEvent)
    if country_iso3:
        query = query.where(models.NewsEvent.country_iso3 == country_iso3.upper())
    if start_date:
        query = query.where(models.NewsEvent.event_date >= start_date)
    if end_date:
        query = query.where(models.NewsEvent.event_date <= end_date)
    if signal_category:
        query = query.where(models.NewsEvent.signal_category == signal_category)
    return db.execute(query.order_by(models.NewsEvent.event_date.desc())).scalars().all()
