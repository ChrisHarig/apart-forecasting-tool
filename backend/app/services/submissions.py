from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models
from app.schemas.prediction_set import ReviewDecisionResponse, SubmitterResponse


SUBMISSION_TRACKS = {"internal_baseline", "public", "verified_group"}
REVIEW_STATUSES = {"unreviewed", "approved", "rejected", "needs_changes"}
VISIBILITY_VALUES = {"public", "private"}

PUBLIC_UNREVIEWED_WARNING = {
    "code": "public_submission_unreviewed",
    "message": "Public submission is unreviewed.",
    "severity": "warning",
}

VERIFIED_GROUP_METADATA_WARNING = {
    "code": "verified_group_metadata_only",
    "message": "Verified-group status is lightweight hackathon metadata, not cryptographic identity verification.",
    "severity": "warning",
}

METHOD_SUMMARY_RECOMMENDED_WARNING = {
    "code": "method_summary_recommended",
    "message": "A short methodSummary is recommended for public comparison.",
    "severity": "info",
}


@dataclass(frozen=True)
class SubmitterMetadata:
    submitter_id: int | None
    submitter_name: str | None
    submitter_email: str | None
    organization: str | None
    submission_track: str
    review_status: str
    visibility: str
    verification_status: str
    method_summary: str | None
    model_url: str | None
    code_url: str | None
    provenance_url: str | None
    disclosure_notes: str | None
    warnings: list[dict[str, str]]


def normalize_submitter_metadata(
    db: Session,
    *,
    submitter_name: str | None = None,
    submitter_email: str | None = None,
    organization: str | None = None,
    submission_track: str | None = None,
    method_summary: str | None = None,
    model_url: str | None = None,
    code_url: str | None = None,
    provenance_url: str | None = None,
    visibility: str | None = None,
    disclosure_notes: str | None = None,
    verified_group: bool = False,
    allow_missing_submitter: bool = False,
) -> SubmitterMetadata:
    track = validate_submission_track(submission_track or ("verified_group" if verified_group else "public"))
    visible = _validate_visibility(visibility or "public")
    name = _clean_text(submitter_name)
    email = _clean_text(submitter_email)
    org = _clean_text(organization)
    method = _clean_text(method_summary)
    model = _validate_metadata_url(model_url, "modelUrl")
    code = _validate_metadata_url(code_url, "codeUrl")
    provenance = _validate_metadata_url(provenance_url, "provenanceUrl")
    notes = _clean_text(disclosure_notes)
    warnings: list[dict[str, str]] = []

    if track in {"public", "verified_group"} and not name and not allow_missing_submitter:
        raise ValueError("submitterName is required for public or verified_group prediction uploads.")
    if track == "verified_group":
        warnings.append(VERIFIED_GROUP_METADATA_WARNING)
        if not org:
            warnings.append(
                {
                    "code": "organization_recommended",
                    "message": "organization is recommended for verified_group submissions.",
                    "severity": "info",
                }
            )
    if track == "public":
        warnings.append(PUBLIC_UNREVIEWED_WARNING)
    if track in {"public", "verified_group"} and not method:
        warnings.append(METHOD_SUMMARY_RECOMMENDED_WARNING)

    verification_status = "internal" if track == "internal_baseline" else "verified_group" if track == "verified_group" else "unverified"
    review_status = "approved" if track == "internal_baseline" else "unreviewed"
    submitter_id = None
    if name or track == "internal_baseline":
        submitter = get_or_create_submitter(
            db,
            display_name=name or "Sentinel Atlas backend",
            email=email,
            organization=org or ("Sentinel Atlas" if track == "internal_baseline" else None),
            verification_status=verification_status,
            affiliation_type=track,
        )
        submitter_id = submitter.id
        name = submitter.display_name
        org = submitter.organization

    return SubmitterMetadata(
        submitter_id=submitter_id,
        submitter_name=name,
        submitter_email=email,
        organization=org,
        submission_track=track,
        review_status=review_status,
        visibility=visible,
        verification_status=verification_status,
        method_summary=method,
        model_url=model,
        code_url=code,
        provenance_url=provenance,
        disclosure_notes=notes,
        warnings=warnings,
    )


def validate_submission_track(value: str) -> str:
    track = (value or "public").strip().lower()
    if track not in SUBMISSION_TRACKS:
        raise ValueError("submissionTrack must be internal_baseline, public, or verified_group.")
    return track


def apply_review_decision(
    db: Session,
    prediction_set_id: int,
    *,
    review_status: str,
    reviewer_name: str | None = None,
    review_notes: str | None = None,
) -> ReviewDecisionResponse:
    status = _validate_review_status(review_status)
    prediction_set = db.get(models.PredictionSet, prediction_set_id)
    if prediction_set is None:
        raise ValueError("Prediction set not found")
    prediction_set.review_status = status
    prediction_set.updated_at = datetime.now(UTC)
    decision = models.ReviewDecision(
        prediction_set_id=prediction_set_id,
        review_status=status,
        reviewer_name=_clean_text(reviewer_name),
        review_notes=_clean_text(review_notes),
        created_at=datetime.now(UTC),
    )
    db.add(decision)
    db.commit()
    db.refresh(decision)
    return review_decision_to_response(decision)


def get_latest_review_decision(db: Session, prediction_set_id: int) -> ReviewDecisionResponse | None:
    if db.get(models.PredictionSet, prediction_set_id) is None:
        raise ValueError("Prediction set not found")
    row = (
        db.execute(
            select(models.ReviewDecision)
            .where(models.ReviewDecision.prediction_set_id == prediction_set_id)
            .order_by(models.ReviewDecision.created_at.desc(), models.ReviewDecision.id.desc())
        )
        .scalars()
        .first()
    )
    return review_decision_to_response(row) if row else None


def list_submitters(db: Session) -> list[SubmitterResponse]:
    rows = db.execute(select(models.Submitter).order_by(models.Submitter.display_name.asc(), models.Submitter.id.asc())).scalars().all()
    return [submitter_to_response(row) for row in rows]


def get_submitter(db: Session, submitter_id: int) -> SubmitterResponse | None:
    row = db.get(models.Submitter, submitter_id)
    return submitter_to_response(row) if row else None


def get_or_create_submitter(
    db: Session,
    *,
    display_name: str,
    email: str | None,
    organization: str | None,
    verification_status: str,
    affiliation_type: str | None,
) -> models.Submitter:
    normalized_email = _clean_text(email)
    query = select(models.Submitter)
    if normalized_email:
        query = query.where(models.Submitter.email == normalized_email)
    else:
        query = query.where(
            models.Submitter.display_name == display_name,
            models.Submitter.organization == organization,
            models.Submitter.verification_status == verification_status,
        )
    row = db.execute(query).scalars().first()
    if row is None:
        row = models.Submitter(
            display_name=display_name,
            email=normalized_email,
            organization=organization,
            verification_status=verification_status,
            affiliation_type=affiliation_type,
            created_at=datetime.now(UTC),
        )
        db.add(row)
        db.flush()
    else:
        row.display_name = display_name
        row.organization = organization or row.organization
        row.verification_status = verification_status
        row.affiliation_type = affiliation_type or row.affiliation_type
        row.updated_at = datetime.now(UTC)
        db.flush()
    return row


def redact_private_submitter_fields(row: models.PredictionSet) -> dict[str, str | int | None]:
    submitter = row.submitter
    return {
        "submitter_id": row.submitter_id,
        "submitter_display_name": row.submitter_name or (submitter.display_name if submitter else None),
        "organization": row.organization or (submitter.organization if submitter else None),
        "verification_status": submitter.verification_status if submitter else None,
    }


def filter_leaderboard_by_track_and_review(
    rows: list[models.PredictionSet],
    *,
    submission_track: str = "all",
    review_status: str = "all",
    include_unreviewed: bool = True,
) -> list[models.PredictionSet]:
    track = (submission_track or "all").strip().lower()
    status_filter = (review_status or "all").strip().lower()
    if track != "all" and track not in SUBMISSION_TRACKS:
        raise ValueError("submissionTrack must be all, internal_baseline, public, or verified_group.")
    if status_filter != "all" and status_filter not in REVIEW_STATUSES:
        raise ValueError("reviewStatus must be all, approved, unreviewed, rejected, or needs_changes.")

    output: list[models.PredictionSet] = []
    for row in rows:
        is_builtin = row.submission_track == "internal_baseline"
        if row.visibility == "private" and not is_builtin:
            continue
        if track != "all" and row.submission_track != track and not is_builtin:
            continue
        if status_filter != "all" and row.review_status != status_filter:
            continue
        if not include_unreviewed and row.review_status == "unreviewed" and not is_builtin:
            continue
        output.append(row)
    return output


def submitter_to_response(row: models.Submitter) -> SubmitterResponse:
    return SubmitterResponse(
        id=row.id,
        display_name=row.display_name,
        organization=row.organization,
        affiliation_type=row.affiliation_type,
        verification_status=row.verification_status,
        notes=row.notes,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def review_decision_to_response(row: models.ReviewDecision) -> ReviewDecisionResponse:
    return ReviewDecisionResponse(
        id=row.id,
        prediction_set_id=row.prediction_set_id,
        review_status=row.review_status,
        reviewer_name=row.reviewer_name,
        review_notes=row.review_notes,
        created_at=row.created_at,
    )


def _validate_review_status(value: str) -> str:
    status = (value or "").strip().lower()
    if status not in REVIEW_STATUSES:
        raise ValueError("reviewStatus must be unreviewed, approved, rejected, or needs_changes.")
    return status


def _validate_visibility(value: str) -> str:
    visibility = (value or "public").strip().lower()
    if visibility not in VISIBILITY_VALUES:
        raise ValueError("visibility must be public or private.")
    return visibility


def _validate_metadata_url(value: str | None, field_name: str) -> str | None:
    cleaned = _clean_text(value)
    if cleaned is None:
        return None
    parsed = urlparse(cleaned)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"{field_name} must be a valid http(s) URL.")
    return cleaned


def _clean_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
