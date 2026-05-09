from __future__ import annotations

from typing import Any

from agent_black_box.models import TraceEvent, TraceRun

REDACT_KEYS = {"apikey", "api-key", "api_key", "token", "authorization", "secret", "password"}
REDACTED = "[REDACTED]"


def redact_run(run: TraceRun) -> TraceRun:
    return TraceRun(
        run_id=run.run_id,
        agent=run.agent,
        session_id=run.session_id,
        ingest_warnings=list(run.ingest_warnings),
        events=[
            TraceEvent(
                ts=event.ts,
                kind=event.kind,
                source=event.source,
                data=_redact_value(event.data),
            )
            for event in run.events
        ],
    )


def _redact_value(value: Any, sensitive_context: bool = False) -> Any:
    if isinstance(value, dict):
        return _redact_dict(value, sensitive_context=sensitive_context)
    if isinstance(value, list):
        return [_redact_value(item, sensitive_context=sensitive_context) for item in value]
    if sensitive_context:
        return REDACTED
    return value


def _redact_dict(data: dict[str, Any], sensitive_context: bool = False) -> dict[str, Any]:
    name_value_sensitive = _dict_names_sensitive_value(data)
    redacted: dict[str, Any] = {}

    for key, value in data.items():
        key_sensitive = _is_sensitive_key(key)
        value_sensitive = sensitive_context or key_sensitive or (key == "value" and name_value_sensitive)
        redacted[key] = _redact_value(value, sensitive_context=value_sensitive)

    return redacted


def _dict_names_sensitive_value(data: dict[str, Any]) -> bool:
    name = data.get("name") or data.get("key")
    return isinstance(name, str) and _is_sensitive_key(name)


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower().replace(" ", "_")
    compact = normalized.replace("_", "").replace("-", "")
    return any(marker in normalized or marker in compact for marker in REDACT_KEYS)
