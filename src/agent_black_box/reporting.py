from __future__ import annotations

from collections import Counter
from typing import Any

from agent_black_box.models import TraceRun
from agent_black_box.timeline import COMPACT_SKIP_EVENT_KINDS, _render_value


IMPORTANT_KINDS = {
    "failure",
    "warning",
    "command",
    "tool_call",
    "tool_result",
    "file_write",
    "completion",
    "assistant_message",
    "prompt",
}


def render_incident_summary(run: TraceRun, compact: bool = False) -> str:
    counts = Counter(event.kind for event in run.events)
    visible_key_events = [event for event in run.events if event.kind in IMPORTANT_KINDS]
    lines = [
        f"Incident Summary: {run.run_id}",
        "===============================",
        "",
        f"agent: {run.agent or 'unknown'}",
        f"session: {run.session_id or 'unknown'}",
        f"events: {run.event_count}",
    ]
    if run.ingest_warnings:
        lines.append(f"ingest_warnings: {len(run.ingest_warnings)}")
    if compact:
        filtered_counts = Counter(event.kind for event in run.events if event.kind in COMPACT_SKIP_EVENT_KINDS)
        lines.extend([
            f"key events: {len(visible_key_events)}",
            f"filtered events: {sum(filtered_counts.values())}",
        ])
        if filtered_counts:
            detail = ", ".join(f"{kind}={count}" for kind, count in sorted(filtered_counts.items()))
            lines.append(f"filtered detail: {detail}")
    if run.ingest_warnings:
        lines.extend(["", "Ingest Warnings", "---------------"])
        lines.extend(f"- {warning}" for warning in run.ingest_warnings)
    lines.extend(["", "Event Counts", "------------"])

    event_count_items = sorted((counts.items() if not compact else ((kind, count) for kind, count in counts.items() if kind not in COMPACT_SKIP_EVENT_KINDS)))
    for kind, count in event_count_items:
        lines.append(f"- {kind}: {count}")

    lines.extend(["", "Key Events", "----------"])

    for event in visible_key_events:
        lines.append(f"- [{event.ts}] {event.kind} ({event.source}) {_event_detail(event.kind, event.data, compact=compact)}".rstrip())

    return "\n".join(lines)


def _event_detail(kind: str, data: dict[str, Any], compact: bool = False) -> str:
    if not data:
        return ""
    parts = []
    for key in ["tool", "tool_call_id", "arguments", "status", "is_error", "message", "content", "details", "command", "path", "name"]:
        if compact and key == "tool_call_id":
            continue
        value = data.get(key)
        if value is not None:
            parts.append(f"{key}={_render_value(kind, key, value, compact=compact)}")
    if not parts:
        compact_text = ", ".join(f"{key}={_render_value(kind, key, value, compact=compact)}" for key, value in list(sorted(data.items()))[:3])
        return " | " + compact_text if compact_text else ""
    return " | " + ", ".join(parts)
