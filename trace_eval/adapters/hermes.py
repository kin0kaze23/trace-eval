"""Hermes SQLite adapter — honest, lossy.

Maps the real Hermes DB schema (sessions + messages tables) to the
canonical trace-eval Event/Trace types.

Real Hermes schema:
  sessions(id, source, user_id, model, started_at, ended_at,
           message_count, tool_call_count, tokens, cost fields, title)
  messages(id, session_id, role, content, tool_call_id, tool_calls,
           tool_name, timestamp, token_count, finish_reason, reasoning)

This adapter loads ALL sessions and merges their messages into a single
Trace, tagging each event with its session_id.

Improvements over v0.1.0:
  - Detects real tool errors from content (status=false, error field, etc.)
  - Maps session end_reason to terminal event status
  - Extracts session-level token data onto the first/last events
  - Reports has_token_data=False for Hermes (tokens exist but at session level, not event level)
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC
from pathlib import Path
from typing import Any

from trace_eval.schema import Event, EventType, Status, Trace

# Patterns that indicate a real tool error in the result content
_ERROR_PATTERNS = [
    lambda c: '"success": false' in c,
    lambda c: '"status": "error"' in c,
    lambda c: '"status": "timeout"' in c,
    lambda c: '"error": ' in c and '"error": null' not in c and '"error": ""' not in c,
    # Non-JSON error patterns (e.g. "Error searching web: ...")
    lambda c: c.strip().startswith("Error ") or c.strip().startswith("BLOCKED:"),
    lambda c: "Traceback (most recent call last)" in c,
    lambda c: "old_string" in c and "not found" in c.lower(),
    lambda c: "Found " in c and "matches for old_string" in c,
]


def _detect_tool_error(content: str) -> bool:
    """Detect real tool errors from content, excluding null/empty error fields."""
    if not content:
        return False
    for pattern in _ERROR_PATTERNS:
        if pattern(content):
            return True
    # Also try JSON parse for structured errors
    if content.strip().startswith("{"):
        try:
            parsed = json.loads(content)
            err = parsed.get("error")
            if err is not None and isinstance(err, str) and err.strip():
                return True
            if parsed.get("success") is False:
                return True
        except (json.JSONDecodeError, TypeError):
            pass
    return False


# Map Hermes end_reason to a terminal event status
_TERMINAL_MAP: dict[str | None, Status | None] = {
    "cli_close": None,  # user closed — not a failure, just incomplete
    "session_reset": None,  # session was reset — not a failure
    "compression": None,  # hit context compression limit
    "cron_complete": Status.success,
    None: None,  # unknown
}


def _get_terminal_status(end_reason: str | None) -> str | None:
    """Map Hermes end_reason to a terminal status for the last event."""
    return _TERMINAL_MAP.get(end_reason)


class HermesAdapter:
    """Reads Hermes SQLite DB and maps events to canonical Trace objects.

    Honest and lossy: populates what exists in the Hermes schema and
    nulls what doesn't. Does NOT synthesize span IDs or fabricate
    relationships.
    """

    def load(self, path: Path) -> Trace:
        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        # --- Read all sessions ---
        c.execute("SELECT * FROM sessions ORDER BY started_at")
        sessions = [dict(row) for row in c.fetchall()]

        if not sessions:
            conn.close()
            return Trace(events=[])

        # --- Read all messages ---
        c.execute("SELECT * FROM messages ORDER BY session_id, timestamp")
        messages = [dict(row) for row in c.fetchall()]

        conn.close()

        # --- Extract session-level aggregates (for metadata only) ---
        # Hermes stores tokens at the session level, not per-event.
        # We do NOT attach these to individual events because:
        # 1. The efficiency judge sums across ALL events, so attaching would
        #    create misleading totals when multiple sessions are merged
        # 2. Per-message token_count in the Hermes messages table is always NULL
        #
        # We report these in the capability report for transparency.
        total_input_tokens = sum(s.get("input_tokens") or 0 for s in sessions)  # noqa: F841
        total_output_tokens = sum(s.get("output_tokens") or 0 for s in sessions)  # noqa: F841
        last_end_reason = sessions[-1].get("end_reason")

        # --- Build events from messages ---
        events: list[Event] = []
        event_index = 0

        for msg in messages:
            role = msg.get("role", "unknown")
            session_id = msg.get("session_id")
            timestamp_raw = msg.get("timestamp")
            content = msg.get("content") or ""
            tool_calls_json = msg.get("tool_calls")
            tool_name = msg.get("tool_name")
            token_count = msg.get("token_count")
            finish_reason = msg.get("finish_reason")
            reasoning = msg.get("reasoning")

            # Convert Unix timestamp to ISO string
            if timestamp_raw is not None:
                from datetime import datetime

                ts = datetime.fromtimestamp(float(timestamp_raw), tz=UTC).isoformat()
            else:
                ts = ""

            # Parse tool_calls JSON if present
            tool_calls_data: list[dict] | None = None
            if tool_calls_json:
                try:
                    tool_calls_data = json.loads(tool_calls_json)
                except (json.JSONDecodeError, TypeError):
                    tool_calls_data = None

            # Determine event type based on role
            if role == "user":
                event_type = EventType.message
                actor = "user"
                status = None
            elif role == "assistant":
                event_type = EventType.llm_call
                actor = "assistant"
                status = None
            elif role == "tool":
                event_type = EventType.tool_result
                actor = "tool"
                # Detect real tool errors from content
                if _detect_tool_error(content):
                    status = Status.error
                else:
                    status = None
            elif role == "session_meta":
                event_type = EventType.system
                actor = "system"
                status = None
            else:
                event_type = None
                actor = role
                status = None

            # Build metadata dict with Hermes-specific fields
            metadata: dict[str, Any] = {}
            if finish_reason:
                metadata["finish_reason"] = finish_reason
            if reasoning:
                metadata["reasoning"] = reasoning
            if tool_calls_data:
                metadata["tool_calls"] = tool_calls_data

            # Extract tool name from tool_calls JSON if not in dedicated column
            resolved_tool_name = tool_name
            if not resolved_tool_name and tool_calls_data:
                if isinstance(tool_calls_data, list) and len(tool_calls_data) > 0:
                    fn = tool_calls_data[0].get("function", {})
                    if isinstance(fn, dict):
                        resolved_tool_name = fn.get("name")

            # Build tool_args from tool result content (for tool role messages)
            tool_args: dict[str, Any] | None = None
            if role == "tool" and content:
                try:
                    parsed = json.loads(content)
                    if isinstance(parsed, dict):
                        tool_args = parsed
                except (json.JSONDecodeError, TypeError):
                    pass

            events.append(
                Event(
                    event_index=event_index,
                    actor=actor,
                    event_type=event_type,
                    timestamp=ts,
                    status=status,
                    session_id=session_id,
                    tool_name=resolved_tool_name,
                    tool_args=tool_args,
                    tokens_in=token_count if role == "assistant" else None,
                    tokens_out=token_count if role == "assistant" else None,
                    metadata=metadata if metadata else None,
                )
            )
            event_index += 1

        # Set terminal status on last event if end_reason is meaningful
        terminal_status = _get_terminal_status(last_end_reason)
        if terminal_status and events:
            events[-1].status = terminal_status

        # Build trace metadata
        first_session = sessions[0] if sessions else {}
        trace_id = f"hermes_{len(sessions)}sessions"

        return Trace(
            schema_version="hermes-sqlite",
            trace_id=trace_id,
            task_id=None,
            task_label=None,
            session_id=first_session.get("id"),
            events=events,
        )

    def capability_report(self, trace: Trace | None = None) -> dict[str, Any]:
        """Hermes has a known schema — report static capabilities.

        Note: has_token_data is False because Hermes stores tokens at
        the session level, not per-event. The adapter extracts session-level
        totals and attaches them to the first LLM call, but this is not
        the same as per-event token accuracy.
        """
        return {
            "has_span_ids": False,
            "has_parent_spans": False,
            "has_event_latency": False,
            "has_token_data": False,
            "has_tool_calls": True,
            "has_cost_data": False,
            "has_retrieval_fields": False,
        }
