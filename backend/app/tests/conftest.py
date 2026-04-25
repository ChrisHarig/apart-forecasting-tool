from __future__ import annotations

import os
import importlib
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest


@pytest.fixture(scope="session")
def fastapi_app() -> Any:
    db_dir = Path(__file__).resolve().parents[2] / ".test-data"
    db_dir.mkdir(exist_ok=True)
    db_path = db_dir / "sentinel_test.db"
    if db_path.exists():
        db_path.unlink()
    os.environ["SENTINEL_DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    os.environ["SENTINEL_ENVIRONMENT"] = "test"

    module = importlib.import_module("app.main")
    return module.app


@pytest.fixture()
def client(fastapi_app: Any) -> Iterator[Any]:
    testclient_module = pytest.importorskip("fastapi.testclient")
    with testclient_module.TestClient(fastapi_app) as test_client:
        from app.db.models import Base
        from app.db.session import SessionLocal, engine

        Base.metadata.create_all(bind=engine)
        with SessionLocal() as db:
            for table in reversed(Base.metadata.sorted_tables):
                db.execute(table.delete())
            db.commit()
        yield test_client


@pytest.fixture()
def aggregate_csv() -> tuple[str, bytes]:
    content = (
        "sourceId,countryIso3,observedAt,reportedAt,signalCategory,metric,value,unit,normalizedValue,qualityScore,provenanceUrl\n"
        "fixture_wastewater,USA,2026-04-01T00:00:00Z,2026-04-03T00:00:00Z,wastewater,viral_signal,10,copies_ml,10,0.8,https://example.test/a\n"
        "fixture_wastewater,USA,2026-04-05T00:00:00Z,2026-04-07T00:00:00Z,wastewater,viral_signal,12,copies_ml,12,0.8,https://example.test/b\n"
        "fixture_wastewater,USA,2026-04-09T00:00:00Z,2026-04-11T00:00:00Z,wastewater,viral_signal,13,copies_ml,13,0.8,https://example.test/c\n"
        "fixture_wastewater,USA,2026-04-13T00:00:00Z,2026-04-15T00:00:00Z,wastewater,viral_signal,15,copies_ml,15,0.82,https://example.test/d\n"
        "fixture_wastewater,USA,2026-04-17T00:00:00Z,2026-04-19T00:00:00Z,wastewater,viral_signal,17,copies_ml,17,0.82,https://example.test/e\n"
        "fixture_wastewater,USA,2026-04-22T00:00:00Z,2026-04-23T00:00:00Z,wastewater,viral_signal,20,copies_ml,20,0.84,https://example.test/f\n"
    )
    return "fixture-aggregate.csv", content.encode("utf-8")


@pytest.fixture()
def privacy_risk_csv() -> tuple[str, bytes]:
    content = (
        "sourceId,countryIso3,observedAt,signalCategory,metric,value,person_id\n"
        "fixture_cases,USA,2026-04-01T00:00:00Z,clinical,case_count,1,person-1\n"
    )
    return "privacy-risk.csv", content.encode("utf-8")
