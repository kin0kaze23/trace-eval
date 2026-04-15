"""Generic JSONL adapter for trace-eval."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from trace_eval.schema import Event, Trace


class GenericJsonlAdapter:
    """Reads newline-delimited JSONL files into canonical Trace objects."""

    def load(self, path: Path) -> Trace:
        events: list[Event] = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                events.append(Event.from_dict(data))
        return Trace.from_events(events)

    def capability_report(self, trace: Trace) -> dict[str, Any]:
        """Report capabilities based on OBSERVED field coverage in the trace."""
        events = trace.events
        if not events:
            return {
                "has_span_ids": False,
                "has_parent_spans": False,
                "has_event_latency": False,
                "has_token_data": False,
                "has_tool_calls": False,
                "has_cost_data": False,
                "has_retrieval_fields": False,
            }
        return {
            "has_span_ids": any(e.span_id for e in events),
            "has_parent_spans": any(e.parent_span_id for e in events),
            "has_event_latency": any(e.latency_ms is not None for e in events),
            "has_token_data": any(e.tokens_in is not None or e.tokens_out is not None for e in events),
            "has_tool_calls": any(e.tool_name for e in events),
            "has_cost_data": any(e.cost_estimate is not None for e in events),
            "has_retrieval_fields": any(
                e.retrieval_entrypoint or e.retrieval_steps or e.deprecated_file_touched or e.fallback_search_used
                for e in events
            ),
        }
