from __future__ import annotations

from collections import Counter
from typing import Any

from agent_black_box.models import TraceRun


PREFERRED_DETAIL_KEYS = [
    "tool",
    "tool_call_id",
    "arguments",
    "command",
    "path",
    "status",
    "is_error",
    "message",
    "content",
    "details",
    "stop_reason",
    "name",
]
COMPACT_HIDE_KEYS = {"tool_call_id"}
COMPACT_SKIP_EVENT_KINDS = {"assistant_thinking", "session_start", "model_change", "thinking_level_change", "model-snapshot"}


def render_timeline(run: TraceRun, compact: bool = False) -> str:
    visible_events = [event for event in run.events if not compact or event.kind not in COMPACT_SKIP_EVENT_KINDS]
    lines = [
        f"run_id: {run.run_id}",
        f"agent: {run.agent or 'unknown'}",
    ]
    if not compact:
        lines.extend([
            f"session_id: {run.session_id or 'unknown'}",
            f"events: {run.event_count}",
        ])
    else:
        lines.extend([
            f"events: {len(visible_events)} shown / {run.event_count} total",
            "view: compact",
        ])
    if run.ingest_warnings:
        lines.append(f"ingest_warnings: {len(run.ingest_warnings)}")
    lines.extend(["", "Timeline", "--------"])

    for idx, event in enumerate(visible_events, start=1):
        detail = _summarize_event_data(event.kind, event.data, compact=compact)
        lines.append(f"{idx:02d}. [{event.ts}] {event.kind} ({event.source}) {detail}".rstrip())

    if compact and len(visible_events) != run.event_count:
        omitted = _omitted_event_summary(run)
        lines.extend(["", f"filtered: {run.event_count - len(visible_events)} event(s) ({omitted})"])

    return "\n".join(lines)


def _omitted_event_summary(run: TraceRun) -> str:
    counts = Counter(event.kind for event in run.events if event.kind in COMPACT_SKIP_EVENT_KINDS)
    parts = [f"{kind}={count}" for kind, count in sorted(counts.items())]
    return ", ".join(parts) if parts else "compact-filtered"


def _summarize_event_data(kind: str, data: dict[str, Any], compact: bool = False) -> str:
    parts = _preferred_parts(kind, data, compact=compact)
    if not parts:
        return ""
    return " | " + ", ".join(parts)


def _preferred_parts(kind: str, data: dict[str, Any], compact: bool = False) -> list[str]:
    if not data:
        return []

    parts: list[str] = []
    for key in PREFERRED_DETAIL_KEYS:
        if compact and key in COMPACT_HIDE_KEYS:
            continue
        value = data.get(key)
        if value is None:
            continue
        rendered = _render_value(kind, key, value, compact=compact)
        if rendered:
            parts.append(f"{key}={rendered}")

    if parts:
        return parts

    first_key = next(iter(data.keys()))
    return [f"{first_key}={_render_value(kind, first_key, data[first_key], compact=compact)}"]


def _render_value(kind: str, key: str, value: Any, compact: bool = False) -> str:
    if isinstance(value, dict):
        if key == "arguments":
            preferred = []
            for subkey in ["command", "path", "action", "query", "messageId", "to"]:
                if subkey in value:
                    preferred.append(f"{subkey}={_clip(str(value[subkey]), 64 if compact else 140)}")
            if preferred:
                return "{" + ", ".join(preferred) + "}"
            compact_text = ", ".join(f"{k}={_clip(str(v), 48 if compact else 120)}" for k, v in sorted(value.items())[:3])
            return "{" + compact_text + "}"
        if key == "details":
            preferred = []
            for subkey in ["exitCode", "status", "timedOut", "durationMs", "error", "count", "ok"]:
                if subkey in value:
                    preferred.append(f"{subkey}={value[subkey]}")
            if preferred:
                return "{" + ", ".join(preferred) + "}"
            if "jobs" in value:
                return f"{{jobs=[{len(value['jobs'])} jobs]}}"
            if "sessions" in value:
                return f"{{sessions=[{len(value['sessions'])} sessions]}}"
            if "message" in value and isinstance(value["message"], dict):
                msg = value["message"]
                msg_id = msg.get("id")
                channel_id = msg.get("channel_id")
                content = _clip(str(msg.get("content", "")), 64 if compact else 160)
                parts = []
                if msg_id:
                    parts.append(f"message.id={msg_id}")
                if channel_id:
                    parts.append(f"channel_id={channel_id}")
                if content:
                    parts.append(f"content={content}")
                return "{" + ", ".join(parts) + "}"
            compact_text = ", ".join(f"{k}={_clip(str(v), 48 if compact else 120)}" for k, v in sorted(value.items())[:3])
            return "{" + compact_text + "}"
        if key == "content" and kind == "assistant_thinking":
            thinking = value.get("thinking") if isinstance(value, dict) else None
            return _clip(str(thinking or "thinking"), 96 if compact else 240)
        compact_text = ", ".join(f"{k}={_clip(str(v), 48 if compact else 120)}" for k, v in sorted(value.items())[:3])
        return "{" + compact_text + "}"

    if isinstance(value, list):
        return f"[{len(value)} items]"

    text = str(value).replace("\n", "\\n")
    return _clip(text, 120 if compact else 320)


def _clip(text: str, max_len: int) -> str:
    if len(text) > max_len:
        return text[: max_len - 3] + "..."
    return text
