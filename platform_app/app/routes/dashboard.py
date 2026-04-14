from flask import Blueprint, render_template, abort
from flask_login import login_required, current_user

from app.models import Participant, SurveyResponse, GrowthCard

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
@dashboard_bp.route("/dashboard")
@login_required
def index():
    participants = Participant.query.order_by(Participant.created_at.desc()).all()
    total_pre    = SurveyResponse.query.filter_by(survey_type="pre").count()
    total_post   = SurveyResponse.query.filter_by(survey_type="post").count()
    cards_issued = GrowthCard.query.count()
    return render_template(
        "dashboard/index.html",
        participants=participants,
        total_pre=total_pre,
        total_post=total_post,
        cards_issued=cards_issued,
    )


@dashboard_bp.route("/dashboard/participant/<code>")
@login_required
def participant_detail(code):
    participant = Participant.query.filter_by(code=code).first_or_404()
    pre  = SurveyResponse.query.filter_by(
        participant_id=participant.id, survey_type="pre"
    ).first()
    post = SurveyResponse.query.filter_by(
        participant_id=participant.id, survey_type="post"
    ).first()
    card = GrowthCard.query.filter_by(participant_id=participant.id).first()
    return render_template(
        "dashboard/participant.html",
        participant=participant,
        pre=pre, post=post, card=card,
    )


@dashboard_bp.route("/dashboard/export")
@login_required
def export():
    if current_user.role != "admin":
        abort(403)
    # Full export logic lives in api.py — redirect there
    from flask import redirect, url_for
    return redirect(url_for("api.export_csv"))