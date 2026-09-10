"""Wires detectors together into named analysis profiles (spec section 32).

Each profile is just a list of detector instances; `run_pipeline` runs
them against one shared `AnalysisContext` (so expensive intermediate data
-- the level envelope, the frame-hash sequence -- is computed once) and
collects results into a `Timeline`. A detector raising an exception does
not abort the whole run: it is recorded as a limitation on the report
instead, since a partial audit is still useful and matches the "insufficient
evidence" philosophy better than an all-or-nothing failure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .detectors import (
    AnalysisContext,
    AudioDropoutDetector,
    BlackoutDetector,
    BriefUnexpectedSlideDetector,
    ClippingDetector,
    Detector,
    FeedbackHowlingDetector,
    FreezeDetector,
    ProgressionInterruptionDetector,
    SlideRollbackPatternDetector,
)
from .evidence import extract_evidence_for_timeline
from .timeline import Timeline


def _technical_detectors() -> list[Detector]:
    return [BlackoutDetector(), FreezeDetector(), ClippingDetector()]


def _production_detectors() -> list[Detector]:
    return [FreezeDetector(), ProgressionInterruptionDetector(), AudioDropoutDetector()]


def _presentation_detectors() -> list[Detector]:
    return [SlideRollbackPatternDetector(), BriefUnexpectedSlideDetector()]


def _post_production_detectors() -> list[Detector]:
    # Post-production (source-vs-export) analysis is a separate two-file
    # workflow (see postproduction/compare.py), not a single-file detector.
    return []


PROFILES: dict[str, "callable"] = {
    "technical": _technical_detectors,
    "production": _production_detectors,
    "presentation": _presentation_detectors,
    "post_production": _post_production_detectors,
}


def build_detectors(profile: str, include_feedback_experimental: bool = False) -> list[Detector]:
    if profile == "full":
        detectors: list[Detector] = []
        seen_names: set[str] = set()
        for name in ("technical", "production", "presentation"):
            for det in PROFILES[name]():
                if det.name not in seen_names:
                    detectors.append(det)
                    seen_names.add(det.name)
    elif profile in PROFILES:
        detectors = PROFILES[profile]()
    else:
        raise ValueError(f"Unknown profile {profile!r}. Choose from: full, {', '.join(PROFILES)}")

    if include_feedback_experimental:
        detectors.append(FeedbackHowlingDetector())

    return detectors


@dataclass
class PipelineResult:
    context: AnalysisContext
    timeline: Timeline
    limitations: list[str] = field(default_factory=list)


def run_pipeline(
    source: str,
    profile: str = "full",
    include_feedback_experimental: bool = False,
    evidence_dir: str | Path | None = None,
    min_severity_for_evidence: str = "medium",
) -> PipelineResult:
    ctx = AnalysisContext(source)
    detectors = build_detectors(profile, include_feedback_experimental)

    timeline = Timeline()
    limitations: list[str] = []

    if not ctx.media_info.has_video and not ctx.media_info.has_audio:
        limitations.append(
            f"{source!r} could not be probed as a media file with video or audio "
            "streams; no detectors were run."
        )
        return PipelineResult(context=ctx, timeline=timeline, limitations=limitations)

    for detector in detectors:
        if "video" in detector.requires and not ctx.media_info.has_video:
            limitations.append(
                f"Detector '{detector.name}' skipped: input has no video stream."
            )
            continue
        if detector.requires == "audio" and not ctx.media_info.has_audio:
            limitations.append(
                f"Detector '{detector.name}' skipped: input has no audio stream."
            )
            continue
        try:
            events = detector.run(ctx)
        except Exception as exc:  # noqa: BLE001 - one detector failing shouldn't abort the audit
            limitations.append(f"Detector '{detector.name}' failed: {exc}")
            continue

        timeline.extend(events)
        skipped_reason = getattr(detector, "skipped_reason", None)
        if skipped_reason:
            limitations.append(f"Detector '{detector.name}' skipped: {skipped_reason}")

    if evidence_dir is not None:
        extract_evidence_for_timeline(
            timeline, evidence_dir, min_severity_for_evidence=min_severity_for_evidence
        )

    return PipelineResult(context=ctx, timeline=timeline, limitations=limitations)
