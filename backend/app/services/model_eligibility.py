"""Cautious model-readiness registry for aggregate Sentinel Atlas data."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Mapping, Sequence

from .data_quality import DataQualityReport, assess_data_quality
from .feature_availability import CountryFeatureAvailability, assess_feature_availability
from .normalization import NormalizedRecord, SourceDescriptor, coerce_date, normalize_iso3


MODEL_IDS = (
    "wastewater_trend_only",
    "forecast_hub_passthrough",
    "mobility_context_only",
    "news_event_signal",
    "multi_signal_ensemble",
    "insufficient_data",
)


@dataclass(frozen=True)
class ModelRequirement:
    """Transparent readiness requirements for one registered model mode."""

    model_id: str
    label: str
    description: str
    required_features: tuple[str, ...] = ()
    min_records: int = 0
    min_temporal_days: int = 0
    max_latest_age_days: int | None = None
    min_quality_score: float = 0.0
    min_feature_score: float = 0.0
    min_distinct_features: int = 0
    metadata_only_allowed: bool = False
    limitations: tuple[str, ...] = ()


@dataclass(frozen=True)
class ModelCandidateAssessment:
    """Eligibility details for a single model registry entry."""

    model_id: str
    eligible: bool
    readiness_score: float
    missing_features: tuple[str, ...] = ()
    missing_requirements: tuple[str, ...] = ()
    sources_used: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()


@dataclass(frozen=True)
class ModelEligibilityReport:
    """Final cautious model-readiness decision.

    The report deliberately carries no prediction payload. Route handlers should
    expose this as readiness metadata, not as a production forecast.
    """

    country_iso3: str
    selected_model: str
    eligible: bool
    readiness_score: float
    prediction: None = None
    prediction_generated: bool = False
    missing_features: tuple[str, ...] = ()
    missing_requirements: tuple[str, ...] = ()
    sources_used: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    quality_report: DataQualityReport | None = None
    feature_availability: CountryFeatureAvailability | None = None
    candidate_assessments: Mapping[str, ModelCandidateAssessment] = field(default_factory=dict)


MODEL_REGISTRY: Mapping[str, ModelRequirement] = {
    "wastewater_trend_only": ModelRequirement(
        model_id="wastewater_trend_only",
        label="Wastewater trend only",
        description="Descriptive trend readiness for connected aggregate wastewater records.",
        required_features=("wastewater",),
        min_records=6,
        min_temporal_days=21,
        max_latest_age_days=21,
        min_quality_score=0.45,
        min_feature_score=0.35,
        limitations=(
            "Trend-only readiness; does not estimate infections or produce forecasts.",
            "Requires aggregate wastewater data with provenance and recent observations.",
        ),
    ),
    "forecast_hub_passthrough": ModelRequirement(
        model_id="forecast_hub_passthrough",
        label="Forecast Hub passthrough",
        description="Readiness to pass through external validated forecast-hub records without generating forecasts.",
        required_features=("forecast_hub",),
        min_records=1,
        max_latest_age_days=30,
        min_quality_score=0.35,
        min_feature_score=0.25,
        limitations=(
            "Passthrough only; Sentinel Atlas does not create or alter forecast values.",
            "Forecast methodology and uncertainty must come from the external source provenance.",
        ),
    ),
    "mobility_context_only": ModelRequirement(
        model_id="mobility_context_only",
        label="Mobility context only",
        description="Contextual readiness for aggregate mobility metadata or records.",
        required_features=("mobility",),
        min_records=0,
        min_quality_score=0.0,
        min_feature_score=0.20,
        metadata_only_allowed=True,
        limitations=(
            "Context only; does not infer transmission, individual movement, or risk.",
            "Only aggregate mobility summaries are allowed.",
        ),
    ),
    "news_event_signal": ModelRequirement(
        model_id="news_event_signal",
        label="News/event signal",
        description="Readiness for provenance-backed aggregate event signals.",
        required_features=("news_event",),
        min_records=1,
        max_latest_age_days=30,
        min_quality_score=0.30,
        min_feature_score=0.25,
        limitations=(
            "Event signal only; not a public alert, diagnosis, or forecast.",
            "Requires source links or provenance metadata for interpretation.",
        ),
    ),
    "multi_signal_ensemble": ModelRequirement(
        model_id="multi_signal_ensemble",
        label="Multi-signal ensemble readiness",
        description="Cautious readiness gate for future aggregate multi-signal models.",
        required_features=("aggregate_public_health",),
        min_records=20,
        min_temporal_days=60,
        max_latest_age_days=21,
        min_quality_score=0.70,
        min_feature_score=0.40,
        min_distinct_features=3,
        limitations=(
            "Readiness gate only; this service does not train or run an ensemble.",
            "Requires multiple recent aggregate signals and strong provenance.",
        ),
    ),
    "insufficient_data": ModelRequirement(
        model_id="insufficient_data",
        label="Insufficient data",
        description="Honest fallback when requirements for cautious model readiness are missing.",
        limitations=(
            "No prediction is available.",
            "Connect aggregate records and provenance-backed source metadata before enabling model workflows.",
        ),
    ),
}


def evaluate_model_eligibility(
    country_iso3: str,
    records: Sequence[NormalizedRecord],
    sources: Sequence[SourceDescriptor | Mapping[str, object]] = (),
    *,
    requested_model: str | None = None,
    as_of_date: date | str | None = None,
) -> ModelEligibilityReport:
    """Evaluate model readiness and return `insufficient_data` when gates fail."""

    country = normalize_iso3(country_iso3)
    if not country or country == "GLOBAL":
        raise ValueError("country_iso3 must be a concrete ISO3 country code")

    today = coerce_date(as_of_date) or date.today()
    quality_report = assess_data_quality(country, records, sources, as_of_date=today)
    availability = assess_feature_availability(country, records, sources, as_of_date=today)

    candidate_assessments = {
        model_id: _assess_candidate(requirement, records, quality_report, availability, today)
        for model_id, requirement in MODEL_REGISTRY.items()
        if model_id != "insufficient_data"
    }

    warnings = [
        "No fake prediction is generated; this response is model-readiness metadata only.",
        "Sentinel Atlas accepts aggregate public-health/infrastructure records only.",
    ]

    if requested_model and requested_model not in MODEL_REGISTRY:
        warnings.append(f"Requested model '{requested_model}' is not registered.")
        return _insufficient_report(
            country,
            quality_report,
            availability,
            candidate_assessments,
            missing_requirements=(f"unknown_model:{requested_model}",),
            warnings=tuple(warnings),
        )

    if requested_model and requested_model != "insufficient_data":
        selected = candidate_assessments[requested_model]
        if selected.eligible:
            return _eligible_report(country, selected, quality_report, availability, candidate_assessments, warnings)
        return _insufficient_report(
            country,
            quality_report,
            availability,
            candidate_assessments,
            missing_features=selected.missing_features,
            missing_requirements=selected.missing_requirements,
            sources_used=selected.sources_used,
            warnings=tuple(warnings + list(selected.warnings)),
            limitations=selected.limitations,
        )

    eligible_candidates = [candidate for candidate in candidate_assessments.values() if candidate.eligible]
    if not eligible_candidates:
        missing_features = _unique(
            tuple(feature for candidate in candidate_assessments.values() for feature in candidate.missing_features)
        )
        missing_requirements = _unique(
            tuple(requirement for candidate in candidate_assessments.values() for requirement in candidate.missing_requirements)
        )
        return _insufficient_report(
            country,
            quality_report,
            availability,
            candidate_assessments,
            missing_features=missing_features,
            missing_requirements=missing_requirements,
            warnings=tuple(warnings),
        )

    selected = max(eligible_candidates, key=lambda candidate: candidate.readiness_score)
    return _eligible_report(country, selected, quality_report, availability, candidate_assessments, warnings)


def _assess_candidate(
    requirement: ModelRequirement,
    records: Sequence[NormalizedRecord],
    quality_report: DataQualityReport,
    availability: CountryFeatureAvailability,
    as_of_date: date,
) -> ModelCandidateAssessment:
    country_records = tuple(record for record in records if record.country_iso3 == quality_report.country_iso3)
    feature_scores = {
        feature: availability.features.get(feature)
        for feature in requirement.required_features
    }

    missing_features = tuple(
        feature
        for feature, feature_availability in feature_scores.items()
        if feature_availability is None
        or not feature_availability.available
        or feature_availability.score < requirement.min_feature_score
    )

    sources_used = _unique(
        tuple(
            source_id
            for feature_availability in feature_scores.values()
            if feature_availability is not None
            for source_id in feature_availability.source_ids
        )
    )

    missing_requirements: list[str] = []
    warnings: list[str] = []

    if len(country_records) < requirement.min_records:
        missing_requirements.append(f"min_records:{requirement.min_records}")

    if not requirement.metadata_only_allowed and requirement.min_records == 0 and not sources_used:
        missing_requirements.append("source_metadata")

    if requirement.min_temporal_days:
        temporal_days = _temporal_span_days(country_records)
        if temporal_days < requirement.min_temporal_days:
            missing_requirements.append(f"min_temporal_days:{requirement.min_temporal_days}")

    if requirement.max_latest_age_days is not None:
        latest = max((record.date for record in country_records), default=None)
        if latest is None:
            missing_requirements.append("latest_observation_date")
        else:
            age_days = max((as_of_date - latest).days, 0)
            if age_days > requirement.max_latest_age_days:
                missing_requirements.append(f"max_latest_age_days:{requirement.max_latest_age_days}")

    if quality_report.overall_score < requirement.min_quality_score:
        missing_requirements.append(f"min_quality_score:{requirement.min_quality_score}")

    if requirement.min_distinct_features:
        available_features = tuple(
            feature
            for feature, feature_availability in availability.features.items()
            if feature_availability.available
            and feature_availability.record_count > 0
            and feature_availability.score >= requirement.min_feature_score
        )
        if len(available_features) < requirement.min_distinct_features:
            missing_requirements.append(f"min_distinct_features:{requirement.min_distinct_features}")

    if requirement.metadata_only_allowed and not any(
        availability.features.get(feature) and availability.features[feature].record_count
        for feature in requirement.required_features
    ):
        warnings.append("Only source metadata is available; no aggregate records are connected for this context.")

    feature_score = _average_feature_score(requirement.required_features, availability)
    readiness_score = _readiness_score(requirement, quality_report.overall_score, feature_score, country_records, as_of_date)
    eligible = not missing_features and not missing_requirements

    return ModelCandidateAssessment(
        model_id=requirement.model_id,
        eligible=eligible,
        readiness_score=readiness_score if eligible else min(readiness_score, 0.49),
        missing_features=missing_features,
        missing_requirements=tuple(_unique(tuple(missing_requirements))),
        sources_used=sources_used,
        warnings=tuple(warnings),
        limitations=requirement.limitations,
    )


def _readiness_score(
    requirement: ModelRequirement,
    quality_score: float,
    feature_score: float,
    records: Sequence[NormalizedRecord],
    as_of_date: date,
) -> float:
    recency_component = 0.0
    latest = max((record.date for record in records), default=None)
    if latest is not None:
        age_days = max((as_of_date - latest).days, 0)
        if requirement.max_latest_age_days:
            recency_component = max(0.0, min(1.0, 1.0 - (age_days / (requirement.max_latest_age_days * 3))))
        else:
            recency_component = 0.5

    score = (quality_score * 0.50) + (feature_score * 0.35) + (recency_component * 0.15)
    if requirement.metadata_only_allowed and not records:
        score = min(score, 0.50)
    return round(min(score, 1.0), 3)


def _eligible_report(
    country: str,
    selected: ModelCandidateAssessment,
    quality_report: DataQualityReport,
    availability: CountryFeatureAvailability,
    candidate_assessments: Mapping[str, ModelCandidateAssessment],
    warnings: Sequence[str],
) -> ModelEligibilityReport:
    return ModelEligibilityReport(
        country_iso3=country,
        selected_model=selected.model_id,
        eligible=True,
        readiness_score=selected.readiness_score,
        prediction=None,
        prediction_generated=False,
        missing_features=(),
        missing_requirements=(),
        sources_used=selected.sources_used,
        warnings=tuple(_unique(tuple(warnings) + selected.warnings)),
        limitations=selected.limitations,
        quality_report=quality_report,
        feature_availability=availability,
        candidate_assessments=candidate_assessments,
    )


def _insufficient_report(
    country: str,
    quality_report: DataQualityReport,
    availability: CountryFeatureAvailability,
    candidate_assessments: Mapping[str, ModelCandidateAssessment],
    *,
    missing_features: Sequence[str] = (),
    missing_requirements: Sequence[str] = (),
    sources_used: Sequence[str] = (),
    warnings: Sequence[str] = (),
    limitations: Sequence[str] = (),
) -> ModelEligibilityReport:
    insufficient = MODEL_REGISTRY["insufficient_data"]
    default_limitations = insufficient.limitations
    return ModelEligibilityReport(
        country_iso3=country,
        selected_model="insufficient_data",
        eligible=False,
        readiness_score=0.0,
        prediction=None,
        prediction_generated=False,
        missing_features=tuple(_unique(tuple(missing_features))),
        missing_requirements=tuple(_unique(tuple(missing_requirements))),
        sources_used=tuple(_unique(tuple(sources_used))),
        warnings=tuple(_unique(tuple(warnings))),
        limitations=tuple(_unique(tuple(limitations) + default_limitations)),
        quality_report=quality_report,
        feature_availability=availability,
        candidate_assessments=candidate_assessments,
    )


def _average_feature_score(
    features: Sequence[str],
    availability: CountryFeatureAvailability,
) -> float:
    if not features:
        return 0.0
    scores = [
        availability.features[feature].score
        for feature in features
        if feature in availability.features
    ]
    if not scores:
        return 0.0
    return sum(scores) / len(features)


def _temporal_span_days(records: Sequence[NormalizedRecord]) -> int:
    if not records:
        return 0
    dates = sorted({record.date for record in records})
    return (dates[-1] - dates[0]).days + 1


def _unique(values: Sequence[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        output.append(value)
    return tuple(output)


class ModelEligibilityService:
    """Database-backed model-readiness facade for FastAPI routes."""

    def __init__(self, db) -> None:
        self.db = db

    def evaluate(
        self,
        country_iso3: str,
        *,
        requested_model_id: str | None = None,
        horizon_days: int = 14,
        target_signal: str = "public_health_signal",
    ) -> dict[str, object]:
        from datetime import UTC, datetime

        from app.services.feature_availability import (
            FeatureAvailabilityService,
            _db_and_registry_sources,
            _db_records_for_country,
        )

        country = normalize_iso3(country_iso3) or country_iso3.upper()
        records = _db_records_for_country(self.db, country)
        sources = _db_and_registry_sources(self.db, country)
        report = evaluate_model_eligibility(
            country,
            records,
            sources,
            requested_model=requested_model_id,
        )
        features = FeatureAvailabilityService(self.db).compute_features(country)
        eligible_models = [
            {
                "id": model_id,
                "eligible": assessment.eligible,
                "readinessScore": assessment.readiness_score,
                "missingFeatures": list(assessment.missing_features),
                "missingRequirements": list(assessment.missing_requirements),
            }
            for model_id, assessment in report.candidate_assessments.items()
            if assessment.eligible
        ]
        warnings = [{"code": "model_readiness", "message": warning, "severity": "warning"} for warning in report.warnings]
        selected_model = report.selected_model
        report_eligible = report.eligible
        forced_missing_requirements = list(report.missing_requirements)
        if not records:
            selected_model = "insufficient_data"
            report_eligible = False
            forced_missing_requirements = list(_unique(tuple(forced_missing_requirements) + ("normalized_aggregate_records",)))
        if not report_eligible:
            warnings.append(
                {
                    "code": "insufficient_data",
                    "message": "The backend refused to fabricate model output.",
                    "severity": "warning",
                }
            )

        if report_eligible:
            explanation = (
                f"Selected {selected_model}. Output is limited to cautious aggregate readiness or trend support; "
                "this is not a validated outbreak prediction."
            )
        else:
            explanation = (
                "No model output was produced because required aggregate signals are missing, stale, or too low quality. "
                "The backend refused to fabricate predictions."
            )

        return {
            "country_iso3": country,
            "selected_model_id": selected_model,
            "eligible_models": eligible_models,
            "output_status": "complete" if report_eligible else "insufficient_data",
            "features": features,
            "missing_features": list(report.missing_features or tuple(forced_missing_requirements)),
            "sources_used": list(report.sources_used),
            "data_quality_score": report.quality_report.overall_score if report.quality_report else 0.0,
            "warnings": warnings,
            "limitations": list(report.limitations),
            "explanation": explanation,
            "generated_at": datetime.now(UTC),
            "horizon_days": horizon_days,
            "target_signal": target_signal,
        }

    def build_placeholder_output_points(self, eligibility: Mapping[str, object]) -> list[dict[str, object]]:
        if eligibility.get("selected_model_id") != "wastewater_trend_only":
            return []

        from sqlalchemy import select

        from app.db import models

        country = str(eligibility["country_iso3"]).upper()
        rows = self.db.execute(
            select(models.Observation)
            .where(
                models.Observation.country_iso3 == country,
                models.Observation.signal_category == "wastewater",
            )
            .order_by(models.Observation.observed_at.asc())
        ).scalars().all()
        if len(rows) < 2:
            return []
        first = rows[0].normalized_value if rows[0].normalized_value is not None else rows[0].value
        latest = rows[-1].normalized_value if rows[-1].normalized_value is not None else rows[-1].value
        relative_change = 0.0 if first == 0 else (latest - first) / abs(first)
        return [
            {
                "date": rows[-1].observed_at.date(),
                "metric": "observed_wastewater_relative_change",
                "value": round(relative_change, 6),
                "lower": None,
                "upper": None,
                "unit": "relative_change",
            }
        ]
