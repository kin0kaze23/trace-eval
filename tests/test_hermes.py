"""Tests for Hermes SQLite adapter against the real DB schema."""
import sqlite3
from pathlib import Path

import pytest

from trace_eval.adapters.hermes import HermesAdapter
from trace_eval.schema import EventType


@pytest.fixture
def hermes_db(tmp_path: Path):
    """Create a minimal Hermes SQLite DB matching the real schema."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    c = conn.cursor()

    c.execute("""
        CREATE TABLE sessions (
            id TEXT PRIMARY KEY,
            source TEXT,
            user_id TEXT,
            model TEXT,
            model_config TEXT,
            system_prompt TEXT,
            parent_session_id TEXT,
            started_at TEXT,
            ended_at TEXT,
            end_reason TEXT,
            message_count INTEGER,
            tool_call_count INTEGER,
            input_tokens INTEGER,
            output_tokens INTEGER,
            cache_read_tokens INTEGER,
            cache_write_tokens INTEGER,
            reasoning_tokens INTEGER,
            billing_provider TEXT,
            billing_base_url TEXT,
            billing_mode TEXT,
            estimated_cost_usd REAL,
            actual_cost_usd REAL,
            cost_status TEXT,
            cost_source TEXT,
            pricing_version INTEGER,
            title TEXT
        )
    """)

    c.execute("""
        CREATE TABLE messages (
            id INTEGER PRIMARY KEY,
            session_id TEXT,
            role TEXT,
            content TEXT,
            tool_call_id TEXT,
            tool_calls TEXT,
            tool_name TEXT,
            timestamp REAL,
            token_count INTEGER,
            finish_reason TEXT,
            reasoning TEXT
        )
    """)

    # Insert a session
    c.execute(
        "INSERT INTO sessions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [
            "sess-001", "test", "user-1", "claude-sonnet-4-6",
            None, None, None, "2026-04-15T10:00:00Z", None, None,
            3, 1, 1200, 350, 0, 0, 0, None, None, None,
            0.0, 0.045, "complete", "direct", 1, "Test Session",
        ],
    )

    # Insert messages: user, assistant, tool
    c.execute(
        "INSERT INTO messages (id, session_id, role, content, timestamp) VALUES (1, 'sess-001', 'user', 'Hello', 1744711200.0)",
    )
    c.execute(
        "INSERT INTO messages (id, session_id, role, content, timestamp, token_count) VALUES (2, 'sess-001', 'assistant', 'Hi there', 1744711205.0, 350)",
    )
    c.execute(
        "INSERT INTO messages (id, session_id, role, content, tool_name, timestamp) VALUES (3, 'sess-001', 'tool', '{\"result\": 42}', 'grep', 1744711206.0)",
    )

    conn.commit()
    conn.close()
    return db_path


def test_hermes_adapter_load(hermes_db):
    adapter = HermesAdapter()
    trace = adapter.load(hermes_db)
    assert len(trace.events) == 3
    assert trace.session_id == "sess-001"


def test_hermes_maps_roles_to_event_types(hermes_db):
    adapter = HermesAdapter()
    trace = adapter.load(hermes_db)
    assert trace.events[0].event_type == EventType.message
    assert trace.events[0].actor == "user"
    assert trace.events[1].event_type == EventType.llm_call
    assert trace.events[1].actor == "assistant"
    assert trace.events[2].event_type == EventType.tool_result
    assert trace.events[2].actor == "tool"


def test_hermes_extracts_token_data(hermes_db):
    adapter = HermesAdapter()
    trace = adapter.load(hermes_db)
    assert trace.events[1].tokens_in == 350
    assert trace.events[1].tokens_out == 350


def test_hermes_extracts_tool_name(hermes_db):
    adapter = HermesAdapter()
    trace = adapter.load(hermes_db)
    assert trace.events[2].tool_name == "grep"


def test_hermes_handles_session_meta():
    """session_meta role messages map to EventType.system."""
    db_path = Path("/tmp/test_session_meta.db")
    conn = sqlite3.connect(str(db_path))
    c = conn.cursor()
    c.execute("""
        CREATE TABLE sessions (id TEXT PRIMARY KEY, started_at TEXT)
    """)
    c.execute("""
        CREATE TABLE messages (
            id INTEGER PRIMARY KEY, session_id TEXT, role TEXT,
            content TEXT, timestamp REAL, tool_calls TEXT,
            tool_name TEXT, token_count INTEGER, finish_reason TEXT,
            reasoning TEXT, tool_call_id TEXT
        )
    """)
    c.execute("INSERT INTO sessions VALUES ('sess-1', '2026-04-15T10:00:00Z')")
    c.execute(
        "INSERT INTO messages (id, session_id, role, timestamp) VALUES (1, 'sess-1', 'session_meta', 1744711200.0)"
    )
    conn.commit()
    conn.close()

    adapter = HermesAdapter()
    trace = adapter.load(db_path)
    assert len(trace.events) == 1
    assert trace.events[0].event_type == EventType.system
    assert trace.events[0].actor == "system"

    db_path.unlink()


def test_hermes_parses_tool_calls_json(hermes_db):
    """When tool_name is missing but tool_calls JSON exists, extract from it."""
    db_path = Path("/tmp/test_tool_calls.db")
    conn = sqlite3.connect(str(db_path))
    c = conn.cursor()
    c.execute("CREATE TABLE sessions (id TEXT PRIMARY KEY, started_at TEXT)")
    c.execute(
        "CREATE TABLE messages (id INTEGER PRIMARY KEY, session_id TEXT, role TEXT, content TEXT, tool_calls TEXT, tool_name TEXT, timestamp REAL, token_count INTEGER, finish_reason TEXT, reasoning TEXT, tool_call_id TEXT)"
    )
    c.execute("INSERT INTO sessions VALUES ('sess-1', '2026-04-15T10:00:00Z')")
    tool_calls_json = '[{"function": {"name": "file_search", "arguments": "{}"}}]'
    c.execute(
        "INSERT INTO messages (id, session_id, role, tool_calls, timestamp) VALUES (1, 'sess-1', 'assistant', ?, 1744711200.0)",
        [tool_calls_json],
    )
    conn.commit()
    conn.close()

    adapter = HermesAdapter()
    trace = adapter.load(db_path)
    assert trace.events[0].tool_name == "file_search"

    db_path.unlink()


def test_hermes_parses_tool_args_from_content(hermes_db):
    """Tool result content is parsed as JSON for tool_args."""
    adapter = HermesAdapter()
    trace = adapter.load(hermes_db)
    assert trace.events[2].tool_args == {"result": 42}


def test_hermes_empty_db(tmp_path):
    """Empty sessions table returns empty Trace."""
    db_path = tmp_path / "empty.db"
    conn = sqlite3.connect(str(db_path))
    c = conn.cursor()
    c.execute("CREATE TABLE sessions (id TEXT PRIMARY KEY, started_at TEXT)")
    c.execute(
        "CREATE TABLE messages (id INTEGER PRIMARY KEY, session_id TEXT, role TEXT, content TEXT, timestamp REAL, tool_calls TEXT, tool_name TEXT, token_count INTEGER, finish_reason TEXT, reasoning TEXT, tool_call_id TEXT)"
    )
    conn.commit()
    conn.close()

    adapter = HermesAdapter()
    trace = adapter.load(db_path)
    assert len(trace.events) == 0


def test_hermes_capability_report():
    adapter = HermesAdapter()
    report = adapter.capability_report()
    assert report["has_span_ids"] is False
    assert report["has_parent_spans"] is False
    assert report["has_event_latency"] is False
    assert report["has_token_data"] is True
    assert report["has_tool_calls"] is True
    assert report["has_cost_data"] == "partial"
    assert report["has_retrieval_fields"] is False


def test_hermes_honest_lossy():
    """Hermes adapter should not synthesize span IDs."""
    adapter = HermesAdapter()
    report = adapter.capability_report()
    assert report["has_span_ids"] is False
    assert report["has_parent_spans"] is False
