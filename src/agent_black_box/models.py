from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class TraceEvent:
    ts: str
    kind: str
    source: str
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class TraceRun:
    run_id: str
    agent: str | None = None
    session_id: str | None = None
    events: list[TraceEvent] = field(default_factory=list)
    ingest_warnings: list[str] = field(default_factory=list)

    def add_event(self, event: TraceEvent) -> None:
        self.events.append(event)

    @property
    def event_count(self) -> int:
        return len(self.events)
