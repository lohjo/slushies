import pytest
from app.services.score_service import (
    compute_act_totals, compute_cmi_total, compute_rsem_total,
    compute_ewb_total, compute_change_scores, cohens_d,
    effect_size_label, is_meaningful_change,
)


SAMPLE_PRE = {
    "act_a1": 2, "act_a2": 2, "act_a3": 2, "act_a4": 2, "act_a5": 2, "act_a6": 2,
    "cmi_b1": 1, "cmi_b2": 1, "cmi_b3": 1, "cmi_b4": 1, "cmi_b5": 1, "cmi_b6": 1,
    "rsem_c1": 2, "rsem_c2": 2, "rsem_c3": 2, "rsem_c4": 2, "rsem_c5": 2,
    "rsem_c6": 2, "rsem_c7": 2, "rsem_c8": 2, "rsem_c9": 2, "rsem_c10": 2,
    "ewb_d1": 2, "ewb_d2": 2, "ewb_d3": 2, "ewb_d4": 2, "ewb_d5": 2, "ewb_d6": 2,
    "act_total": 12, "cmi_total": 6, "rsem_total": 15, "ewb_total": 12,
}

SAMPLE_POST = {
    **SAMPLE_PRE,
    "act_total": 18, "cmi_total": 14, "rsem_total": 22, "ewb_total": 20,
}


class TestActScoring:
    def test_total(self):
        row = {f"act_a{i}": 3 for i in range(1, 7)}
        r = compute_act_totals(row)
        assert r["act_total"] == 18

    def test_subdomains(self):
        row = {"act_a1": 5, "act_a2": 4, "act_a3": 3, "act_a4": 2, "act_a5": 1, "act_a6": 1}
        r = compute_act_totals(row)
        assert r["act_connect"] == 9
        assert r["act_act"]     == 5
        assert r["act_thrive"]  == 2

    def test_missing_item_returns_empty(self):
        row = {"act_a1": 3}
        assert compute_act_totals(row) == {}


class TestRosenbergScoring:
    def test_all_strongly_agree(self):
        # Positive items: SA(4) → 3. Reverse items: SA(4) → 0.
        row = {f"rsem_c{i}": 4 for i in range(1, 11)}
        r = compute_rsem_total(row)
        # 5 positive items × 3 = 15; 5 reverse items × 0 = 0
        assert r["rsem_total"] == 15

    def test_all_strongly_disagree(self):
        row = {f"rsem_c{i}": 1 for i in range(1, 11)}
        r = compute_rsem_total(row)
        # 5 positive items × 0 = 0; 5 reverse items × 3 = 15
        assert r["rsem_total"] == 15


class TestChangeScores:
    def test_positive_change(self):
        deltas = compute_change_scores(SAMPLE_PRE, SAMPLE_POST)
        assert deltas["delta_act"]  == 6.0
        assert deltas["delta_cmi"]  == 8.0
        assert deltas["delta_rsem"] == 7.0
        assert deltas["delta_ewb"]  == 8.0

    def test_no_change(self):
        deltas = compute_change_scores(SAMPLE_PRE, SAMPLE_PRE)
        assert all(v == 0 for v in deltas.values())


class TestEffectSize:
    def test_cohens_d(self):
        assert cohens_d(5.0, 2.5) == 2.0

    def test_zero_std_returns_none(self):
        assert cohens_d(5.0, 0) is None

    def test_labels(self):
        assert effect_size_label(0.1) == "negligible"
        assert effect_size_label(0.3) == "small"
        assert effect_size_label(0.6) == "medium"
        assert effect_size_label(0.9) == "large"


class TestMeaningfulChange:
    def test_rsem_threshold(self):
        assert is_meaningful_change(3.0, "rsem") is True
        assert is_meaningful_change(2.9, "rsem") is False

    def test_act_threshold(self):
        assert is_meaningful_change(2.0, "act") is True
        assert is_meaningful_change(1.9, "act") is False