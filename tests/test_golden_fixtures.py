"""Golden fixture expected-score tests."""

import json
from pathlib import Path

from tests.fixtures.golden_fixtures import ALL_SCENARIOS, write_fixture
from trace_eval.judges.tool_discipline import judge_tool_discipline
from trace_eval.schema import Event


def _events_from_dicts(dicts):
    return [Event.from_dict(d) for d in dicts]


class TestGoldenFixtures:
    """Verify expected scores for golden fixtures."""

    def test_success_scenario(self):
        events = _events_from_dicts(ALL_SCENARIOS["success"])
        result = judge_tool_discipline(events)
        assert result.score == 100.0
        assert result.raw_metrics["exact_pairs"] == 1
        assert result.raw_metrics["tool_retries"] == 0

    def test_retry_scenario(self):
        events = _events_from_dicts(ALL_SCENARIOS["retry"])
        result = judge_tool_discipline(events)
        assert result.raw_metrics["tool_retries"] == 1
        assert result.raw_metrics["exact_pairs"] == 2
        assert result.score == 90.0  # 100 - 10*1

    def test_timeout_scenario(self):
        events = _events_from_dicts(ALL_SCENARIOS["timeout"])
        result = judge_tool_discipline(events)
        assert result.raw_metrics["tool_timeouts"] == 1
        assert result.raw_metrics["tool_retries"] == 1  # timeout then retry
        assert result.score == 75.0  # 100 - 15*1 - 10*1

    def test_interleaved_scenario(self):
        events = _events_from_dicts(ALL_SCENARIOS["interleaved"])
        result = judge_tool_discipline(events)
        assert result.raw_metrics["tool_retries"] == 0
        assert result.raw_metrics["exact_pairs"] == 2
        assert result.score == 100.0

    def test_redundant_scenario(self):
        events = _events_from_dicts(ALL_SCENARIOS["redundant"])
        result = judge_tool_discipline(events)
        assert result.raw_metrics["redundant_calls"] == 1
        assert result.score == 92.0  # 100 - 8*1

    def test_orphan_scenario(self):
        events = _events_from_dicts(ALL_SCENARIOS["orphan"])
        result = judge_tool_discipline(events)
        assert result.raw_metrics["orphan_results"] == 1

    def test_unmatched_scenario(self):
        events = _events_from_dicts(ALL_SCENARIOS["unmatched"])
        result = judge_tool_discipline(events)
        assert result.raw_metrics["unmatched_calls"] == 1

    def test_duplicate_id_scenario(self):
        events = _events_from_dicts(ALL_SCENARIOS["duplicate_id"])
        result = judge_tool_discipline(events)
        assert result.raw_metrics["duplicate_tool_call_ids"] == 1
        assert result.confidence != "high"

    def test_fixture_cli_compatible(self, tmp_path):
        """Golden fixtures should be loadable by the CLI."""
        import subprocess
        import sys

        trace = write_fixture("success", ALL_SCENARIOS["success"], tmp_path)
        result = subprocess.run(
            [sys.executable, "-m", "trace_eval.cli", "run", str(trace), "--format", "json"],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).resolve().parent.parent),
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "total_score" in data
