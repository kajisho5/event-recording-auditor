"""Top-level summary (index.md / index.html) for a batch run (batch.py).

One row per input file/venue: status, duration, finding counts by
severity, and a link into that venue's own report.md/report.html.
"""

from __future__ import annotations

from html import escape
from pathlib import Path
from typing import TYPE_CHECKING

from . import i18n
from .timestamps import seconds_to_timestamp

if TYPE_CHECKING:
    from ..batch import BatchJobResult


def _duration_str(result: "BatchJobResult", lang: str) -> str:
    if result.duration is None:
        return i18n.t("unknown_duration", lang)
    return seconds_to_timestamp(result.duration)


def build_batch_index_markdown(
    results: list["BatchJobResult"], out_dir: Path, language: str = i18n.DEFAULT_LANGUAGE
) -> str:
    lang = language if language in i18n.SUPPORTED_LANGUAGES else i18n.DEFAULT_LANGUAGE

    lines = [
        f"# {i18n.t('batch_title', lang)}",
        "",
        f"**{i18n.t('total_venues', lang)}:** {len(results)}",
        "",
        f"| {i18n.t('col_venue', lang)} | {i18n.t('col_status', lang)} "
        f"| {i18n.t('duration', lang)} | {i18n.t('total_findings', lang)} "
        f"| {i18n.severity_label('high', lang)} | {i18n.severity_label('medium', lang)} "
        f"| {i18n.severity_label('low', lang)} | {i18n.t('col_report', lang)} |",
        "|---|---|---|---|---|---|---|---|",
    ]

    for r in results:
        if r.ok:
            status = i18n.t("status_ok", lang)
            findings = str(r.total_findings)
            high = str(r.by_severity.get("high", 0))
            medium = str(r.by_severity.get("medium", 0))
            low = str(r.by_severity.get("low", 0))
            report_link = f"[report.md]({r.slug}/report.md)"
        else:
            status = f"{i18n.t('status_error', lang)}: {r.error}"
            findings = high = medium = low = "-"
            report_link = "-"
        lines.append(
            f"| `{r.source}` | {status} | {_duration_str(r, lang)} | {findings} "
            f"| {high} | {medium} | {low} | {report_link} |"
        )

    return "\n".join(lines) + "\n"


def write_batch_index_markdown(
    results: list["BatchJobResult"], out_path: str | Path, language: str = i18n.DEFAULT_LANGUAGE
) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(build_batch_index_markdown(results, out_path.parent, language))
    return out_path


_CSS = """
:root { color-scheme: light; }
body { font-family: -apple-system, "Segoe UI", Helvetica, Arial, sans-serif;
       margin: 0; padding: 24px; background: #f7f7f8; color: #1f2328; }
h1 { margin: 0 0 16px 0; }
table { width: 100%; border-collapse: collapse; background: white;
        border: 1px solid #d0d7de; border-radius: 8px; overflow: hidden; }
th, td { padding: 8px 12px; text-align: left; border-bottom: 1px solid #eaeef2; }
th { background: #f0f2f4; font-size: 12px; text-transform: uppercase; }
.status-ok { color: #1a7f37; font-weight: 600; }
.status-error { color: #c0392b; font-weight: 600; }
"""


def build_batch_index_html(
    results: list["BatchJobResult"], out_dir: Path, language: str = i18n.DEFAULT_LANGUAGE
) -> str:
    lang = language if language in i18n.SUPPORTED_LANGUAGES else i18n.DEFAULT_LANGUAGE

    rows = []
    for r in results:
        if r.ok:
            status_html = f'<span class="status-ok">{escape(i18n.t("status_ok", lang))}</span>'
            findings = str(r.total_findings)
            high = str(r.by_severity.get("high", 0))
            medium = str(r.by_severity.get("medium", 0))
            low = str(r.by_severity.get("low", 0))
            report_link = f'<a href="{escape(r.slug)}/report.html">report.html</a>'
        else:
            status_html = (
                f'<span class="status-error">{escape(i18n.t("status_error", lang))}: '
                f'{escape(r.error or "")}</span>'
            )
            findings = high = medium = low = "-"
            report_link = "-"
        rows.append(
            "<tr>"
            f"<td>{escape(r.source)}</td>"
            f"<td>{status_html}</td>"
            f"<td>{escape(_duration_str(r, lang))}</td>"
            f"<td>{findings}</td>"
            f"<td>{high}</td><td>{medium}</td><td>{low}</td>"
            f"<td>{report_link}</td>"
            "</tr>"
        )

    return f"""<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<title>{escape(i18n.t("batch_title", lang))}</title>
<style>{_CSS}</style>
</head>
<body>
  <h1>{escape(i18n.t("batch_title", lang))}</h1>
  <p><strong>{escape(i18n.t("total_venues", lang))}:</strong> {len(results)}</p>
  <table>
    <thead><tr>
      <th>{escape(i18n.t("col_venue", lang))}</th>
      <th>{escape(i18n.t("col_status", lang))}</th>
      <th>{escape(i18n.t("duration", lang))}</th>
      <th>{escape(i18n.t("total_findings", lang))}</th>
      <th>{escape(i18n.severity_label("high", lang))}</th>
      <th>{escape(i18n.severity_label("medium", lang))}</th>
      <th>{escape(i18n.severity_label("low", lang))}</th>
      <th>{escape(i18n.t("col_report", lang))}</th>
    </tr></thead>
    <tbody>
      {"".join(rows)}
    </tbody>
  </table>
</body>
</html>
"""


def write_batch_index_html(
    results: list["BatchJobResult"], out_path: str | Path, language: str = i18n.DEFAULT_LANGUAGE
) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(build_batch_index_html(results, out_path.parent, language))
    return out_path
