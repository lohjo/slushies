"""
sheets_service.py
Handles all communication with the Google Sheets API v4.
Authenticates via a Service Account so no user OAuth flow is needed.
"""
import json
from flask import current_app
from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

# Column positions in the Google Sheet (0-indexed after timestamp)
# Adjust these if your form question order differs.
COL_MAP = {
    "timestamp":    0,
    "code":         1,
    "survey_type":  2,   # participant answers 'pre' or 'post'
    # profile
    "profile_f1": 3, "profile_f2": 4,
    # ACT SG
    "act_a1": 5,  "act_a2": 6,  "act_a3": 7,
    "act_a4": 8,  "act_a5": 9,  "act_a6": 10,
    # CMI
    "cmi_b1": 11,  "cmi_b2": 12, "cmi_b3": 13,
    "cmi_b4": 14, "cmi_b5": 15, "cmi_b6": 16,
    # Rosenberg
    "rsem_c1": 17, "rsem_c2": 18, "rsem_c3": 19, "rsem_c4": 20,
    "rsem_c5": 21, "rsem_c6": 22, "rsem_c7": 23, "rsem_c8": 24,
    "rsem_c9": 25, "rsem_c10": 26,
    # Eudaimonic WB
    "ewb_d1": 27, "ewb_d2": 28, "ewb_d3": 29,
    "ewb_d4": 30, "ewb_d5": 31, "ewb_d6": 32,
}


def _get_service():
    json_blob = current_app.config.get("GOOGLE_SERVICE_ACCOUNT_JSON")

    if json_blob:
        try:
            info = json.loads(json_blob)
        except json.JSONDecodeError as exc:
            raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON is not valid JSON.") from exc

        creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    else:
        key_file = current_app.config["GOOGLE_SERVICE_ACCOUNT_FILE"]
        creds = service_account.Credentials.from_service_account_file(
            key_file, scopes=SCOPES
        )

    return build("sheets", "v4", credentials=creds)


def fetch_all_rows(sheet_range=None):
    """
    Fetches all response rows from the linked Google Sheet.
    Skips the header row (A1) by starting at A2.
    Returns a list of raw row arrays.
    """
    service = _get_service()
    effective_range = sheet_range or current_app.config.get("GOOGLE_SHEET_RANGE", "Sheet1!A2:AJ")
    result = (
        service.spreadsheets()
        .values()
        .get(
            spreadsheetId=current_app.config["GOOGLE_SHEET_ID"],
            range=effective_range,
        )
        .execute()
    )
    values = result.get("values", [])
    if not values and not current_app.config.get("SHEETS_ALLOW_EMPTY", False):
        raise RuntimeError(
            "Google Sheets returned no rows. Verify GOOGLE_SHEET_RANGE tab name and bounds."
        )
    return values


def parse_row(row, row_index):
    """
    Converts a raw sheet row (list of strings) into a dict
    ready to be stored in SurveyResponse.
    """

    def safe_float(val):
        try:
            return float(val)
        except (ValueError, TypeError):
            return None

    parsed = {"sheet_row_index": row_index}
    for field, col in COL_MAP.items():
        raw = row[col] if col < len(row) else None
        if field in ("timestamp", "code", "survey_type") or field.startswith("reflect"):
            parsed[field] = raw
        else:
            parsed[field] = safe_float(raw)

    return parsed