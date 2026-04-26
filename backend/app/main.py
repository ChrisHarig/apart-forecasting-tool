from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    countries,
    forecast_benchmarks,
    forecast_challenges,
    forecast_models,
    locations,
    model_runs,
    news,
    sources,
    timeseries,
)
from app.config import get_settings
from app.db import init_db


settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.create_db_on_startup:
        init_db()
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description=(
        "Aggregate public-health data readiness backend for Sentinel Atlas. "
        "The service tracks country/source availability, provenance, quality, and cautious model eligibility."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(countries.router, prefix=settings.api_prefix)
app.include_router(sources.router, prefix=settings.api_prefix)
app.include_router(timeseries.router, prefix=settings.api_prefix)
app.include_router(locations.router, prefix=settings.api_prefix)
app.include_router(news.router, prefix=settings.api_prefix)
app.include_router(model_runs.router, prefix=settings.api_prefix)
app.include_router(forecast_models.router, prefix=settings.api_prefix)
app.include_router(forecast_benchmarks.router, prefix=settings.api_prefix)
app.include_router(forecast_challenges.router, prefix=settings.api_prefix)


@app.get("/health", tags=["health"])
def health() -> dict:
    return {
        "status": "ok",
        "service": settings.app_name,
        "safety": "aggregate public-health and infrastructure data only",
    }
