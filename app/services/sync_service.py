"""
sync_service.py
Orchestrates the full pipeline:
  Google Sheets row → parse → score → upsert DB → generate card (if post survey)

Called by both:
  - /webhook/form-submit  (Apps Script trigger, real-time)
  - /api/sync             (manual pull, staff-initiated)
"""
from sqlalchemy.exc import IntegrityError
from flask import current_app

from app import db
from app.models import Participant, SurveyResponse, GrowthCard
from app.services.sheets_service import fetch_all_rows, parse_row
from app.services.score_service import compute_all_totals, compute_change_scores


def process_row(raw_row: list, row_index: int) -> dict:
    """
    Parse one raw sheet row, upsert participant + response,
    and trigger card generation if this is a post-survey submission
    with a matching pre-survey on record.
    Returns a status dict for logging.
    """
    try:
        row_index = int(row_index)
    except (TypeError, ValueError):
        return {"status": "skipped", "reason": "invalid row index"}

    if row_index < 2:
        return {"status": "skipped", "reason": "invalid row index"}

    parsed = parse_row(raw_row, row_index)
    code = (parsed.get("code") or "").strip().upper()
    survey_type = (parsed.get("survey_type") or "").strip().lower()

    if not code or survey_type not in ("pre", "post"):
        return {"status": "skipped", "reason": "missing code or invalid type"}

    default_cohort = current_app.config.get("DEFAULT_COHORT")

    # ── Upsert participant ───────────────────────────────────────────────────
    participant = Participant.query.filter_by(code=code).first()
    if not participant:
        participant = Participant(code=code, cohort=default_cohort)
        db.session.add(participant)
        db.session.flush()   # get participant.id before commit
    elif not participant.cohort and default_cohort:
        participant.cohort = default_cohort

    # ── Compute scores and persist ───────────────────────────────────────────
    totals = compute_all_totals(parsed)
    expected_totals = {
        "act_total": "ACT SG",
        "cmi_total": "CMI",
        "rsem_total": "Rosenberg",
        "ewb_total": "Well-Being",
    }
    missing_scales = [label for key, label in expected_totals.items() if key not in totals]
    if missing_scales:
        current_app.logger.warning(
            "Partial row %s (%s): missing items for %s",
            row_index,
            code,
            ", ".join(missing_scales),
        )

    incoming_complete = all(key in totals for key in expected_totals)

    # ── Deduplicate/backfill by sheet row index ──────────────────────────────
    existing = SurveyResponse.query.filter_by(sheet_row_index=row_index).first()
    backfilled = False
    if existing:
        if existing.participant_id != participant.id or existing.survey_type != survey_type:
            current_app.logger.error(
                "Conflicting row identity for row_index=%s existing(participant_id=%s,survey_type=%s) incoming(participant_id=%s,survey_type=%s)",
                row_index,
                existing.participant_id,
                existing.survey_type,
                participant.id,
                survey_type,
            )
            return {"status": "failed", "reason": "conflicting row identity", "code": code}

        existing_complete = all(
            getattr(existing, key) is not None for key in expected_totals
        )
        if existing_complete:
            return {"status": "skipped", "reason": "already processed", "code": code}

        if not incoming_complete:
            return {"status": "skipped", "reason": "already processed", "code": code}

        response = existing
        backfilled = True
    else:
        response = SurveyResponse(
            participant_id=participant.id,
            survey_type=survey_type,
        )
        db.session.add(response)

    parsed.update(totals)
    parsed.pop("timestamp", None)
    parsed.pop("code", None)
    parsed.pop("survey_type", None)

    for key, value in parsed.items():
        if hasattr(SurveyResponse, key):
            setattr(response, key, value)

    db.session.flush()

    # ── Commit participant + survey response before card generation ───────────
    # Card generation (WeasyPrint) can fail independently; survey data must be
    # persisted regardless so submissions are never lost on a render error.
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return {"status": "skipped", "reason": "already processed", "code": code}

    if backfilled:
        saved_status = "post_backfilled_no_pre" if survey_type == "post" else "pre_backfilled"
    else:
        saved_status = "post_saved_no_pre" if survey_type == "post" else "pre_saved"

    # ── Generate growth card if this is the post-survey ──────────────────────
    if survey_type == "post":
        pre_response = SurveyResponse.query.filter_by(
            participant_id=participant.id, survey_type="pre"
        ).first()

        if pre_response:
            from app.services.card_service import generate_card

            pre_dict  = pre_response.to_dict()
            post_dict = response.to_dict()
            deltas    = compute_change_scores(pre_dict, post_dict)

            try:
                card_path = generate_card(
                    participant_code=code,
                    pre=pre_dict,
                    post=post_dict,
                    deltas=deltas,
                    cohort=participant.cohort or "platform",
                )
            except Exception:
                current_app.logger.exception("Card generation failed for row %s (%s)", row_index, code)
                return {
                    "status": "post_saved_card_failed",
                    "reason": "card generation failed",
                    "code": code,
                    "row_index": row_index,
                }

            card = GrowthCard.query.filter_by(participant_id=participant.id).first()
            if card:
                card.file_path = card_path
                for key, value in deltas.items():
                    if hasattr(card, key):
                        setattr(card, key, value)
            else:
                card = GrowthCard(
                    participant_id=participant.id,
                    file_path=card_path,
                    **deltas,
                )
                db.session.add(card)

            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                return {"status": "skipped", "reason": "already processed", "code": code}

            return {"status": "card_generated", "code": code, "path": card_path}

    return {"status": saved_status, "code": code}


def sync_all_from_sheets() -> list:
    """
    Fetches every row from the sheet and processes each one.
    Safe to run multiple times — deduplication prevents double entries.
    """
    rows = fetch_all_rows()
    results = []
    for i, row in enumerate(rows, start=2):   # start=2 because row 1 is header
        result = process_row(row, row_index=i)
        results.append(result)
    return results