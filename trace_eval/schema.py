"""Canonical trace schema types for trace-eval v1."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class EventType(Enum):
    message = "message"
    llm_call = "llm_call"
    tool_call = "tool_call"
    tool_result = "tool_result"
    vault_read = "vault_read"
    memory_read = "memory_read"
    memory_write = "memory_write"
    search_fallback = "search_fallback"
    context_warning = "context_warning"
    context_compress = "context_compress"
    system = "system"
    session_start = "session_start"
    session_end = "session_end"


class Status(Enum):
    success = "success"
    error = "error"
    partial = "partial"
    timeout = "timeout"


@dataclass
class FrictionFlag:
    id: str
    severity: str  # "critical" | "high" | "medium" | "low"
    dimension: str
    event_index: int | None
    suggestion: str


@dataclass
class JudgeResult:
    score: float | None
    confidence: str  # "high" | "medium" | "low"
    friction_flags: list[FrictionFlag]
    explanation: str
    raw_metrics: dict[str, Any]
    scorable: bool


@dataclass
class FieldCoverageEntry:
    present: int = 0
    total: int = 0

    @property
    def coverage_pct(self) -> float:
        if self.total == 0:
            return 100.0
        return (self.present / self.total) * 100


@dataclass
class FieldCoverage:
    fields: dict[str, FieldCoverageEntry] = field(default_factory=dict)

    @staticmethod
    def compute(events: list[Event]) -> FieldCoverage:
        tracked = [
            "tokens_in", "tokens_out", "cost_estimate", "latency_ms",
            "context_pressure_pct", "context_tokens", "tool_name",
            "tool_args", "retrieval_entrypoint", "retrieval_steps",
            "deprecated_file_touched", "fallback_search_used",
            "span_id", "parent_span_id", "error_type",
        ]
        coverage: dict[str, FieldCoverageEntry] = {}
        for f in tracked:
            present = sum(1 for e in events if getattr(e, f, None) is not None)
            coverage[f] = FieldCoverageEntry(present=present, total=len(events))
        return FieldCoverage(fields=coverage)


@dataclass
class Event:
    event_index: int
    actor: str
    event_type: EventType | None
    timestamp: str
    status: Status | None

    # Trace-level fields (denormalized from first event or per-event)
    schema_version: str | None = None
    trace_id: str | None = None
    task_id: str | None = None
    task_label: str | None = None
    session_id: str | None = None

    # Extended fields
    span_id: str | None = None
    parent_span_id: str | None = None
    tool_name: str | None = None
    tool_args: dict[str, Any] | None = None
    latency_ms: int | None = None
    error_type: str | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    cost_estimate: float | None = None
    context_tokens: int | None = None
    context_pressure_pct: float | None = None
    retrieval_entrypoint: str | None = None
    retrieval_steps: list[str] | None = None
    deprecated_file_touched: bool | None = None
    fallback_search_used: bool | None = None

    # Meta fields
    model: str | None = None
    provider: str | None = None
    environment: str | None = None
    cwd: str | None = None
    repo: str | None = None
    metadata: dict[str, Any] | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Event:
        event_type_str = data.get("event_type")
        event_type = None
        if event_type_str:
            try:
                event_type = EventType(event_type_str)
            except ValueError:
                event_type = None

        status_str = data.get("status")
        status = None
        if status_str:
            try:
                status = Status(status_str)
            except ValueError:
                status = None

        return cls(
            event_index=int(data["event_index"]),
            actor=str(data.get("actor", "unknown")),
            event_type=event_type,
            timestamp=str(data.get("timestamp", "")),
            status=status,
            schema_version=data.get("schema_version"),
            trace_id=data.get("trace_id"),
            task_id=data.get("task_id"),
            task_label=data.get("task_label"),
            session_id=data.get("session_id"),
            span_id=data.get("span_id"),
            parent_span_id=data.get("parent_span_id"),
            tool_name=data.get("tool_name"),
            tool_args=data.get("tool_args"),
            latency_ms=int(data["latency_ms"]) if "latency_ms" in data and data["latency_ms"] is not None else None,
            error_type=data.get("error_type"),
            tokens_in=int(data["tokens_in"]) if "tokens_in" in data and data["tokens_in"] is not None else None,
            tokens_out=int(data["tokens_out"]) if "tokens_out" in data and data["tokens_out"] is not None else None,
            cost_estimate=float(data["cost_estimate"]) if "cost_estimate" in data and data["cost_estimate"] is not None else None,
            context_tokens=int(data["context_tokens"]) if "context_tokens" in data and data["context_tokens"] is not None else None,
            context_pressure_pct=float(data["context_pressure_pct"]) if "context_pressure_pct" in data and data["context_pressure_pct"] is not None else None,
            retrieval_entrypoint=data.get("retrieval_entrypoint"),
            retrieval_steps=data.get("retrieval_steps"),
            deprecated_file_touched=data.get("deprecated_file_touched"),
            fallback_search_used=data.get("fallback_search_used"),
            model=data.get("model"),
            provider=data.get("provider"),
            environment=data.get("environment"),
            cwd=data.get("cwd"),
            repo=data.get("repo"),
            metadata=data.get("metadata"),
        )


@dataclass
class Trace:
    schema_version: str | None = None
    trace_id: str | None = None
    task_id: str | None = None
    task_label: str | None = None
    session_id: str | None = None
    events: list[Event] = field(default_factory=list)

    @classmethod
    def from_events(cls, events: list[Event]) -> Trace:
        first = events[0] if events else None
        return cls(
            schema_version=first.schema_version if first else None,
            trace_id=first.trace_id if first else None,
            task_id=first.task_id if first else None,
            task_label=first.task_label if first else None,
            session_id=first.session_id if first else None,
            events=sorted(events, key=lambda e: e.event_index),
        )
