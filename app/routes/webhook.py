"""
webhook.py
Receives real-time POST from Google Apps Script onFormSubmit trigger.
Validates a shared secret header, then processes the row immediately.
"""
import hmac
import os
from flask import Blueprint, request, jsonify, current_app

from app import limiter
from app.services.sync_service import process_row

webhook_bp = Blueprint("webhook", __name__)


def _verify_secret(req):
    """
    Compare the X-Webhook-Secret header against WEBHOOK_SECRET in config.
    Returns True if secrets match or if no secret is configured (dev mode).
 
    FIX: strip() both values — Cloud Run env vars pasted via GCP console
    can append a trailing newline, causing compare_digest to always fail.
    We strip only the config value (our own data); the header value is
    user-controlled so we preserve it and strip only leading/trailing whitespace.
    """
    expected = (current_app.config.get("WEBHOOK_SECRET") or "").strip()
    if not expected:
        env = os.getenv("FLASK_ENV", "development").lower()
        if env == "production":
            current_app.logger.error("WEBHOOK_SECRET is missing in production.")
            return False
        return True   # skip verification in development
    provided = req.headers.get("X-Webhook-Secret", "").strip()
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

    if result.get("status") == "failed":
        status_code = 500
    elif result.get("status") == "skipped":
        status_code = 202
    else:
        status_code = 200
    return jsonify(result), status_code