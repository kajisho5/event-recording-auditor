"""Human-readable, plain-text report.md.

Complements report.html (spec section 17): the same content, formatted as
Markdown so it's easy to paste into a chat, ticket, or editor, or read
directly in a terminal -- without needing to open a browser.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ..timeline import Event, Timeline
from .timestamps import seconds_to_timestamp as _seconds_to_timestamp


def _relative_path(target: str, report_dir: Path) -> str | None:
    try:
        return os.path.relpath(target, report_dir)
    except ValueError:
        return None


def _timeline_table(events: list[Event]) -> str:
    header = "| Time | Duration | Category | Severity | Confidence | Type |\n"
    header += "|---|---|---|---|---|---|\n"
    rows = []
    for e in events:
        rows.append(
            f"| {_seconds_to_timestamp(e.start)} - {_seconds_to_timestamp(e.end)} "
            f"| {e.duration:.2f}s | {e.category.value} | {e.severity.value} "
            f"| {e.confidence.value} | {e.type} |"
        )
    return header + "\n".join(rows)


def _finding_section(e: Event, report_dir: Path) -> str:
    lines = [
        f"### {_seconds_to_timestamp(e.start)} - {_seconds_to_timestamp(e.end)} "
        f"({e.duration:.2f}s) -- {e.severity.value.upper()} / {e.type}",
        "",
        f"- **Category**: {e.category.value}",
        f"- **Confidence**: {e.confidence.value}",
        f"- **Detector**: {e.detector}",
        "",
        "**Observed:**",
    ]
    for obs in e.observations:
        lines.append(f"- {obs}")
    lines.append("")
    interpretation = e.possible_interpretation or "(insufficient evidence for an interpretation)"
    lines.append(f"**Possible interpretation:** {interpretation}")
    lines.append("")
    lines.append(
        "**Human verification required.**"
        if e.requires_human_review
        else "_Informational entry; human verification not required._"
    )

    evidence_links = []
    for label, path in e.evidence.items():
        if label == "error":
            continue
        rel = _relative_path(path, report_dir)
        if rel:
            evidence_links.append(f"[{label}]({rel})")
    if evidence_links:
        lines.append("")
        lines.append("**Evidence:** " + " · ".join(evidence_links))

    return "\n".join(lines)


def build_report_markdown(
    timeline: Timeline,
    media_summary: dict[str, Any],
    report_dir: Path,
    limitations: list[str] | None = None,
) -> str:
    events = timeline.events
    summary = timeline.summary()

    duration = media_summary.get("duration")
    duration_str = _seconds_to_timestamp(duration) if duration else "unknown"
    path = media_summary.get("path", "(unknown file)")

    lines = [
        "# Event Recording Audit",
        "",
        f"**File:** `{path}`  ",
        f"**Duration:** {duration_str}  ",
        f"**Total findings:** {summary['total_events']} "
        f"(high: {summary['by_severity']['high']}, "
        f"medium: {summary['by_severity']['medium']}, "
        f"low: {summary['by_severity']['low']})",
        "",
        "## Timeline",
        "",
    ]

    if events:
        lines.append(_timeline_table(events))
    else:
        lines.append("No anomaly candidates were detected.")

    lines.append("")
    lines.append("## Detailed findings")
    lines.append("")
    if events:
        for e in events:
            lines.append(_finding_section(e, report_dir))
            lines.append("")
    else:
        lines.append("(none)")

    if limitations:
        lines.append("## Limitations")
        lines.append("")
        for item in limitations:
            lines.append(f"- {item}")
        lines.append("")

    return "\n".join(lines)


def write_markdown_report(
    timeline: Timeline,
    media_summary: dict[str, Any],
    out_path: str | Path,
    limitations: list[str] | None = None,
) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    markdown = build_report_markdown(timeline, media_summary, out_path.parent, limitations)
    out_path.write_text(markdown)
    return out_path
