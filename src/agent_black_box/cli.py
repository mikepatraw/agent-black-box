from __future__ import annotations

import argparse
from pathlib import Path

from agent_black_box.adapters import parse_trace
from agent_black_box.banner import render_banner
from agent_black_box.diffing import diff_runs
from agent_black_box.filtering import filter_run
from agent_black_box.html_report import render_html_report
from agent_black_box.parser import TraceParseError
from agent_black_box.redaction import redact_run
from agent_black_box.reporting import render_incident_summary
from agent_black_box.timeline import render_timeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agent-black-box")
    sub = parser.add_subparsers(dest="command", required=True)

    timeline_cmd = sub.add_parser("timeline", help="Render a trace timeline from a trace file")
    timeline_cmd.add_argument("trace", help="Path to trace file")
    timeline_cmd.add_argument("--format", default="jsonl", choices=["jsonl", "openclaw-jsonl"], help="Trace source format")
    timeline_cmd.add_argument("--kind", action="append", dest="kinds", help="Filter to specific event kind, repeatable")
    timeline_cmd.add_argument("--redact", action="store_true", help="Redact common secret fields")
    timeline_cmd.add_argument("--strict", action="store_true", help="Fail on malformed JSONL rows instead of skipping them")
    timeline_cmd.add_argument("--compact", action="store_true", help="Reserved for compact rendering behavior on noisy real traces")
    timeline_cmd.add_argument("--banner", action="store_true", help="Render demo banner before output")
    timeline_cmd.add_argument("--output", help="Write output to a file")

    diff_cmd = sub.add_parser("diff", help="Compare two trace files")
    diff_cmd.add_argument("left", help="Path to the first trace file")
    diff_cmd.add_argument("right", help="Path to the second trace file")
    diff_cmd.add_argument("--format", default="jsonl", choices=["jsonl", "openclaw-jsonl"], help="Trace source format for both files")
    diff_cmd.add_argument("--strict", action="store_true", help="Fail on malformed JSONL rows instead of skipping them")
    diff_cmd.add_argument("--compact", action="store_true", help="Enable compact diff behavior on noisy real traces")
    diff_cmd.add_argument("--focus", action="store_true", help="Render a focused diff summary instead of raw event-by-event output")
    diff_cmd.add_argument("--banner", action="store_true", help="Render demo banner before output")
    diff_cmd.add_argument("--output", help="Write output to a file")

    summary_cmd = sub.add_parser("summary", help="Export an incident-style summary from a trace file")
    summary_cmd.add_argument("trace", help="Path to trace file")
    summary_cmd.add_argument("--format", default="jsonl", choices=["jsonl", "openclaw-jsonl"], help="Trace source format")
    summary_cmd.add_argument("--kind", action="append", dest="kinds", help="Filter to specific event kind, repeatable")
    summary_cmd.add_argument("--redact", action="store_true", help="Redact common secret fields")
    summary_cmd.add_argument("--strict", action="store_true", help="Fail on malformed JSONL rows instead of skipping them")
    summary_cmd.add_argument("--compact", action="store_true", help="Reserved for compact rendering behavior on noisy real traces")
    summary_cmd.add_argument("--banner", action="store_true", help="Render demo banner before output")
    summary_cmd.add_argument("--output", help="Write output to a file")

    report_cmd = sub.add_parser("report", help="Generate a static HTML report from one or two trace files")
    report_cmd.add_argument("trace", help="Path to primary trace file")
    report_cmd.add_argument("compare", nargs="?", help="Optional comparison trace for focused diff")
    report_cmd.add_argument("--format", default="jsonl", choices=["jsonl", "openclaw-jsonl"], help="Trace source format")
    report_cmd.add_argument("--redact", action="store_true", help="Redact common secret fields")
    report_cmd.add_argument("--strict", action="store_true", help="Fail on malformed JSONL rows instead of skipping them")
    report_cmd.add_argument("--compact", action="store_true", help="Use compact rendering for the report sections")
    report_cmd.add_argument("--output", required=True, help="Write HTML report to a file")
    report_cmd.add_argument("--title", help="Override HTML report title")
    report_cmd.add_argument("--subtitle", help="Override HTML report subtitle")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return _run_command(args, parser)
    except TraceParseError as exc:
        parser.error(str(exc))
    return 2


def _run_command(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    if args.command == "timeline":
        run = parse_trace(args.trace, source_format=args.format, strict=args.strict)
        run = filter_run(run, args.kinds)
        if args.redact:
            run = redact_run(run)
        output = _maybe_banner(render_timeline(run, compact=args.compact), args.banner)
        _emit(output, args.output)
        return 0

    if args.command == "diff":
        left = parse_trace(args.left, source_format=args.format, strict=args.strict)
        right = parse_trace(args.right, source_format=args.format, strict=args.strict)
        output = _maybe_banner(diff_runs(left, right, compact=args.compact, focus=args.focus), args.banner)
        _emit(output, args.output)
        return 0

    if args.command == "summary":
        run = parse_trace(args.trace, source_format=args.format, strict=args.strict)
        run = filter_run(run, args.kinds)
        if args.redact:
            run = redact_run(run)
        output = _maybe_banner(render_incident_summary(run, compact=args.compact), args.banner)
        _emit(output, args.output)
        return 0

    if args.command == "report":
        run = parse_trace(args.trace, source_format=args.format, strict=args.strict)
        if args.redact:
            run = redact_run(run)
        compare_run = parse_trace(args.compare, source_format=args.format, strict=args.strict) if args.compare else None
        if compare_run and args.redact:
            compare_run = redact_run(compare_run)

        timeline = render_timeline(run, compact=args.compact)
        summary = render_incident_summary(run, compact=args.compact)
        diff = diff_runs(run, compare_run, compact=args.compact, focus=True) if compare_run else "No comparison run provided."
        title = args.title or f"Agent Black Box Report · {run.run_id}"
        subtitle = args.subtitle or "Static black-box report for a real agent run, designed for inspection, sharing, and demo readability."
        output = render_html_report(title=title, subtitle=subtitle, timeline=timeline, summary=summary, diff=diff, run=run, compare_run=compare_run)
        _emit(output, args.output)
        return 0

    parser.error("unknown command")
    return 2


def _maybe_banner(text: str, enabled: bool) -> str:
    if not enabled:
        return text
    return render_banner() + "\n" + text


def _emit(text: str, output_path: str | None) -> None:
    if output_path:
        Path(output_path).write_text(text + "\n")
        print(f"wrote {output_path}")
        return
    print(text)


if __name__ == "__main__":
    raise SystemExit(main())
