"""Tests for canonical rating semantics."""

from pathlib import Path

from trace_eval.report import score_interpretation
from trace_eval.scoring import compute_rating, rating_explanation

TRACE_EVAL_DIR = Path(__file__).resolve().parent.parent


class TestRatingBoundaries:
    def test_score_0_is_critical(self):
        assert compute_rating(0) == "Critical"

    def test_score_39_99_is_critical(self):
        assert compute_rating(39.99) == "Critical"

    def test_score_40_is_poor(self):
        assert compute_rating(40) == "Poor"

    def test_score_59_99_is_poor(self):
        assert compute_rating(59.99) == "Poor"

    def test_score_60_is_fair(self):
        assert compute_rating(60) == "Fair"

    def test_score_79_99_is_fair(self):
        assert compute_rating(79.99) == "Fair"

    def test_score_80_is_good(self):
        assert compute_rating(80) == "Good"

    def test_score_89_99_is_good(self):
        assert compute_rating(89.99) == "Good"

    def test_score_90_is_excellent(self):
        assert compute_rating(90) == "Excellent"

    def test_score_100_is_excellent(self):
        assert compute_rating(100) == "Excellent"


class TestRatingExplanation:
    def test_explanation_for_each_rating(self):
        for score in [95, 85, 70, 50, 20]:
            expl = rating_explanation(score)
            assert isinstance(expl, str)
            assert len(expl) > 0


class TestReportConsistency:
    def test_score_interpretation_uses_canonical(self):
        for score in [95, 85, 70, 50, 20]:
            rating = compute_rating(score)
            interpretation = score_interpretation(score)
            assert rating in interpretation, f"Rating '{rating}' not in interpretation '{interpretation}'"

    def test_no_duplicate_score_rating_class(self):
        import trace_eval.report as report_mod

        assert not hasattr(report_mod, "ScoreRating"), "ScoreRating enum should be removed from report.py"

    def test_no_duplicate_score_interpretation_dict(self):
        import trace_eval.report as report_mod

        assert not hasattr(report_mod, "SCORE_INTERPRETATION"), (
            "SCORE_INTERPRETATION dict should be removed from report.py"
        )
