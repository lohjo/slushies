"""
sync_service.py
Orchestrates the full pipeline:
  Google Sheets row → parse → score → upsert DB → generate card (if post survey)

Called by both:
  - /webhook/form-submit  (Apps Script trigger, real-time)
  - /api/sync             (manual pull, staff-initiated)
"""
from sqlalchemy.exc import IntegrityError

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

    # ── Upsert participant ───────────────────────────────────────────────────
    participant = Participant.query.filter_by(code=code).first()
    if not participant:
        participant = Participant(code=code)
        db.session.add(participant)
        db.session.flush()   # get participant.id before commit

    # ── Deduplicate by sheet row index ───────────────────────────────────────
    existing = SurveyResponse.query.filter_by(sheet_row_index=row_index).first()
    if existing:
        return {"status": "skipped", "reason": "already processed", "code": code}

    # ── Compute scores and persist ───────────────────────────────────────────
    totals = compute_all_totals(parsed)
    parsed.update(totals)
    parsed.pop("timestamp", None)
    parsed.pop("code", None)
    parsed.pop("survey_type", None)

    response = SurveyResponse(
        participant_id=participant.id,
        survey_type=survey_type,
        **{k: v for k, v in parsed.items() if hasattr(SurveyResponse, k)},
    )
    db.session.add(response)
    try:
        db.session.commit()
    except IntegrityError:
        # Concurrent webhook retries can race; DB uniqueness is the final guardrail.
        db.session.rollback()
        return {"status": "skipped", "reason": "already processed", "code": code}

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

            card_path = generate_card(
                participant_code=code,
                pre=pre_dict,
                post=post_dict,
                deltas=deltas,
                cohort=participant.cohort or "platform",
            )

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
            db.session.commit()

            return {"status": "card_generated", "code": code, "path": card_path}

        return {"status": "post_saved_no_pre", "code": code}

    return {"status": "pre_saved", "code": code}


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