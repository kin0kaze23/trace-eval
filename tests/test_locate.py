import json

from trace_eval.locate import _is_valid_trace, format_locate


def test_is_valid_trace_claude_code(tmp_path):
    f = tmp_path / "test.jsonl"
    f.write_text(json.dumps({"type": "user", "message": {"content": "hi"}}) + "\n")
    assert _is_valid_trace(f, "claude-code") is True


def test_is_valid_trace_cursor(tmp_path):
    f = tmp_path / "test.jsonl"
    f.write_text(json.dumps({"role": "user", "message": {"content": []}}) + "\n")
    assert _is_valid_trace(f, "cursor") is True


def test_is_valid_trace_openclaw(tmp_path):
    f = tmp_path / "test.jsonl"
    f.write_text(json.dumps({"type": "session", "cwd": "/tmp"}) + "\n")
    assert _is_valid_trace(f, "openclaw") is True


def test_is_valid_trace_empty_file(tmp_path):
    f = tmp_path / "test.jsonl"
    f.write_text("")
    assert _is_valid_trace(f, "claude-code") is False


def test_is_valid_trace_invalid_json(tmp_path):
    f = tmp_path / "test.jsonl"
    f.write_text("not json\n")
    assert _is_valid_trace(f, "claude-code") is False


def test_format_locate_empty():
    text = format_locate([])
    assert "No recent trace files" in text


def test_format_locate_with_results(tmp_path):
    f = tmp_path / "session.jsonl"
    f.write_text(json.dumps({"type": "user"}) + "\n")
    from trace_eval.locate import TraceLocation

    locs = [
        TraceLocation(
            agent_type="claude-code",
            path=str(f),
            size_bytes=1024,
            modified_time="5m ago",
            project_name="my-project",
        )
    ]
    text = format_locate(locs)
    assert "my-project" in text
    assert "claude-code" in text
    assert "Found 1 recent trace" in text
