"""Tests for doctor command."""

from trace_eval.doctor import (
    _agent_status_icon,
    _build_recommendation,
    _human_size,
    format_doctor_json,
    format_doctor_text,
    run_doctor,
)


def test_doctor_returns_version():
    result = run_doctor()
    assert "version" in result
    assert result["version"] == "0.6.0"


def test_doctor_returns_python_version():
    result = run_doctor()
    assert "python" in result
    assert "." in result["python"]


def test_doctor_checks_all_agents():
    result = run_doctor()
    assert "agents" in result
    agent_names = [a["agent"] for a in result["agents"]]
    assert "claude-code" in agent_names
    assert "openclaw" in agent_names
    assert "cursor" in agent_names


def test_doctor_has_recommendation():
    result = run_doctor()
    assert "recommendation" in result
    assert isinstance(result["recommendation"], str)
    assert len(result["recommendation"]) > 0


def test_doctor_total_traces():
    result = run_doctor()
    assert "total_traces" in result
    assert isinstance(result["total_traces"], int)


def test_doctor_text_format_has_version():
    result = run_doctor()
    output = format_doctor_text(result)
    assert "0.6.0" in output


def test_doctor_text_format_has_installation():
    result = run_doctor()
    output = format_doctor_text(result)
    assert "INSTALLATION:" in output


def test_doctor_text_format_has_agent_detection():
    result = run_doctor()
    output = format_doctor_text(result)
    assert "AGENT DETECTION:" in output


def test_doctor_text_format_has_recommendation():
    result = run_doctor()
    output = format_doctor_text(result)
    assert "RECOMMENDED:" in output


def test_doctor_json_is_valid():
    result = run_doctor()
    output = format_doctor_json(result)
    import json

    parsed = json.loads(output)
    assert "version" in parsed
    assert "agents" in parsed
    assert "recommendation" in parsed


def test_human_size():
    assert _human_size(500) == "500B"
    assert _human_size(1024) == "1KB"
    assert _human_size(1048576) == "1.0MB"
    assert _human_size(10485760) == "10.0MB"


def test_agent_status_icon():
    assert _agent_status_icon("found") == "[+]"
    assert _agent_status_icon("not_found") == "[-]"
    assert _agent_status_icon("unknown") == "[?]"
    assert _agent_status_icon("other") == "[ ]"


def test_recommendation_with_traces():
    result = {
        "total_traces": 5,
        "agents": [],
    }
    rec = _build_recommendation(result)
    assert "loop" in rec


def test_recommendation_no_traces_with_dirs():
    result = {
        "total_traces": 0,
        "agents": [
            {"status": "found", "trace_count": 0, "agent": "claude-code"},
        ],
    }
    rec = _build_recommendation(result)
    assert "hours" in rec.lower() or "168" in rec


def test_recommendation_no_traces_no_dirs():
    result = {
        "total_traces": 0,
        "agents": [
            {"status": "not_found", "trace_count": 0, "agent": "claude-code"},
        ],
    }
    rec = _build_recommendation(result)
    assert "install" in rec.lower() or "convert" in rec.lower()
