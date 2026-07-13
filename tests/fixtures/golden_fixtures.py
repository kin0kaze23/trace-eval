"""Golden canonical fixture with tool call/result correlation."""

import json
from pathlib import Path

FIXTURE_DIR = Path(__file__).parent


def _make_event(
    idx,
    actor,
    etype,
    ts,
    status=None,
    tool_name=None,
    tool_call_id=None,
    tool_args=None,
    tokens_in=None,
    tokens_out=None,
):
    d = {"event_index": idx, "actor": actor, "event_type": etype, "timestamp": ts}
    if status:
        d["status"] = status
    if tool_name:
        d["tool_name"] = tool_name
    if tool_call_id:
        d["tool_call_id"] = tool_call_id
    if tool_args is not None:
        d["tool_args"] = tool_args
    if tokens_in is not None:
        d["tokens_in"] = tokens_in
    if tokens_out is not None:
        d["tokens_out"] = tokens_out
    return d


# Scenario 1: Successful call/result pair
SCENARIO_SUCCESS = [
    _make_event(0, "user", "session_start", "2026-01-01T00:00:00Z", "success"),
    _make_event(1, "assistant", "llm_call", "2026-01-01T00:00:05Z", "success", tokens_in=100, tokens_out=50),
    _make_event(2, "assistant", "tool_call", "2026-01-01T00:00:10Z", tool_name="grep", tool_call_id="tc-001"),
    _make_event(3, "tool", "tool_result", "2026-01-01T00:00:11Z", "success", tool_name="grep", tool_call_id="tc-001"),
    _make_event(4, "assistant", "session_end", "2026-01-01T00:00:15Z", "success"),
]

# Scenario 2: Error followed by successful retry
SCENARIO_RETRY = [
    _make_event(0, "user", "session_start", "2026-01-01T00:00:00Z", "success"),
    _make_event(1, "assistant", "tool_call", "2026-01-01T00:00:05Z", tool_name="write", tool_call_id="tc-001"),
    _make_event(2, "tool", "tool_result", "2026-01-01T00:00:06Z", "error", tool_name="write", tool_call_id="tc-001"),
    _make_event(3, "assistant", "tool_call", "2026-01-01T00:00:10Z", tool_name="write", tool_call_id="tc-002"),
    _make_event(4, "tool", "tool_result", "2026-01-01T00:00:11Z", "success", tool_name="write", tool_call_id="tc-002"),
    _make_event(5, "assistant", "session_end", "2026-01-01T00:00:15Z", "success"),
]

# Scenario 3: Timeout followed by retry
SCENARIO_TIMEOUT = [
    _make_event(0, "user", "session_start", "2026-01-01T00:00:00Z", "success"),
    _make_event(1, "assistant", "tool_call", "2026-01-01T00:00:05Z", tool_name="bash", tool_call_id="tc-001"),
    _make_event(2, "tool", "tool_result", "2026-01-01T00:00:06Z", "timeout", tool_name="bash", tool_call_id="tc-001"),
    _make_event(3, "assistant", "tool_call", "2026-01-01T00:00:10Z", tool_name="bash", tool_call_id="tc-002"),
    _make_event(4, "tool", "tool_result", "2026-01-01T00:00:11Z", "success", tool_name="bash", tool_call_id="tc-002"),
    _make_event(5, "assistant", "session_end", "2026-01-01T00:00:15Z", "success"),
]

# Scenario 4: Interleaved calls with same tool but different IDs
SCENARIO_INTERLEAVED = [
    _make_event(0, "user", "session_start", "2026-01-01T00:00:00Z", "success"),
    _make_event(1, "assistant", "tool_call", "2026-01-01T00:00:05Z", tool_name="grep", tool_call_id="tc-A"),
    _make_event(2, "assistant", "tool_call", "2026-01-01T00:00:06Z", tool_name="grep", tool_call_id="tc-B"),
    _make_event(3, "tool", "tool_result", "2026-01-01T00:00:07Z", "success", tool_name="grep", tool_call_id="tc-A"),
    _make_event(4, "tool", "tool_result", "2026-01-01T00:00:08Z", "success", tool_name="grep", tool_call_id="tc-B"),
    _make_event(5, "assistant", "session_end", "2026-01-01T00:00:15Z", "success"),
]

# Scenario 5: Redundant successful call with identical args
SCENARIO_REDUNDANT = [
    _make_event(0, "user", "session_start", "2026-01-01T00:00:00Z", "success"),
    _make_event(
        1,
        "assistant",
        "tool_call",
        "2026-01-01T00:00:05Z",
        tool_name="grep",
        tool_call_id="tc-001",
        tool_args={"pattern": "auth"},
    ),
    _make_event(2, "tool", "tool_result", "2026-01-01T00:00:06Z", "success", tool_name="grep", tool_call_id="tc-001"),
    _make_event(
        3,
        "assistant",
        "tool_call",
        "2026-01-01T00:00:10Z",
        tool_name="grep",
        tool_call_id="tc-002",
        tool_args={"pattern": "auth"},
    ),
    _make_event(4, "tool", "tool_result", "2026-01-01T00:00:11Z", "success", tool_name="grep", tool_call_id="tc-002"),
    _make_event(5, "assistant", "session_end", "2026-01-01T00:00:15Z", "success"),
]

# Scenario 6: Orphan result (no matching call)
SCENARIO_ORPHAN = [
    _make_event(0, "user", "session_start", "2026-01-01T00:00:00Z", "success"),
    _make_event(
        1, "tool", "tool_result", "2026-01-01T00:00:05Z", "success", tool_name="grep", tool_call_id="orphan-001"
    ),
    _make_event(2, "assistant", "session_end", "2026-01-01T00:00:15Z", "success"),
]

# Scenario 7: Unmatched call (no result)
SCENARIO_UNMATCHED = [
    _make_event(0, "user", "session_start", "2026-01-01T00:00:00Z", "success"),
    _make_event(1, "assistant", "tool_call", "2026-01-01T00:00:05Z", tool_name="grep", tool_call_id="tc-001"),
    _make_event(2, "assistant", "session_end", "2026-01-01T00:00:15Z", "success"),
]

# Scenario 8: Duplicate tool_call_id
SCENARIO_DUPLICATE_ID = [
    _make_event(0, "user", "session_start", "2026-01-01T00:00:00Z", "success"),
    _make_event(1, "assistant", "tool_call", "2026-01-01T00:00:05Z", tool_name="grep", tool_call_id="dup-001"),
    _make_event(2, "assistant", "tool_call", "2026-01-01T00:00:06Z", tool_name="grep", tool_call_id="dup-001"),
    _make_event(3, "tool", "tool_result", "2026-01-01T00:00:07Z", "success", tool_name="grep", tool_call_id="dup-001"),
    _make_event(4, "assistant", "session_end", "2026-01-01T00:00:15Z", "success"),
]

ALL_SCENARIOS = {
    "success": SCENARIO_SUCCESS,
    "retry": SCENARIO_RETRY,
    "timeout": SCENARIO_TIMEOUT,
    "interleaved": SCENARIO_INTERLEAVED,
    "redundant": SCENARIO_REDUNDANT,
    "orphan": SCENARIO_ORPHAN,
    "unmatched": SCENARIO_UNMATCHED,
    "duplicate_id": SCENARIO_DUPLICATE_ID,
}


def write_fixture(name, events, tmp_path):
    """Write events as a canonical JSONL file."""
    p = tmp_path / f"{name}.jsonl"
    p.write_text("\n".join(json.dumps(e) for e in events) + "\n")
    return p
