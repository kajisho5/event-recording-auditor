"""Command-line entry point.

    event-recording-auditor analyze RECORDING.mp4 --out-dir out/
    event-recording-auditor compare SOURCE.mp4 EXPORT.mp4 --out-dir out/

See SKILL.md for the Agent-facing workflow this wraps.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .batch import run_batch
from .pipeline import PROFILES, run_pipeline
from .postproduction import compare_source_and_export
from .reporting import (
    write_batch_index_html,
    write_batch_index_markdown,
    write_html_report,
    write_json_report,
    write_markdown_report,
)
from .reporting.i18n import SUPPORTED_LANGUAGES


def _media_summary(ctx) -> dict:
    return {
        "path": ctx.source,
        "duration": ctx.media_info.duration,
        "has_video": ctx.media_info.has_video,
        "has_audio": ctx.media_info.has_audio,
        "resolution": ctx.media_info.resolution,
        "frame_rate": ctx.media_info.frame_rate,
    }


def cmd_analyze(args: argparse.Namespace) -> int:
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    evidence_dir = out_dir / "evidence" if not args.no_evidence else None

    result = run_pipeline(
        args.source,
        profile=args.profile,
        include_feedback_experimental=args.experimental_feedback,
        evidence_dir=evidence_dir,
        min_severity_for_evidence=args.min_severity_for_evidence,
    )

    media_summary = _media_summary(result.context)
    json_path = write_json_report(result.timeline, media_summary, out_dir / "report.json", result.limitations)
    html_path = write_html_report(
        result.timeline,
        media_summary,
        out_dir / "report.html",
        result.limitations,
        language=args.lang,
    )
    markdown_path = write_markdown_report(
        result.timeline,
        media_summary,
        out_dir / "report.md",
        result.limitations,
        language=args.lang,
    )

    print(f"Analyzed {args.source}")
    print(f"  {len(result.timeline)} anomaly candidate(s) found")
    print(f"  JSON report: {json_path}")
    print(f"  HTML report: {html_path}")
    print(f"  Markdown report: {markdown_path}")
    for limitation in result.limitations:
        print(f"  Note: {limitation}")
    return 0


def cmd_batch(args: argparse.Namespace) -> int:
    results = run_batch(
        args.sources,
        out_dir=args.out_dir,
        profile=args.profile,
        include_feedback_experimental=args.experimental_feedback,
        no_evidence=args.no_evidence,
        min_severity_for_evidence=args.min_severity_for_evidence,
        lang=args.lang,
        concurrency=args.concurrency,
    )

    out_dir = Path(args.out_dir)
    index_md = write_batch_index_markdown(results, out_dir / "index.md", language=args.lang)
    index_html = write_batch_index_html(results, out_dir / "index.html", language=args.lang)

    ok_count = sum(1 for r in results if r.ok)
    error_count = len(results) - ok_count
    print(f"Processed {len(results)} file(s): {ok_count} ok, {error_count} error(s)")
    for r in results:
        if r.ok:
            print(f"  [ok]    {r.source} -> {r.total_findings} finding(s) ({out_dir / r.slug})")
        else:
            print(f"  [error] {r.source}: {r.error}")
    print(f"Index: {index_md}")
    print(f"Index: {index_html}")
    return 1 if error_count and error_count == len(results) else 0


def cmd_compare(args: argparse.Namespace) -> int:
    delivery_spec = None
    if args.delivery_spec:
        delivery_spec = json.loads(Path(args.delivery_spec).read_text())

    result = compare_source_and_export(
        args.source,
        args.export,
        delivery_spec=delivery_spec,
        max_compare_duration=args.max_compare_duration,
    )

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "comparison.json"
    out_path.write_text(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))

    print(f"Compared source={args.source} export={args.export}")
    print(f"  Conclusion: {result.conclusion.value}")
    for line in result.reasoning:
        print(f"  - {line}")
    print(f"  Report: {out_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="event-recording-auditor")
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze = subparsers.add_parser("analyze", help="Audit a single event recording.")
    analyze.add_argument("source", help="Path to the recording to analyze.")
    analyze.add_argument("--out-dir", default="audit-output", help="Directory for reports/evidence.")
    analyze.add_argument(
        "--profile",
        choices=["full", *PROFILES.keys()],
        default="full",
        help="Which detector set to run (default: full).",
    )
    analyze.add_argument(
        "--experimental-feedback",
        action="store_true",
        help="Also run the experimental feedback/howling detector (requires numpy).",
    )
    analyze.add_argument("--no-evidence", action="store_true", help="Skip evidence extraction.")
    analyze.add_argument(
        "--min-severity-for-evidence",
        choices=["low", "medium", "high"],
        default="medium",
        help="Minimum severity to extract an evidence package for (default: medium).",
    )
    analyze.add_argument(
        "--lang",
        choices=list(SUPPORTED_LANGUAGES),
        default="en",
        help=(
            "Language for report.html/report.md prose (default: en). report.json is "
            "always English -- it's the stable machine-readable format."
        ),
    )
    analyze.set_defaults(func=cmd_analyze)

    batch = subparsers.add_parser(
        "batch",
        help="Audit several independent recordings concurrently (e.g. one file per venue).",
    )
    batch.add_argument("sources", nargs="+", help="Paths to the recordings to analyze.")
    batch.add_argument(
        "--out-dir",
        default="batch-audit",
        help="Directory for the batch index and per-file subdirectories (default: batch-audit).",
    )
    batch.add_argument(
        "--profile",
        choices=["full", *PROFILES.keys()],
        default="full",
        help="Which detector set to run for every file (default: full).",
    )
    batch.add_argument(
        "--experimental-feedback",
        action="store_true",
        help="Also run the experimental feedback/howling detector (requires numpy).",
    )
    batch.add_argument("--no-evidence", action="store_true", help="Skip evidence extraction.")
    batch.add_argument(
        "--min-severity-for-evidence",
        choices=["low", "medium", "high"],
        default="medium",
        help="Minimum severity to extract an evidence package for (default: medium).",
    )
    batch.add_argument(
        "--lang",
        choices=list(SUPPORTED_LANGUAGES),
        default="en",
        help="Language for report prose, same as `analyze --lang` (default: en).",
    )
    batch.add_argument(
        "--concurrency",
        type=int,
        default=None,
        help=(
            "Max files to process at once (default: min(file count, CPU count) -- "
            "each job is CPU-bound on ffmpeg decode, so more than the CPU count just "
            "adds contention)."
        ),
    )
    batch.set_defaults(func=cmd_batch)

    compare = subparsers.add_parser(
        "compare", help="Compare a source recording against an edited/exported file."
    )
    compare.add_argument("source", help="Path to the original camera/source file.")
    compare.add_argument("export", help="Path to the edited/exported delivery file.")
    compare.add_argument("--out-dir", default="audit-output", help="Directory for the comparison report.")
    compare.add_argument(
        "--delivery-spec",
        default=None,
        help="Optional JSON file describing the intended delivery format.",
    )
    compare.add_argument(
        "--max-compare-duration",
        type=float,
        default=60.0,
        help="Seconds of each file to compare for objective quality metrics (default: 60).",
    )
    compare.set_defaults(func=cmd_compare)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
