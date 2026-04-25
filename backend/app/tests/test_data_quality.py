from __future__ import annotations

from datetime import date, timedelta

from app.services.data_quality import (
    assess_data_quality,
    score_recency,
    score_reporting_lag,
    score_temporal_coverage,
    score_uncertainty,
)
from app.services.normalization import NormalizedRecord, Provenance


def _records() -> tuple[NormalizedRecord, ...]:
    today = date.today()
    return (
        NormalizedRecord(
            source_id="fixture_wastewater",
            country_iso3="USA",
            metric="viral_signal",
            date=today - timedelta(days=14),
            value=10,
            provenance=Provenance(source_url="https://example.test/a"),
            reported_at=today - timedelta(days=12),
        ),
        NormalizedRecord(
            source_id="fixture_wastewater",
            country_iso3="USA",
            metric="viral_signal",
            date=today,
            value=12,
            provenance=Provenance(source_url="https://example.test/b"),
            reported_at=today,
        ),
    )


def test_transparent_data_quality_scores_are_bounded() -> None:
    records = _records()
    assert 0 <= score_temporal_coverage(records, expected_window_days=30, expected_interval_days=7).score <= 1
    assert score_reporting_lag(records).score == 1.0
    assert 0 <= score_uncertainty(records, ("fixture_wastewater",)).score <= 1


def test_recency_score_degrades_for_stale_data() -> None:
    records = _records()
    stale = (
        NormalizedRecord(
            source_id="fixture_wastewater",
            country_iso3="USA",
            metric="viral_signal",
            date=date.today() - timedelta(days=120),
            value=1,
        ),
    )

    assert score_recency(records, date.today()).score == 1.0
    assert score_recency(stale, date.today()).score == 0.0


def test_quality_report_does_not_claim_prediction() -> None:
    report = assess_data_quality("USA", _records())

    assert 0 <= report.overall_score <= 1
    assert "not outbreak risk estimates" in " ".join(report.limitations).lower()
