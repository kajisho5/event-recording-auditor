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
from . import i18n
from .timestamps import seconds_to_timestamp as _seconds_to_timestamp


def _relative_path(target: str, report_dir: Path) -> str | None:
    try:
        return os.path.relpath(target, report_dir)
    except ValueError:
        return None


def _timeline_table(events: list[Event], lang: str) -> str:
    header = (
        f"| {i18n.t('col_time', lang)} | {i18n.t('col_duration', lang)} "
        f"| {i18n.t('col_category', lang)} | {i18n.t('col_severity', lang)} "
        f"| {i18n.t('col_confidence', lang)} | {i18n.t('col_type', lang)} |\n"
    )
    header += "|---|---|---|---|---|---|\n"
    rows = []
    for e in events:
        rows.append(
            f"| {_seconds_to_timestamp(e.start)} - {_seconds_to_timestamp(e.end)} "
            f"| {e.duration:.2f}s | {i18n.category_label(e.category.value, lang)} "
            f"| {i18n.severity_label(e.severity.value, lang)} "
            f"| {i18n.confidence_label(e.confidence.value, lang)} | {e.type} |"
        )
    return header + "\n".join(rows)


def _finding_section(e: Event, report_dir: Path, lang: str) -> str:
    observations, interpretation = i18n.translate_event_text(e, lang)
    lines = [
        f"### {_seconds_to_timestamp(e.start)} - {_seconds_to_timestamp(e.end)} "
        f"({e.duration:.2f}s) -- {i18n.severity_label(e.severity.value, lang).upper()} / {e.type}",
        "",
        f"- **{i18n.t('col_category', lang)}**: {i18n.category_label(e.category.value, lang)}",
        f"- **{i18n.t('col_confidence', lang)}**: {i18n.confidence_label(e.confidence.value, lang)}",
        f"- **{i18n.t('detector', lang)}**: {e.detector}",
        "",
        f"**{i18n.t('observed', lang)}:**",
    ]
    for obs in observations:
        lines.append(f"- {obs}")
    lines.append("")
    interpretation = interpretation or i18n.t("no_interpretation", lang)
    lines.append(f"**{i18n.t('possible_interpretation', lang)}:** {interpretation}")
    lines.append("")
    lines.append(
        f"**{i18n.t('human_verification_required', lang)}**"
        if e.requires_human_review
        else f"_{i18n.t('informational_entry', lang)}_"
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
        lines.append(f"**{i18n.t('evidence', lang)}:** " + " · ".join(evidence_links))

    return "\n".join(lines)


def build_report_markdown(
    timeline: Timeline,
    media_summary: dict[str, Any],
    report_dir: Path,
    limitations: list[str] | None = None,
    language: str = i18n.DEFAULT_LANGUAGE,
) -> str:
    lang = language if language in i18n.SUPPORTED_LANGUAGES else i18n.DEFAULT_LANGUAGE
    events = timeline.events
    summary = timeline.summary()

    duration = media_summary.get("duration")
    duration_str = _seconds_to_timestamp(duration) if duration else i18n.t("unknown_duration", lang)
    path = media_summary.get("path", i18n.t("unknown_file", lang))

    lines = [
        f"# {i18n.t('title', lang)}",
        "",
        f"**{i18n.t('file', lang)}:** `{path}`  ",
        f"**{i18n.t('duration', lang)}:** {duration_str}  ",
        f"**{i18n.t('total_findings', lang)}:** {summary['total_events']} "
        f"({i18n.severity_label('high', lang)}: {summary['by_severity']['high']}, "
        f"{i18n.severity_label('medium', lang)}: {summary['by_severity']['medium']}, "
        f"{i18n.severity_label('low', lang)}: {summary['by_severity']['low']})",
        "",
        f"## {i18n.t('timeline', lang)}",
        "",
    ]

    if events:
        lines.append(_timeline_table(events, lang))
    else:
        lines.append(i18n.t("no_findings", lang))

    lines.append("")
    lines.append(f"## {i18n.t('detailed_findings', lang)}")
    lines.append("")
    if events:
        for e in events:
            lines.append(_finding_section(e, report_dir, lang))
            lines.append("")
    else:
        lines.append(i18n.t("none", lang))

    if limitations:
        lines.append(f"## {i18n.t('limitations', lang)}")
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
    language: str = i18n.DEFAULT_LANGUAGE,
) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    markdown = build_report_markdown(timeline, media_summary, out_path.parent, limitations, language)
    out_path.write_text(markdown)
    return out_path
