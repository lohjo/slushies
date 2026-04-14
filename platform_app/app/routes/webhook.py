"""
webhook.py
Receives real-time POST from Google Apps Script onFormSubmit trigger.
Validates a shared secret header, then processes the row immediately.
"""
import hmac
from flask import Blueprint, request, jsonify, current_app

from app import limiter
from app.services.sync_service import process_row

webhook_bp = Blueprint("webhook", __name__)


def _verify_secret(req):
    """
    Compare the X-Webhook-Secret header against WEBHOOK_SECRET in config.
    Returns True if secrets match or if no secret is configured (dev mode).
    """
    expected = current_app.config.get("WEBHOOK_SECRET", "")
    if not expected:
        return True   # skip verification in development
    provided = req.headers.get("X-Webhook-Secret", "")
    return hmac.compare_digest(expected, provided)


@webhook_bp.route("/form-submit", methods=["POST"])
@limiter.limit(lambda: current_app.config.get("WEBHOOK_RATE_LIMIT", "30 per minute"))
def form_submit():
    """
    Payload shape sent by Apps Script:
    {
        "row_index": 42,
        "values": ["2025-04-01 09:00", "AB01", "post", "4", "3", ...]
    }
    """
    if not _verify_secret(request):
        return jsonify({"error": "Unauthorized"}), 401

    payload = request.json
    if not payload or "values" not in payload:
        return jsonify({"error": "Missing values"}), 400

    result = process_row(
        raw_row=payload["values"],
        row_index=payload.get("row_index", 0),
    )

    status_code = 200 if result["status"] not in ("skipped",) else 202
    return jsonify(result), status_code