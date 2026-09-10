"""Build a per-incident evidence package (spec section 30).

    incident-0007/
        metadata.json
        before.jpg
        event.jpg
        after.jpg
        evidence.mp4
        explanation.txt

Everything here reads from the original file and writes only to `out_dir`
-- the source recording is never modified (requirement: never silently
modify or overwrite the original recording).
"""

from __future__ import annotations

import json
from pathlib import Path

from ..media.extraction import extract_clip, extract_frame
from ..timeline import Event, Timeline

_FRAME_CONTEXT_OFFSET = 1.0  # seconds before/after the event for before/after stills


def build_evidence_package(
    event: Event,
    out_dir: str | Path,
    index: int,
    include_clip: bool = True,
) -> dict[str, str]:
    """Extract frames/clip/explanation for one event into `out_dir/incident-NNNN/`.

    Returns the relative-path evidence dict that gets attached to the
    event (and written into the JSON/HTML reports).
    """
    incident_dir = Path(out_dir) / f"incident-{index:04d}"
    incident_dir.mkdir(parents=True, exist_ok=True)
    source = event.source_files[0] if event.source_files else None
    if source is None:
        raise ValueError(f"Event {event.id} has no source_files to extract evidence from")

    paths: dict[str, str] = {}

    before_time = max(event.start - _FRAME_CONTEXT_OFFSET, 0.0)
    event_time = event.start
    after_time = event.end + _FRAME_CONTEXT_OFFSET

    extract_frame(source, before_time, incident_dir / "before.jpg")
    paths["before_frame"] = str((incident_dir / "before.jpg").resolve())

    extract_frame(source, event_time, incident_dir / "event.jpg")
    paths["event_frame"] = str((incident_dir / "event.jpg").resolve())

    extract_frame(source, after_time, incident_dir / "after.jpg")
    paths["after_frame"] = str((incident_dir / "after.jpg").resolve())

    if include_clip:
        extract_clip(source, event.start, event.end, incident_dir / "evidence.mp4")
        paths["clip"] = str((incident_dir / "evidence.mp4").resolve())

    metadata_path = incident_dir / "metadata.json"
    metadata_path.write_text(json.dumps(event.to_dict(), indent=2, ensure_ascii=False))
    paths["metadata"] = str(metadata_path.resolve())

    explanation_path = incident_dir / "explanation.txt"
    explanation_path.write_text(_render_explanation(event))
    paths["explanation"] = str(explanation_path.resolve())

    return paths


def _render_explanation(event: Event) -> str:
    lines = [
        f"Event: {event.type} ({event.category.value})",
        f"Time: {event.start:.2f}s - {event.end:.2f}s ({event.duration:.2f}s)",
        f"Severity: {event.severity.value}   Confidence: {event.confidence.value}",
        "",
        "Observed:",
    ]
    for obs in event.observations:
        lines.append(f"  - {obs}")
    lines.append("")
    lines.append("Possible interpretation:")
    lines.append(f"  {event.possible_interpretation or '(none stated)'}")
    lines.append("")
    lines.append(
        "Human verification required."
        if event.requires_human_review
        else "Informational entry; human verification not required."
    )
    return "\n".join(lines) + "\n"


def extract_evidence_for_timeline(
    timeline: Timeline,
    out_dir: str | Path,
    min_severity_for_evidence: str = "medium",
    include_clip: bool = True,
) -> None:
    """Populate `event.evidence` for every qualifying event in `timeline`.

    Mutates the Event objects in place (adds evidence paths) rather than
    returning a new structure, since evidence is an enrichment of an
    existing finding, not a separate artifact.
    """
    severity_rank = {"low": 0, "medium": 1, "high": 2}
    threshold = severity_rank[min_severity_for_evidence]

    for index, event in enumerate(timeline.events, start=1):
        if severity_rank[event.severity.value] < threshold:
            continue
        if not event.source_files:
            continue
        try:
            event.evidence = build_evidence_package(event, out_dir, index, include_clip=include_clip)
        except Exception as exc:  # noqa: BLE001 - evidence extraction is best-effort
            event.evidence = {"error": str(exc)}
