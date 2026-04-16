"""Convert non-canonical agent traces to trace-eval canonical JSONL.

Supports:
  - Claude Code sessions (.jsonl from ~/.claude/projects/)
  - OpenClaw sessions (.jsonl from ~/.openclaw/)

Usage:
  trace-eval convert claude-code ~/.claude/projects/.../session.jsonl -o output.jsonl
  trace-eval convert openclaw ~/.openclaw/.../session.jsonl -o output.jsonl
"""

from __future__ import annotations

import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from trace_eval.schema import Event, EventType, Status


# ---------------------------------------------------------------------------
# Claude Code converter
# ---------------------------------------------------------------------------

def _cc_detect_error(text: str) -> bool:
    """Detect errors in Claude Code tool result content."""
    if not text:
        return False
    # Explicit error field
    if '"error": ' in text and '"error": null' not in text and '"error": ""' not in text:
        return True
    # Non-zero exit codes
    for line in text.split("\n")[:5]:
        if "exit code" in line.lower():
            code_part = line.lower().split("exit code")[-1].strip()
            try:
                if int(code_part.split()[0]) != 0:
                    return True
            except (ValueError, IndexError):
                pass
    # Command-not-found patterns
    error_patterns = [
        "command not found", "no such file or directory", "not found",
        "permission denied", "is a directory", "illegal operation",
        "exit code 1", "exit code 2", "exit code 127", "exit code 128",
    ]
    for pat in error_patterns:
        if pat.lower() in text.lower():
            return True
    return False


def convert_claude_code(input_path: Path) -> list[dict]:
    """Convert a Claude Code session JSONL to canonical events."""
    with open(input_path) as f:
        raw_events = [json.loads(l) for l in f if l.strip()]

    # Extract session ID from first event
    session_id = ""
    for e in raw_events:
        sid = e.get("sessionId")
        if sid:
            session_id = sid
            break

    trace_id = f"claude_code_{session_id[:8] if session_id else 'unknown'}"

    canonical = []
    idx = 0

    for e in raw_events:
        etype = e.get("type", "")

        # Skip metadata events
        if etype in (
            "permission-mode", "file-history-snapshot", "attachment",
            "custom-title", "agent-name", "last-prompt", "queue-operation",
        ):
            continue

        if etype == "system":
            # System messages - skip (not user-facing events)
            continue

        if etype == "user":
            msg = e.get("message", {})
            content = msg.get("content", "")

            # Check if this is a tool_result (content is a list with tool_result type)
            if isinstance(content, list):
                has_tool_result = any(
                    isinstance(c, dict) and c.get("type") == "tool_result"
                    for c in content
                )
                has_text = any(
                    isinstance(c, dict) and c.get("type") == "text"
                    for c in content
                )

                if has_tool_result:
                    # This is a tool result response
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "tool_result":
                            tool_result_text = ""
                            inner_content = block.get("content", "")
                            if isinstance(inner_content, str):
                                tool_result_text = inner_content
                            elif isinstance(inner_content, list):
                                tool_result_text = "\n".join(
                                    c.get("text", "") for c in inner_content
                                    if isinstance(c, dict) and c.get("type") == "text"
                                )

                            is_error = block.get("isError", False)
                            has_error = is_error or _cc_detect_error(tool_result_text)
                            status = "error" if has_error else None

                            tool_args = None
                            if tool_result_text.strip().startswith("{"):
                                try:
                                    parsed = json.loads(tool_result_text)
                                    if isinstance(parsed, dict):
                                        tool_args = parsed
                                except (json.JSONDecodeError, TypeError):
                                    pass

                            canonical.append({
                                "event_index": idx,
                                "actor": "tool",
                                "event_type": "tool_result",
                                "timestamp": e.get("timestamp", ""),
                                "status": status,
                                "session_id": session_id,
                                "tool_args": tool_args,
                            })
                            idx += 1

                elif has_text:
                    # Regular user message with text content
                    text_parts = [
                        c.get("text", "") for c in content
                        if isinstance(c, dict) and c.get("type") == "text" and c.get("text")
                    ]
                    if text_parts:
                        canonical.append({
                            "event_index": idx,
                            "actor": "user",
                            "event_type": "message",
                            "timestamp": e.get("timestamp", ""),
                            "status": None,
                            "session_id": session_id,
                            "schema_version": "v1",
                            "trace_id": trace_id,
                        })
                        idx += 1
                # If neither tool_result nor text, skip (could be just metadata)

            elif isinstance(content, str) and len(content) > 0:
                canonical.append({
                    "event_index": idx,
                    "actor": "user",
                    "event_type": "message",
                    "timestamp": e.get("timestamp", ""),
                    "status": None,
                    "session_id": session_id,
                    "schema_version": "v1",
                    "trace_id": trace_id,
                })
                idx += 1
            continue

        if etype == "assistant":
            msg = e.get("message", {})
            content_blocks = msg.get("content", [])
            usage = msg.get("usage", {})
            stop_reason = msg.get("stop_reason")

            # Extract tool uses
            for block in content_blocks:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    tool_name = block.get("name", "unknown")
                    tool_input = block.get("input", {})
                    canonical.append({
                        "event_index": idx,
                        "actor": "assistant",
                        "event_type": "tool_call",
                        "timestamp": e.get("timestamp", ""),
                        "status": None,
                        "session_id": session_id,
                        "tool_name": tool_name,
                        "tool_args": tool_input if isinstance(tool_input, dict) else None,
                    })
                    idx += 1

            # Emit LLM call event
            status = None
            if stop_reason == "error":
                status = "error"

            tokens_in = None
            tokens_out = None
            if isinstance(usage, dict):
                ti = usage.get("input_tokens")
                to = usage.get("output_tokens")
                if ti is not None and ti > 0:
                    tokens_in = int(ti)
                if to is not None and to > 0:
                    tokens_out = int(to)

            canonical.append({
                "event_index": idx,
                "actor": "assistant",
                "event_type": "llm_call",
                "timestamp": e.get("timestamp", ""),
                "status": status,
                "session_id": session_id,
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
            })
            idx += 1
            continue

        if etype == "tool_result":
            msg = e.get("message", {})
            content_blocks = msg.get("content", [])
            is_error = msg.get("isError", False)

            # Extract tool name from content
            tool_name = None
            text_parts = []
            for block in content_blocks:
                if isinstance(block, dict):
                    t = block.get("text", "")
                    if t:
                        text_parts.append(t)
                    # Try to get tool name from type field
                    tn = block.get("type")
                    if tn and tn != "text":
                        tool_name = tn

            text = "\n".join(text_parts)

            # Detect error status
            has_error = is_error or _cc_detect_error(text)
            status = "error" if has_error else None

            # Try to parse tool_args from first text block
            tool_args = None
            if text.strip().startswith("{"):
                try:
                    parsed = json.loads(text)
                    if isinstance(parsed, dict):
                        tool_args = parsed
                except (json.JSONDecodeError, TypeError):
                    pass

            canonical.append({
                "event_index": idx,
                "actor": "tool",
                "event_type": "tool_result",
                "timestamp": e.get("timestamp", ""),
                "status": status,
                "session_id": session_id,
                "tool_name": tool_name,
                "tool_args": tool_args,
            })
            idx += 1
            continue

    return canonical


# ---------------------------------------------------------------------------
# OpenClaw converter
# ---------------------------------------------------------------------------

def convert_openclaw(input_path: Path) -> list[dict]:
    """Convert an OpenClaw session JSONL to canonical events."""
    with open(input_path) as f:
        raw_events = [json.loads(l) for l in f if l.strip()]

    session_id = ""
    cwd = ""
    for e in raw_events:
        if e.get("type") == "session":
            session_id = e.get("id", "")
            cwd = e.get("cwd", "")
            break

    trace_id = f"openclaw_{session_id[:8] if session_id else 'unknown'}"

    canonical = []
    idx = 0

    for e in raw_events:
        etype = e.get("type", "")

        if etype == "session":
            canonical.append({
                "event_index": idx,
                "actor": "system",
                "event_type": "session_start",
                "timestamp": e.get("timestamp", ""),
                "status": None,
                "session_id": session_id,
                "schema_version": "v1",
                "trace_id": trace_id,
                "cwd": cwd,
            })
            idx += 1
            continue

        if etype in ("model_change", "thinking_level_change", "custom"):
            continue

        if etype == "message":
            msg = e.get("message", {})
            role = msg.get("role", "unknown")
            content_items = msg.get("content", [])
            usage = msg.get("usage", {})
            stop_reason = msg.get("stopReason")

            text_parts = []
            tool_calls = []
            for c in content_items:
                if not isinstance(c, dict):
                    continue
                if c.get("type") == "text":
                    text_parts.append(c.get("text", ""))
                elif c.get("type") == "toolCall":
                    tool_calls.append(c)
                elif c.get("type") == "thinking":
                    pass  # Skip thinking blocks

            if role == "user":
                canonical.append({
                    "event_index": idx,
                    "actor": "user",
                    "event_type": "message",
                    "timestamp": e.get("timestamp", ""),
                    "status": None,
                    "session_id": session_id,
                })
                idx += 1

            elif role == "assistant":
                # Emit tool_call events
                for tc in tool_calls:
                    tool_name = tc.get("name", "unknown")
                    tool_args = tc.get("arguments", {})
                    canonical.append({
                        "event_index": idx,
                        "actor": "assistant",
                        "event_type": "tool_call",
                        "timestamp": e.get("timestamp", ""),
                        "status": None,
                        "session_id": session_id,
                        "tool_name": tool_name,
                        "tool_args": tool_args if isinstance(tool_args, dict) else None,
                    })
                    idx += 1

                # Emit LLM call event
                status = None
                if stop_reason == "error":
                    status = "error"

                tokens_in = None
                tokens_out = None
                if isinstance(usage, dict):
                    ti = usage.get("input")
                    to = usage.get("output")
                    if ti and ti > 0:
                        tokens_in = int(ti)
                    if to and to > 0:
                        tokens_out = int(to)

                canonical.append({
                    "event_index": idx,
                    "actor": "assistant",
                    "event_type": "llm_call",
                    "timestamp": e.get("timestamp", ""),
                    "status": status,
                    "session_id": session_id,
                    "tokens_in": tokens_in,
                    "tokens_out": tokens_out,
                })
                idx += 1

            elif role == "toolResult":
                tool_name = msg.get("toolName", "unknown")
                content_texts = []
                for c in content_items:
                    if isinstance(c, dict):
                        content_texts.append(c.get("text", ""))

                content = "\n".join(content_texts)
                is_error = msg.get("isError", False)

                has_error = is_error or (
                    '"status": "error"' in content or '"error":' in content
                )
                status = "error" if has_error else None

                tool_args = None
                if content.strip().startswith("{"):
                    try:
                        parsed = json.loads(content)
                        if isinstance(parsed, dict):
                            tool_args = parsed
                    except (json.JSONDecodeError, TypeError):
                        pass

                canonical.append({
                    "event_index": idx,
                    "actor": "tool",
                    "event_type": "tool_result",
                    "timestamp": e.get("timestamp", ""),
                    "status": status,
                    "session_id": session_id,
                    "tool_name": tool_name,
                    "tool_args": tool_args,
                })
                idx += 1

    return canonical


# ---------------------------------------------------------------------------
# Cursor converter
# ---------------------------------------------------------------------------

def convert_cursor(input_path: Path) -> list[dict]:
    """Convert a Cursor agent transcript JSONL to canonical events.

    Cursor stores agent transcripts as JSONL with role-based messages:
    - "user" with text content
    - "assistant" with text and/or toolCall content blocks
    - "toolResult" with toolName, optional isError, and text content
    """
    with open(input_path) as f:
        raw_events = [json.loads(l) for l in f if l.strip()]

    # Extract session ID from file path
    session_id = input_path.stem
    trace_id = f"cursor_{session_id[:8]}"

    canonical = []
    idx = 0

    for e in raw_events:
        role = e.get("role", "")
        msg = e.get("message", {})
        content_items = msg.get("content", [])
        usage = msg.get("usage", {})
        stop_reason = msg.get("stopReason")

        if role == "user":
            text_parts = [
                c.get("text", "") for c in content_items
                if isinstance(c, dict) and c.get("type") == "text"
            ]
            if text_parts:
                canonical.append({
                    "event_index": idx,
                    "actor": "user",
                    "event_type": "message",
                    "timestamp": e.get("timestamp", ""),
                    "status": None,
                    "session_id": session_id,
                    "schema_version": "v1",
                    "trace_id": trace_id,
                })
                idx += 1

        elif role == "assistant":
            # Emit tool_call events
            for c in content_items:
                if isinstance(c, dict) and c.get("type") == "toolCall":
                    tool_name = c.get("name", "unknown")
                    tool_args = c.get("arguments", {})
                    canonical.append({
                        "event_index": idx,
                        "actor": "assistant",
                        "event_type": "tool_call",
                        "timestamp": e.get("timestamp", ""),
                        "status": None,
                        "session_id": session_id,
                        "tool_name": tool_name,
                        "tool_args": tool_args if isinstance(tool_args, dict) else None,
                    })
                    idx += 1

            # Emit LLM call event
            status = None
            if stop_reason == "error":
                status = "error"

            tokens_in = None
            tokens_out = None
            if isinstance(usage, dict):
                ti = usage.get("input")
                to = usage.get("output")
                if ti is not None and ti > 0:
                    tokens_in = int(ti)
                if to is not None and to > 0:
                    tokens_out = int(to)

            canonical.append({
                "event_index": idx,
                "actor": "assistant",
                "event_type": "llm_call",
                "timestamp": e.get("timestamp", ""),
                "status": status,
                "session_id": session_id,
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
            })
            idx += 1

        elif role == "toolResult":
            tool_name = msg.get("toolName", "unknown")
            content_texts = []
            for c in content_items:
                if isinstance(c, dict):
                    content_texts.append(c.get("text", ""))

            content = "\n".join(content_texts)
            is_error = msg.get("isError", False)

            has_error = is_error or _cc_detect_error(content)
            status = "error" if has_error else None

            tool_args = None
            if content.strip().startswith("{"):
                try:
                    parsed = json.loads(content)
                    if isinstance(parsed, dict):
                        tool_args = parsed
                except (json.JSONDecodeError, TypeError):
                    pass

            canonical.append({
                "event_index": idx,
                "actor": "tool",
                "event_type": "tool_result",
                "timestamp": e.get("timestamp", ""),
                "status": status,
                "session_id": session_id,
                "tool_name": tool_name,
                "tool_args": tool_args,
            })
            idx += 1

    return canonical


# ---------------------------------------------------------------------------
# Generic converter (auto-detect format)
# ---------------------------------------------------------------------------

def _detect_format(input_path: Path) -> str:
    """Auto-detect trace format from the file content."""
    with open(input_path) as f:
        # Read first 5 lines to find a recognizable event
        lines = []
        for i, line in enumerate(f):
            if i >= 5:
                break
            line = line.strip()
            if line:
                lines.append(line)

    for line in lines:
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue

        if data.get("type") == "session" and "cwd" in data:
            return "openclaw"
        if data.get("type") in ("permission-mode", "user", "assistant", "tool_result"):
            return "claude_code"
        if "event_type" in data:
            return "canonical"
        # Cursor format: has "role" field with "user", "assistant", or "toolResult"
        if "role" in data and data["role"] in ("user", "assistant", "toolResult"):
            return "cursor"  # Already canonical

    return "unknown"


CONVERTERS = {
    "claude-code": convert_claude_code,
    "claude_code": convert_claude_code,
    "openclaw": convert_openclaw,
    "cursor": convert_cursor,
}


def convert(input_path: Path, fmt: str | None = None) -> list[dict]:
    """Convert a trace file to canonical events."""
    if fmt is None:
        fmt = _detect_format(input_path)

    if fmt == "canonical":
        # Already canonical, just return as-is
        events = []
        with open(input_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    events.append(json.loads(line))
        return events

    converter = CONVERTERS.get(fmt)
    if converter is None:
        raise ValueError(f"Unknown format: {fmt}. Supported: {list(CONVERTERS.keys())}")

    return converter(input_path)
