"""Trace file loading and adapter dispatch."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from trace_eval.adapters.generic_jsonl import GenericJsonlAdapter
from trace_eval.adapters.hermes import HermesAdapter
from trace_eval.schema import Trace


def detect_adapter(path: Path):
    """Auto-detect adapter based on file extension."""
    suffix = path.suffix.lower()
    if suffix in (".jsonl", ".json"):
        return GenericJsonlAdapter()
    if suffix in (".db", ".sqlite", ".sqlite3"):
        return HermesAdapter()
    raise ValueError(f"Unknown file type: {suffix}")


def load_trace(path: Path) -> Trace:
    """Load a trace file using auto-detected adapter."""
    adapter = detect_adapter(path)
    return adapter.load(path)


def load_trace_with_report(path: Path) -> tuple[Trace, dict[str, Any]]:
    """Load a trace and get the adapter capability report."""
    adapter = detect_adapter(path)
    trace = adapter.load(path)
    report = adapter.capability_report(trace)
    return trace, report
