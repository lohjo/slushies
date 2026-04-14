import csv
import io
from flask import Blueprint, jsonify, request, Response, send_file
from flask_login import login_required, current_user
from sqlalchemy import func

from app import db
from app.models import Participant, SurveyResponse, GrowthCard
from app.services.sync_service import sync_all_from_sheets

api_bp = Blueprint("api", __name__)


# ─── Sync ─────────────────────────────────────────────────────────────────────

@api_bp.route("/sync", methods=["POST"])
@login_required
def sync():
    """Manually pull all rows from Google Sheets and process any new ones."""
    results = sync_all_from_sheets()
    processed = [r for r in results if r["status"] != "skipped"]
    return jsonify({"total": len(results), "processed": len(processed), "detail": results})


# ─── Participants CRUD ────────────────────────────────────────────────────────

@api_bp.route("/participants", methods=["GET"])
@login_required
def list_participants():
    rows = Participant.query.order_by(Participant.created_at.desc()).all()
    return jsonify([p.to_dict() for p in rows])


@api_bp.route("/participants/<code>", methods=["GET"])
@login_required
def get_participant(code):
    p = Participant.query.filter_by(code=code).first_or_404()
    return jsonify(p.to_dict())


@api_bp.route("/participants/<code>", methods=["PUT"])
@login_required
def update_participant(code):
    p = Participant.query.filter_by(code=code).first_or_404()
    data = request.json or {}
    if "cohort" in data:
        p.cohort = data["cohort"]
    db.session.commit()
    return jsonify(p.to_dict())


@api_bp.route("/participants/<code>", methods=["DELETE"])
@login_required
def delete_participant(code):
    if current_user.role != "admin":
        return jsonify({"error": "Forbidden"}), 403
    p = Participant.query.filter_by(code=code).first_or_404()
    db.session.delete(p)
    db.session.commit()
    return jsonify({"deleted": code})


# ─── Responses CRUD ──────────────────────────────────────────────────────────

@api_bp.route("/responses", methods=["GET"])
@login_required
def list_responses():
    rows = SurveyResponse.query.all()
    return jsonify([r.to_dict() for r in rows])


@api_bp.route("/responses/<int:id>", methods=["GET"])
@login_required
def get_response(id):
    r = SurveyResponse.query.get_or_404(id)
    return jsonify(r.to_dict())


@api_bp.route("/responses/<int:id>", methods=["DELETE"])
@login_required
def delete_response(id):
    if current_user.role != "admin":
        return jsonify({"error": "Forbidden"}), 403
    r = SurveyResponse.query.get_or_404(id)
    db.session.delete(r)
    db.session.commit()
    return jsonify({"deleted": id})


# ─── Growth Cards ─────────────────────────────────────────────────────────────

@api_bp.route("/cards/<code>", methods=["GET"])
@login_required
def download_card(code):
    participant = Participant.query.filter_by(code=code).first_or_404()
    card = GrowthCard.query.filter_by(participant_id=participant.id).first_or_404()
    return send_file(card.file_path, as_attachment=True,
                     download_name=f"growth_card_{code}.pdf")


# ─── CSV Export ───────────────────────────────────────────────────────────────

@api_bp.route("/export/csv", methods=["GET"])
@login_required
def export_csv():
    if current_user.role != "admin":
        return jsonify({"error": "Forbidden"}), 403

    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        "code", "cohort", "survey_type",
        "act_total", "act_connect", "act_act", "act_thrive",
        "cmi_total", "rsem_total", "ewb_total",
        "delta_act", "delta_cmi", "delta_rsem", "delta_ewb",
        "submitted_at",
    ])

    latest_card_ids = (
        db.session.query(
            GrowthCard.participant_id.label("participant_id"),
            func.max(GrowthCard.id).label("latest_card_id"),
        )
        .group_by(GrowthCard.participant_id)
        .subquery()
    )

    responses = (
        db.session.query(SurveyResponse, Participant, GrowthCard)
        .join(Participant, SurveyResponse.participant_id == Participant.id)
        .outerjoin(latest_card_ids, latest_card_ids.c.participant_id == Participant.id)
        .outerjoin(GrowthCard, GrowthCard.id == latest_card_ids.c.latest_card_id)
        .order_by(Participant.code.asc(), SurveyResponse.submitted_at.asc())
        .all()
    )
    for r, p, card in responses:
        writer.writerow([
            p.code, p.cohort, r.survey_type,
            r.act_total, r.act_connect, r.act_act, r.act_thrive,
            r.cmi_total, r.rsem_total, r.ewb_total,
            card.delta_act if card else None,
            card.delta_cmi if card else None,
            card.delta_rsem if card else None,
            card.delta_ewb if card else None,
            r.submitted_at,
        ])

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=platform_responses.csv"},
    )