import json
from pathlib import Path

from trace_eval.convert import _detect_format, convert_cursor


def test_convert_cursor_basic(tmp_path):
    """Test basic Cursor session conversion."""
    sample = tmp_path / "cursor.jsonl"
    sample.write_text(
        json.dumps({"role": "user", "message": {"content": [{"type": "text", "text": "hello"}]}})
        + "\n"
        + json.dumps(
            {
                "role": "assistant",
                "message": {
                    "content": [{"type": "text", "text": "hi"}],
                    "usage": {"input": 100, "output": 50},
                    "stopReason": "end_turn",
                },
            }
        )
        + "\n"
    )
    events = convert_cursor(sample)
    assert len(events) == 2
    assert events[0]["actor"] == "user"
    assert events[0]["event_type"] == "message"
    assert events[1]["actor"] == "assistant"
    assert events[1]["event_type"] == "llm_call"
    assert events[1]["tokens_in"] == 100
    assert events[1]["tokens_out"] == 50


def test_convert_cursor_tool_calls(tmp_path):
    """Test Cursor tool_call extraction."""
    sample = tmp_path / "cursor.jsonl"
    sample.write_text(
        json.dumps(
            {
                "role": "assistant",
                "message": {"content": [{"type": "toolCall", "name": "read_file", "arguments": {"path": "app.py"}}]},
            }
        )
        + "\n"
    )
    events = convert_cursor(sample)
    assert len(events) == 2  # tool_call + llm_call
    assert events[0]["event_type"] == "tool_call"
    assert events[0]["tool_name"] == "read_file"
    assert events[0]["tool_args"] == {"path": "app.py"}
    assert events[1]["event_type"] == "llm_call"


def test_convert_cursor_tool_result_error(tmp_path):
    """Test Cursor error detection in tool results."""
    sample = tmp_path / "cursor.jsonl"
    sample.write_text(
        json.dumps(
            {
                "role": "toolResult",
                "message": {
                    "toolName": "bash",
                    "isError": True,
                    "content": [{"type": "text", "text": "exit code 1\ncommand not found"}],
                },
            }
        )
        + "\n"
    )
    events = convert_cursor(sample)
    assert len(events) == 1
    assert events[0]["event_type"] == "tool_result"
    assert events[0]["status"] == "error"


def test_convert_cursor_tool_result_success(tmp_path):
    """Test Cursor successful tool result."""
    sample = tmp_path / "cursor.jsonl"
    sample.write_text(
        json.dumps(
            {
                "role": "toolResult",
                "message": {"toolName": "edit", "content": [{"type": "text", "text": "File edited successfully"}]},
            }
        )
        + "\n"
    )
    events = convert_cursor(sample)
    assert len(events) == 1
    assert events[0]["event_type"] == "tool_result"
    assert events[0]["status"] is None


def test_cursor_auto_detect(tmp_path):
    """Test auto-detection of Cursor format."""
    sample = tmp_path / "cursor.jsonl"
    sample.write_text(json.dumps({"role": "user", "message": {"content": [{"type": "text", "text": "hello"}]}}) + "\n")
    fmt = _detect_format(sample)
    assert fmt == "cursor"


def test_convert_cursor_sample_file():
    """Test the bundled Cursor sample file converts successfully."""
    sample = Path(__file__).parent.parent / "examples" / "cursor_sample.jsonl"
    events = convert_cursor(sample)
    assert len(events) > 0
    # Should have user message, llm calls, tool calls, and tool results
    event_types = [e["event_type"] for e in events]
    assert "message" in event_types
    assert "llm_call" in event_types
    assert "tool_call" in event_types
    assert "tool_result" in event_types
    # Should detect the error in the bash tool result
    tool_results = [e for e in events if e["event_type"] == "tool_result"]
    errors = [e for e in tool_results if e["status"] == "error"]
    assert len(errors) >= 1  # The failed pytest command
