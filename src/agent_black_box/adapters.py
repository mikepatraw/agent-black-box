from __future__ import annotations

from pathlib import Path
from typing import Any

from agent_black_box.models import TraceEvent, TraceRun
from agent_black_box.parser import _parse_json_line


OPENCLAW_SIMPLE_KEYS = {"run_id", "agent", "session_id", "ts", "timestamp", "event", "kind", "source"}
OPENCLAW_SESSION_KEYS = {"type", "version", "id", "timestamp", "cwd", "parentId"}


def parse_trace(path: str | Path, source_format: str = "jsonl", *, strict: bool = False) -> TraceRun:
    if source_format == "jsonl":
        from agent_black_box.parser import parse_jsonl_trace

        return parse_jsonl_trace(path, strict=strict)

    if source_format == "openclaw-jsonl":
        return parse_openclaw_jsonl(path, strict=strict)

    raise ValueError(f"unsupported source format: {source_format}")


def parse_openclaw_jsonl(path: str | Path, *, strict: bool = False) -> TraceRun:
    path = Path(path)
    warnings: list[str] = []
    rows = []
    for line_number, raw_line in enumerate(path.read_text().splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        row = _parse_json_line(line, path=path, line_number=line_number, strict=strict, warnings=warnings)
        if row is not None:
            rows.append(row)
    if not rows:
        return TraceRun(run_id="openclaw-run", ingest_warnings=warnings)

    if _looks_like_openclaw_session(rows[0]):
        run = _parse_openclaw_session_rows(rows)
    else:
        run = _parse_openclaw_simple_rows(rows)
    run.ingest_warnings.extend(warnings)
    return run


def _looks_like_openclaw_session(row: dict[str, Any]) -> bool:
    return row.get("type") == "session" or ("type" in row and row.get("type") in {"message", "model_change", "thinking_level_change", "custom"})


def _parse_openclaw_simple_rows(rows: list[dict[str, Any]]) -> TraceRun:
    run = TraceRun(run_id="openclaw-run")

    for obj in rows:
        run.run_id = str(obj.get("run_id") or obj.get("session_id") or run.run_id)
        run.agent = obj.get("agent") or "openclaw"
        run.session_id = obj.get("session_id") or run.session_id
        run.add_event(
            TraceEvent(
                ts=str(obj.get("ts") or obj.get("timestamp") or "unknown-ts"),
                kind=str(obj.get("event") or obj.get("kind") or "unknown"),
                source=str(obj.get("source") or "openclaw"),
                data={k: v for k, v in obj.items() if k not in OPENCLAW_SIMPLE_KEYS},
            )
        )

    return run


def _parse_openclaw_session_rows(rows: list[dict[str, Any]]) -> TraceRun:
    session_row = rows[0]
    run = TraceRun(
        run_id=str(session_row.get("id") or "openclaw-run"),
        agent="openclaw",
        session_id=str(session_row.get("id") or "openclaw-run"),
    )

    for row in rows:
        row_type = row.get("type")

        if row_type == "session":
            run.add_event(
                TraceEvent(
                    ts=str(row.get("timestamp") or "unknown-ts"),
                    kind="session_start",
                    source="openclaw",
                    data={k: v for k, v in row.items() if k not in OPENCLAW_SESSION_KEYS},
                )
            )
            continue

        if row_type == "model_change":
            run.add_event(
                TraceEvent(
                    ts=str(row.get("timestamp") or "unknown-ts"),
                    kind="model_change",
                    source="openclaw",
                    data={k: v for k, v in row.items() if k not in {"type", "timestamp"}},
                )
            )
            continue

        if row_type == "thinking_level_change":
            run.add_event(
                TraceEvent(
                    ts=str(row.get("timestamp") or "unknown-ts"),
                    kind="thinking_level_change",
                    source="openclaw",
                    data={k: v for k, v in row.items() if k not in {"type", "timestamp"}},
                )
            )
            continue

        if row_type == "custom":
            run.add_event(
                TraceEvent(
                    ts=str(row.get("timestamp") or "unknown-ts"),
                    kind=str(row.get("customType") or "custom"),
                    source="openclaw",
                    data={k: v for k, v in row.items() if k not in {"type", "timestamp", "customType"}},
                )
            )
            continue

        if row_type == "message":
            _ingest_openclaw_message(run, row)
            continue

        run.add_event(
            TraceEvent(
                ts=str(row.get("timestamp") or "unknown-ts"),
                kind=str(row_type or "unknown"),
                source="openclaw",
                data={k: v for k, v in row.items() if k not in {"type", "timestamp"}},
            )
        )

    return run


def _ingest_openclaw_message(run: TraceRun, row: dict[str, Any]) -> None:
    message = row.get("message") or {}
    role = message.get("role")
    ts = str(row.get("timestamp") or message.get("timestamp") or "unknown-ts")
    base_data = {"message_id": row.get("id"), "parent_id": row.get("parentId")}

    if role == "user":
        text = _extract_text_content(message.get("content", []))
        run.add_event(TraceEvent(ts=ts, kind="prompt", source="user", data={**base_data, "message": text, "role": role}))
        return

    if role == "toolResult":
        text = _extract_text_content(message.get("content", []))
        data = {
            **base_data,
            "tool_call_id": message.get("toolCallId"),
            "tool": message.get("toolName"),
            "is_error": message.get("isError"),
            "content": text,
        }
        if message.get("details") is not None:
            data["details"] = message.get("details")
        run.add_event(TraceEvent(ts=ts, kind="tool_result", source=str(message.get("toolName") or "tool"), data=data))
        return

    if role == "assistant":
        for item in message.get("content", []):
            item_type = item.get("type")
            if item_type == "text":
                run.add_event(
                    TraceEvent(
                        ts=ts,
                        kind="assistant_message",
                        source="assistant",
                        data={**base_data, "message": item.get("text", ""), "stop_reason": message.get("stopReason")},
                    )
                )
            elif item_type == "toolCall":
                run.add_event(
                    TraceEvent(
                        ts=ts,
                        kind="tool_call",
                        source="assistant",
                        data={
                            **base_data,
                            "tool_call_id": item.get("id"),
                            "tool": item.get("name"),
                            "arguments": item.get("arguments") or {},
                        },
                    )
                )
            else:
                run.add_event(
                    TraceEvent(
                        ts=ts,
                        kind=f"assistant_{item_type or 'content'}",
                        source="assistant",
                        data={**base_data, "content": item},
                    )
                )
        return

    run.add_event(
        TraceEvent(
            ts=ts,
            kind=str(role or "message"),
            source="openclaw",
            data={**base_data, "message": message},
        )
    )


def _extract_text_content(items: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for item in items:
        if item.get("type") == "text":
            text = item.get("text")
            if text:
                parts.append(str(text))
    return "\n".join(parts)
