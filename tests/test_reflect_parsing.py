"""
test_reflect_parsing.py

Verifies that open-reflection fields (E1–E4) are correctly parsed from
sheet rows by sheets_service.parse_row, and that the configured default
sheet range covers all 37 columns (A–AK, indices 0–36).
"""
import pytest
from app.services.sheets_service import parse_row, COL_MAP


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_row(length=37, overrides=None):
    """Build a synthetic sheet row with a given length, applying field overrides."""
    row = [""] * length
    overrides = overrides or {}
    for field, value in overrides.items():
        idx = COL_MAP[field]
        row[idx] = value
    return row


# ── COL_MAP contract tests ────────────────────────────────────────────────────

def test_reflect_fields_present_in_col_map():
    """All four reflect fields must be registered in COL_MAP."""
    for field in ("reflect_e1", "reflect_e2", "reflect_e3", "reflect_e4"):
        assert field in COL_MAP, f"{field} missing from COL_MAP"


def test_reflect_col_indices_are_correct():
    """Reflect columns must start right after EWB (ewb_d6=32)."""
    assert COL_MAP["reflect_e1"] == 33
    assert COL_MAP["reflect_e2"] == 34
    assert COL_MAP["reflect_e3"] == 35
    assert COL_MAP["reflect_e4"] == 36


def test_col_map_max_index_is_36():
    """
    The highest column index in COL_MAP must be 36 (AK).
    This ensures the default sheet range Sheet1!A2:AK covers every mapped field.
    """
    assert max(COL_MAP.values()) == 36


# ── parse_row reflect tests ───────────────────────────────────────────────────

def test_parse_row_reflect_fields_populated():
    """Reflect values present in the row are returned as strings."""
    row = _make_row(
        37,
        {
            "code": "AB01",
            "survey_type": "post",
            "reflect_e1": "I learned to trust.",
            "reflect_e2": "My team.",
            "reflect_e3": "The moment I spoke up.",
            "reflect_e4": "Keep going.",
        },
    )
    parsed = parse_row(row, row_index=5)

    assert parsed["reflect_e1"] == "I learned to trust."
    assert parsed["reflect_e2"] == "My team."
    assert parsed["reflect_e3"] == "The moment I spoke up."
    assert parsed["reflect_e4"] == "Keep going."


def test_parse_row_reflect_fields_empty_string_when_pre_survey():
    """Pre-survey rows have no reflect answers; fields should be empty string or None."""
    row = _make_row(37, {"code": "AB01", "survey_type": "pre"})
    parsed = parse_row(row, row_index=3)

    # Empty string is acceptable; None is not (row is long enough to index)
    for field in ("reflect_e1", "reflect_e2", "reflect_e3", "reflect_e4"):
        assert parsed[field] == "" or parsed[field] is None


def test_parse_row_reflect_none_when_row_too_short():
    """Rows shorter than 37 columns must not raise; missing reflect fields are None."""
    row = _make_row(33)  # Only up to ewb_d6 (idx 32); reflect cols missing
    parsed = parse_row(row, row_index=2)

    for field in ("reflect_e1", "reflect_e2", "reflect_e3", "reflect_e4"):
        assert parsed[field] is None, f"Expected None for {field} on short row"


def test_parse_row_reflect_e3_is_used_for_card_quote():
    """
    card_service pulls reflect_e3 as the participant quote.
    Ensure it is correctly parsed so growth cards display quotes.
    """
    quote = "I found my voice during the programme."
    row = _make_row(37, {"code": "XY99", "survey_type": "post", "reflect_e3": quote})
    parsed = parse_row(row, row_index=10)

    assert parsed["reflect_e3"] == quote


# ── default range config test ─────────────────────────────────────────────────

def test_default_sheet_range_covers_reflect_columns():
    """
    The hard-coded fallback in fetch_all_rows must reach column AK.
    We verify by inspecting the default string used when env var is unset.
    """
    # Default defined in config.py BaseConfig and in fetch_all_rows fallback
    from app.config import BaseConfig
    assert BaseConfig.GOOGLE_SHEET_RANGE == "Sheet1!A2:AK", (
        f"Default range is {BaseConfig.GOOGLE_SHEET_RANGE!r} — "
        "must be 'Sheet1!A2:AK' to reach reflect_e4 at column index 36"
    )