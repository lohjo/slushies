"""
card_service.py
Renders a personalised HTML growth card and converts it to PDF.
Uses WeasyPrint (pure Python, no browser dependency).
Install: pip install weasyprint
"""
import os
from datetime import datetime
from flask import current_app, render_template
from weasyprint import HTML as WeasyprintHTML

from app.services.score_service import effect_size_label, is_meaningful_change


def _radar_data(pre: dict, post: dict) -> dict:
    """Normalise scores to 0–100 scale for the radar chart."""
    scales = {
        "ACT SG":     ("act_total",  6,  30),
        "CMI":        ("cmi_total",  6,  24),
        "Rosenberg":  ("rsem_total", 0,  30),
        "Well-Being": ("ewb_total",  6,  30),
    }
    radar = {}
    for label, (key, lo, hi) in scales.items():
        pre_val  = pre.get(key,  0) or 0
        post_val = post.get(key, 0) or 0
        radar[label] = {
            "pre":  round((pre_val  - lo) / (hi - lo) * 100, 1),
            "post": round((post_val - lo) / (hi - lo) * 100, 1),
        }
    return radar


def generate_card(participant_code: str, pre: dict, post: dict,
                  deltas: dict, cohort: str = "platform") -> str:
    """
    Renders the growth card HTML, converts to PDF, and saves to
    the CARDS_OUTPUT_DIR configured in the app.
    Returns the file path of the saved PDF.
    """
    output_dir = current_app.config["CARDS_OUTPUT_DIR"]
    os.makedirs(output_dir, exist_ok=True)

    radar = _radar_data(pre, post)

    # Build a human-readable highlights list for the card narrative
    highlights = []
    scale_labels = {
        "act":  "connection and agency (ACT SG)",
        "cmi":  "career readiness (CMI)",
        "rsem": "self-esteem (Rosenberg)",
        "ewb":  "sense of purpose (Well-Being)",
    }
    for scale, label in scale_labels.items():
        delta = deltas.get(f"delta_{scale}")
        if delta is not None and is_meaningful_change(delta, scale):
            direction = "grew" if delta > 0 else "declined"
            highlights.append(f"Your {label} {direction} meaningfully.")

    # Pull a quote from the open reflection if available
    quote = (post.get("reflect_e3") or "").strip()

    html_string = render_template(
        "cards/growth_card.html",
        code=participant_code,
        cohort=cohort,
        organization_name=current_app.config.get("ORGANIZATION_NAME", "Impart & Ngee Ann Polytechnic"),
        generated_at=datetime.utcnow().strftime("%d %b %Y"),
        radar=radar,
        deltas=deltas,
        highlights=highlights,
        quote=quote,
        effect_size_label=effect_size_label,
    )

    filename = f"growth_card_{participant_code}_{datetime.utcnow().strftime('%Y%m%d')}.pdf"
    output_path = os.path.join(output_dir, filename)

    WeasyprintHTML(string=html_string).write_pdf(output_path)
    return output_path