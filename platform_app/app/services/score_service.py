"""
score_service.py
All scoring logic: domain totals, reverse-scoring, change scores, Cohen's d.
Pure Python — no database or Flask dependencies, so it's easily unit-tested.
"""
import math
from typing import Optional

# Rosenberg items that are reverse-scored (1-indexed to match form labels)
RSEM_REVERSE_ITEMS = {2, 5, 6, 8, 9}


# ─── Domain totals ────────────────────────────────────────────────────────────

def compute_act_totals(row: dict) -> dict:
    """Returns ACT SG total and three sub-domain scores."""
    items = [row.get(f"act_a{i}") for i in range(1, 7)]
    if any(v is None for v in items):
        return {}
    a1, a2, a3, a4, a5, a6 = items
    return {
        "act_total":   sum(items),
        "act_connect": a1 + a2,
        "act_act":     a3 + a4,
        "act_thrive":  a5 + a6,
    }


def compute_cmi_total(row: dict) -> dict:
    items = [row.get(f"cmi_b{i}") for i in range(1, 7)]
    if any(v is None for v in items):
        return {}
    return {"cmi_total": sum(items)}


def _rsem_score(item_num: int, raw: float) -> float:
    """Apply reverse scoring for Rosenberg if needed. Input 1–4, output 0–3."""
    if item_num in RSEM_REVERSE_ITEMS:
        return 4 - raw   # SA(4)→0, A(3)→1, D(2)→2, SD(1)→3
    return raw - 1       # SA(4)→3, A(3)→2, D(2)→1, SD(1)→0


def compute_rsem_total(row: dict) -> dict:
    items = [row.get(f"rsem_c{i}") for i in range(1, 11)]
    if any(v is None for v in items):
        return {}
    scored = [_rsem_score(i + 1, v) for i, v in enumerate(items)]
    return {"rsem_total": sum(scored)}


def compute_ewb_total(row: dict) -> dict:
    items = [row.get(f"ewb_d{i}") for i in range(1, 7)]
    if any(v is None for v in items):
        return {}
    return {"ewb_total": sum(items)}


def compute_all_totals(row: dict) -> dict:
    """Compute all four framework totals and return as a flat dict."""
    totals = {}
    totals.update(compute_act_totals(row))
    totals.update(compute_cmi_total(row))
    totals.update(compute_rsem_total(row))
    totals.update(compute_ewb_total(row))
    return totals


# ─── Change scores ────────────────────────────────────────────────────────────

def compute_change_scores(pre: dict, post: dict) -> dict:
    """
    Returns delta (post − pre) for each of the four framework totals.
    A positive value = improvement.
    """
    keys = ["act_total", "cmi_total", "rsem_total", "ewb_total"]
    deltas = {}
    for k in keys:
        pre_val  = pre.get(k)
        post_val = post.get(k)
        if pre_val is not None and post_val is not None:
            deltas[f"delta_{k.replace('_total', '')}"] = round(post_val - pre_val, 2)
    return deltas


# ─── Effect size ──────────────────────────────────────────────────────────────

def cohens_d(delta: float, std_dev: float) -> Optional[float]:
    """
    Cohen's d = mean change ÷ SD of change scores.
    Pass the individual delta and the population SD (computed outside).
    Returns None if std_dev is zero.
    """
    if std_dev == 0:
        return None
    return round(delta / std_dev, 3)


def effect_size_label(d: float) -> str:
    """Interprets Cohen's d for non-technical stakeholder reports."""
    abs_d = abs(d)
    if abs_d < 0.2:
        return "negligible"
    if abs_d < 0.5:
        return "small"
    if abs_d < 0.8:
        return "medium"
    return "large"


# ─── Meaningful change threshold ─────────────────────────────────────────────

def is_meaningful_change(delta: float, scale: str) -> bool:
    """
    Clinically meaningful thresholds per scale.
    Based on scale range and minimum detectable change conventions.
    """
    thresholds = {
        "act":  2.0,   # 6-item, range 6–30
        "cmi":  2.0,   # 6-item, range 6–24
        "rsem": 3.0,   # 10-item Rosenberg, range 0–30
        "ewb":  2.0,   # 6-item, range 6–30
    }
    return abs(delta) >= thresholds.get(scale, 2.0)