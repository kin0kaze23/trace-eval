"""Tests for canonical rating semantics and precision alignment."""

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
            assert rating in interpretation

    def test_no_duplicate_score_rating_class(self):
        import trace_eval.report as report_mod

        assert not hasattr(report_mod, "ScoreRating")

    def test_no_duplicate_score_interpretation_dict(self):
        import trace_eval.report as report_mod

        assert not hasattr(report_mod, "SCORE_INTERPRETATION")


class TestPrecisionAlignment:
    """Displayed score and rating must never disagree."""

    def test_39_95_rounds_to_40_0_is_poor(self):
        rounded = round(39.95, 1)
        assert rounded == 40.0
        assert compute_rating(rounded) == "Poor"

    def test_59_95_rounds_to_60_0_is_fair(self):
        rounded = round(59.95, 1)
        assert rounded == 60.0
        assert compute_rating(rounded) == "Fair"

    def test_79_95_rounds_to_80_0_is_good(self):
        rounded = round(79.95, 1)
        assert rounded == 80.0
        assert compute_rating(rounded) == "Good"

    def test_89_95_rounds_to_90_0_is_excellent(self):
        rounded = round(89.95, 1)
        assert rounded == 90.0
        assert compute_rating(rounded) == "Excellent"

    def test_unrounded_79_99_is_fair_not_good(self):
        """79.99 is Fair, not Good — no rounding up to 80."""
        assert compute_rating(79.99) == "Fair"

    def test_unrounded_89_99_is_good_not_excellent(self):
        """89.99 is Good, not Excellent — no rounding up to 90."""
        assert compute_rating(89.99) == "Good"
