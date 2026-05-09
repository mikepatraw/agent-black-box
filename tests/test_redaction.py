from agent_black_box.models import TraceEvent, TraceRun
from agent_black_box.redaction import redact_run


def test_redact_run_recurses_into_nested_payloads_without_mutating_original():
    run = TraceRun(
        run_id="run-1",
        agent="demo",
        session_id="session-1",
        events=[
            TraceEvent(
                ts="1",
                kind="tool_call",
                source="assistant",
                data={
                    "arguments": {
                        "Authorization": "Bearer abc123",
                        "headers": [{"x-api-key": "nested-key"}],
                    },
                    "details": [{"secret": "nested-secret"}, {"safe": "keep-me"}],
                    "token": "top-level-token",
                },
            )
        ],
    )

    redacted = redact_run(run)

    assert redacted is not run
    assert redacted.events[0] is not run.events[0]
    assert redacted.events[0].data["token"] == "[REDACTED]"
    assert redacted.events[0].data["arguments"]["Authorization"] == "[REDACTED]"
    assert redacted.events[0].data["arguments"]["headers"][0]["x-api-key"] == "[REDACTED]"
    assert redacted.events[0].data["details"][0]["secret"] == "[REDACTED]"
    assert redacted.events[0].data["details"][1]["safe"] == "keep-me"

    assert run.events[0].data["token"] == "top-level-token"
    assert run.events[0].data["arguments"]["Authorization"] == "Bearer abc123"
    assert run.events[0].data["arguments"]["headers"][0]["x-api-key"] == "nested-key"


def test_redact_run_redacts_auth_like_values_in_lists():
    run = TraceRun(
        run_id="run-2",
        events=[
            TraceEvent(
                ts="1",
                kind="tool_result",
                source="http",
                data={
                    "response": [
                        {"name": "OPENAI_API_KEY", "value": "sk-demo"},
                        {"name": "normal", "value": "visible"},
                    ]
                },
            )
        ],
    )

    redacted = redact_run(run)

    assert redacted.events[0].data["response"][0]["value"] == "[REDACTED]"
    assert redacted.events[0].data["response"][1]["value"] == "visible"
