import pytest

from agent_black_box.adapters import parse_trace
from agent_black_box.parser import TraceParseError, parse_jsonl_trace
from agent_black_box.reporting import render_incident_summary
from agent_black_box.timeline import render_timeline


def test_parse_jsonl_trace_best_effort_skips_malformed_rows_with_warnings(tmp_path):
    trace = tmp_path / "partial.jsonl"
    trace.write_text(
        '{"run_id":"r1","ts":"1","kind":"prompt","source":"user","message":"start"}\n'
        '{bad json}\n'
        '{"run_id":"r1","ts":"2","kind":"completion","source":"assistant","message":"done"}\n'
    )

    run = parse_jsonl_trace(trace)

    assert [event.kind for event in run.events] == ["prompt", "completion"]
    assert run.ingest_warnings == ["line 2: invalid JSON (Expecting property name enclosed in double quotes)"]

    timeline = render_timeline(run)
    summary = render_incident_summary(run)
    assert "ingest_warnings: 1" in timeline
    assert "ingest_warnings: 1" in summary
    assert "line 2: invalid JSON" in summary


def test_parse_jsonl_trace_strict_raises_line_numbered_error(tmp_path):
    trace = tmp_path / "bad.jsonl"
    trace.write_text('{"run_id":"r1","ts":"1","kind":"prompt"}\n{bad json}\n')

    with pytest.raises(TraceParseError, match="bad.jsonl line 2: invalid JSON"):
        parse_jsonl_trace(trace, strict=True)


def test_parse_openclaw_jsonl_best_effort_keeps_valid_session_rows(tmp_path):
    trace = tmp_path / "openclaw-partial.jsonl"
    trace.write_text(
        '{"type":"session","version":3,"id":"sess-123","timestamp":"2026-04-14T12:00:00Z"}\n'
        '{bad json}\n'
        '{"type":"message","id":"u1","timestamp":"2026-04-14T12:00:01Z","message":{"role":"user","content":[{"type":"text","text":"hello"}]}}\n'
    )

    run = parse_trace(trace, source_format="openclaw-jsonl")

    assert run.run_id == "sess-123"
    assert [event.kind for event in run.events] == ["session_start", "prompt"]
    assert run.ingest_warnings == ["line 2: invalid JSON (Expecting property name enclosed in double quotes)"]
