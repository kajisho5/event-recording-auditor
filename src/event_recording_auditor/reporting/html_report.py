"""Human-reviewable report.html (spec section 17).

Self-contained (inline CSS, no external assets) except for links to
evidence files, which are made relative to the report so the whole output
directory can be copied/shared as a unit.
"""

from __future__ import annotations

import os
from html import escape
from pathlib import Path
from typing import Any

from ..timeline import Event, Timeline
from . import i18n
from .timestamps import seconds_to_timestamp as _seconds_to_timestamp

_SEVERITY_COLOR = {
    "high": "#c0392b",
    "medium": "#b7791f",
    "low": "#6b7280",
}

_CSS = """
:root { color-scheme: light; }
body { font-family: -apple-system, "Segoe UI", Helvetica, Arial, sans-serif;
       margin: 0; padding: 24px; background: #f7f7f8; color: #1f2328; }
h1 { margin: 0 0 4px 0; }
.subtitle { color: #57606a; margin-bottom: 24px; }
.summary { display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 24px; }
.card { background: white; border: 1px solid #d0d7de; border-radius: 8px;
        padding: 12px 16px; min-width: 120px; }
.card .value { font-size: 24px; font-weight: 700; }
.card .label { color: #57606a; font-size: 12px; text-transform: uppercase; }
table.timeline { width: 100%; border-collapse: collapse; background: white;
                  border: 1px solid #d0d7de; border-radius: 8px; overflow: hidden; }
table.timeline th, table.timeline td { padding: 8px 12px; text-align: left;
                  border-bottom: 1px solid #eaeef2; vertical-align: top; }
table.timeline th { background: #f0f2f4; font-size: 12px; text-transform: uppercase; }
.badge { display: inline-block; padding: 2px 8px; border-radius: 999px;
         color: white; font-size: 11px; font-weight: 700; text-transform: uppercase; }
.finding { background: white; border: 1px solid #d0d7de; border-radius: 8px;
           padding: 16px; margin-bottom: 16px; }
.finding h3 { margin-top: 0; }
.finding .meta { color: #57606a; font-size: 13px; margin-bottom: 8px; }
.finding ul { margin: 4px 0; }
.interpretation { background: #f6f8fa; border-left: 3px solid #57606a;
                   padding: 8px 12px; margin: 8px 0; font-style: italic; }
.review-required { color: #b7791f; font-weight: 600; }
.limitations { background: #fff8e6; border: 1px solid #f0d98c; border-radius: 8px;
               padding: 12px 16px; margin-top: 24px; }
.evidence a { margin-right: 12px; font-size: 13px; }
"""


def _relative_path(target: str, report_dir: Path) -> str | None:
    try:
        return os.path.relpath(target, report_dir)
    except ValueError:
        return None


def _render_summary_cards(summary: dict[str, Any], lang: str) -> str:
    cards = [
        (i18n.t("total_findings", lang), summary["total_events"]),
        (i18n.severity_label("high", lang), summary["by_severity"]["high"]),
        (i18n.severity_label("medium", lang), summary["by_severity"]["medium"]),
        (i18n.severity_label("low", lang), summary["by_severity"]["low"]),
    ]
    parts = []
    for label, value in cards:
        parts.append(
            f'<div class="card"><div class="value">{value}</div>'
            f'<div class="label">{escape(str(label))}</div></div>'
        )
    return "\n".join(parts)


def _render_timeline_rows(events: list[Event], lang: str) -> str:
    rows = []
    for e in events:
        color = _SEVERITY_COLOR.get(e.severity.value, "#6b7280")
        rows.append(
            "<tr>"
            f'<td>{escape(_seconds_to_timestamp(e.start))}</td>'
            f'<td>{escape(i18n.category_label(e.category.value, lang))}</td>'
            f'<td><span class="badge" style="background:{color}">'
            f'{escape(i18n.severity_label(e.severity.value, lang))}</span></td>'
            f'<td>{escape(i18n.confidence_label(e.confidence.value, lang))}</td>'
            f'<td>{escape(e.type)}</td>'
            f'<td><a href="#finding-{escape(e.id)}">{escape(i18n.t("details", lang))}</a></td>'
            "</tr>"
        )
    return "\n".join(rows)


def _render_finding(e: Event, report_dir: Path, lang: str) -> str:
    color = _SEVERITY_COLOR.get(e.severity.value, "#6b7280")
    observations, interpretation = i18n.translate_event_text(e, lang)
    obs_html = "".join(f"<li>{escape(o)}</li>" for o in observations)
    review = (
        f'<div class="review-required">{escape(i18n.t("human_verification_required", lang))}</div>'
        if e.requires_human_review
        else ""
    )
    evidence_links = []
    for label, path in e.evidence.items():
        if label == "error":
            continue
        rel = _relative_path(path, report_dir)
        if rel:
            evidence_links.append(f'<a href="{escape(rel)}">{escape(label)}</a>')
    evidence_html = (
        f'<div class="evidence">{"".join(evidence_links)}</div>' if evidence_links else ""
    )

    interpretation = interpretation or i18n.t("no_interpretation", lang)

    return f"""
<div class="finding" id="finding-{escape(e.id)}">
  <h3>{escape(_seconds_to_timestamp(e.start))} &ndash; {escape(_seconds_to_timestamp(e.end))}
      <span class="badge" style="background:{color}">{escape(i18n.severity_label(e.severity.value, lang))}</span></h3>
  <div class="meta">{escape(i18n.category_label(e.category.value, lang))} / {escape(e.type)} &middot;
      {escape(i18n.t("col_confidence", lang))}: {escape(i18n.confidence_label(e.confidence.value, lang))} &middot;
      {escape(i18n.t("detector", lang))}: {escape(e.detector)}</div>
  <strong>{escape(i18n.t("observed", lang))}:</strong>
  <ul>{obs_html}</ul>
  <div class="interpretation">{escape(i18n.t("possible_interpretation", lang))}: {escape(interpretation)}</div>
  {review}
  {evidence_html}
</div>
"""


def build_report_html(
    timeline: Timeline,
    media_summary: dict[str, Any],
    report_dir: Path,
    limitations: list[str] | None = None,
    language: str = i18n.DEFAULT_LANGUAGE,
) -> str:
    lang = language if language in i18n.SUPPORTED_LANGUAGES else i18n.DEFAULT_LANGUAGE
    events = timeline.events
    summary = timeline.summary()

    title = escape(media_summary.get("path", i18n.t("unknown_file", lang)))
    duration = media_summary.get("duration")
    duration_str = _seconds_to_timestamp(duration) if duration else i18n.t("unknown_duration", lang)

    limitations_html = ""
    if limitations:
        items = "".join(f"<li>{escape(item)}</li>" for item in limitations)
        limitations_html = (
            f'<div class="limitations"><strong>{escape(i18n.t("limitations", lang))}</strong>'
            f"<ul>{items}</ul></div>"
        )

    findings_html = "".join(_render_finding(e, report_dir, lang) for e in events)

    return f"""<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<title>{escape(i18n.t("title", lang))}</title>
<style>{_CSS}</style>
</head>
<body>
  <h1>{escape(i18n.t("title", lang))}</h1>
  <div class="subtitle">{title} &middot; {escape(i18n.t("duration", lang))} {duration_str}</div>

  <div class="summary">
    {_render_summary_cards(summary, lang)}
  </div>

  <h2>{escape(i18n.t("timeline", lang))}</h2>
  <table class="timeline">
    <thead><tr>
      <th>{escape(i18n.t("col_time", lang))}</th>
      <th>{escape(i18n.t("col_category", lang))}</th>
      <th>{escape(i18n.t("col_severity", lang))}</th>
      <th>{escape(i18n.t("col_confidence", lang))}</th>
      <th>{escape(i18n.t("col_type", lang))}</th>
      <th></th>
    </tr></thead>
    <tbody>
      {_render_timeline_rows(events, lang)}
    </tbody>
  </table>

  <h2>{escape(i18n.t("detailed_findings", lang))}</h2>
  {findings_html or f"<p>{escape(i18n.t('no_findings', lang))}</p>"}

  {limitations_html}
</body>
</html>
"""


def write_html_report(
    timeline: Timeline,
    media_summary: dict[str, Any],
    out_path: str | Path,
    limitations: list[str] | None = None,
    language: str = i18n.DEFAULT_LANGUAGE,
) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    html = build_report_html(timeline, media_summary, out_path.parent, limitations, language)
    out_path.write_text(html)
    return out_path
