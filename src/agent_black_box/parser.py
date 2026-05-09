from __future__ import annotations

import json
from json import JSONDecodeError
from pathlib import Path
from typing import Any

from agent_black_box.models import TraceEvent, TraceRun

DEFAULT_RUN_ID = "unknown-run"


class TraceParseError(ValueError):
    pass


def parse_jsonl_trace(path: str | Path, *, strict: bool = False) -> TraceRun:
    path = Path(path)
    run = TraceRun(run_id=DEFAULT_RUN_ID)

    for line_number, raw_line in enumerate(path.read_text().splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue

        obj = _parse_json_line(line, path=path, line_number=line_number, strict=strict, warnings=run.ingest_warnings)
        if obj is None:
            continue
        _ingest_event(run, obj)

    return run


def _parse_json_line(line: str, *, path: Path, line_number: int, strict: bool, warnings: list[str]) -> dict[str, Any] | None:
    try:
        obj = json.loads(line)
    except JSONDecodeError as exc:
        message = f"line {line_number}: invalid JSON ({exc.msg})"
        if strict:
            raise TraceParseError(f"{path.name} {message}") from exc
        warnings.append(message)
        return None

    if not isinstance(obj, dict):
        message = f"line {line_number}: expected JSON object"
        if strict:
            raise TraceParseError(f"{path.name} {message}")
        warnings.append(message)
        return None

    return obj


def _ingest_event(run: TraceRun, obj: dict[str, Any]) -> None:
    run.run_id = str(obj.get("run_id") or run.run_id)
    run.agent = obj.get("agent") or run.agent
    run.session_id = obj.get("session_id") or run.session_id

    event = TraceEvent(
        ts=str(obj.get("ts") or obj.get("timestamp") or "unknown-ts"),
        kind=str(obj.get("kind") or obj.get("type") or "unknown"),
        source=str(obj.get("source") or "unknown"),
        data={k: v for k, v in obj.items() if k not in {"run_id", "agent", "session_id", "ts", "timestamp", "kind", "type", "source"}},
    )
    run.add_event(event)
