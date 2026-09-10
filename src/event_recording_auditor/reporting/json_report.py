"""Machine-readable report.json (spec section 17)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..timeline import Timeline
from .timestamps import seconds_to_timestamp as _seconds_to_timestamp


def build_report_dict(
    timeline: Timeline,
    media_summary: dict[str, Any],
    limitations: list[str] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    events = []
    for e in timeline.events:
        d = e.to_dict()
        d["start_timestamp"] = _seconds_to_timestamp(e.start)
        d["end_timestamp"] = _seconds_to_timestamp(e.end)
        events.append(d)

    report = {
        "media": media_summary,
        "summary": timeline.summary(),
        "events": events,
        "limitations": limitations or [],
    }
    if extra:
        report.update(extra)
    return report


def write_json_report(
    timeline: Timeline,
    media_summary: dict[str, Any],
    out_path: str | Path,
    limitations: list[str] | None = None,
    extra: dict[str, Any] | None = None,
) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    report = build_report_dict(timeline, media_summary, limitations, extra)
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    return out_path
