"""Tier 1 video detectors: blackout and freeze, wrapped as Event producers.

Both delegate the actual measurement entirely to ffmpeg's blackdetect /
freezedetect filters (see src/event_recording_auditor/video/). This module
only adds severity/confidence judgment and, for freeze, correlates against
concurrent audio activity to reduce the "normal static camera shot"
false-positive class called out in docs/false-positives.md.
"""

from __future__ import annotations

from ..timeline import Category, Confidence, Event, Severity
from ..video.blackdetect import detect_black
from ..video.freezedetect import detect_freeze
from .base import Detector
from .context import AnalysisContext


class BlackoutDetector(Detector):
    name = "blackout"
    tier = 1
    requires = "video"

    def __init__(
        self,
        min_duration: float = 0.10,
        high_severity_duration: float = 2.0,
        medium_severity_duration: float = 0.5,
    ) -> None:
        self.min_duration = min_duration
        self.high_severity_duration = high_severity_duration
        self.medium_severity_duration = medium_severity_duration

    def run(self, ctx: AnalysisContext) -> list[Event]:
        if not ctx.media_info.has_video:
            return []
        segments = detect_black(ctx.source, min_duration=self.min_duration)
        events = []
        for seg in segments:
            if seg.duration >= self.high_severity_duration:
                severity = Severity.HIGH
            elif seg.duration >= self.medium_severity_duration:
                severity = Severity.MEDIUM
            else:
                severity = Severity.LOW
            events.append(
                Event(
                    start=seg.start,
                    end=seg.end,
                    category=Category.VIDEO,
                    type="blackout",
                    severity=severity,
                    confidence=Confidence.HIGH,
                    observations=[f"Video was measured as fully black for {seg.duration:.2f}s."],
                    measurements={"duration": seg.duration},
                    possible_interpretation=(
                        "Possible blackout (signal loss, source cut to black "
                        "unexpectedly) or an intentional black transition. "
                        "The recording alone does not establish intent."
                    ),
                    detector=self.name,
                    source_files=[ctx.source],
                )
            )
        return events


class FreezeDetector(Detector):
    name = "freeze"
    tier = 1
    requires = "video (audio improves confidence)"

    def __init__(
        self,
        min_duration: float = 2.0,
        high_severity_duration: float = 6.0,
        audio_silence_floor_db: float = -40.0,
    ) -> None:
        self.min_duration = min_duration
        self.high_severity_duration = high_severity_duration
        self.audio_silence_floor_db = audio_silence_floor_db

    def run(self, ctx: AnalysisContext) -> list[Event]:
        if not ctx.media_info.has_video:
            return []
        segments = detect_freeze(ctx.source, min_duration=self.min_duration)
        if not segments:
            return []

        envelope = ctx.level_envelope() if ctx.media_info.has_audio else []

        events = []
        for seg in segments:
            audio_active_during = self._audio_active_during(
                envelope, seg.start, seg.end, self.audio_silence_floor_db
            )

            observations = [f"Video showed no measurable change for {seg.duration:.2f}s."]
            if envelope:
                if audio_active_during:
                    observations.append("Audio remained active during this interval.")
                else:
                    observations.append("Audio was near-silent during this interval.")

            if not envelope:
                # No audio track to correlate against -- judge on duration alone.
                severity = Severity.HIGH if seg.duration >= self.high_severity_duration else Severity.MEDIUM
                confidence = Confidence.MEDIUM
                interpretation = (
                    "Possible freeze / signal stall, or a genuinely static shot. "
                    "No audio track was available to help distinguish these."
                )
            elif audio_active_during:
                # Classic false-positive case: presenter talking over a static shot.
                severity = Severity.LOW
                confidence = Confidence.LOW
                interpretation = (
                    "Likely a normal static camera shot: audio activity continued "
                    "throughout, which is inconsistent with a technical freeze."
                )
            else:
                severity = Severity.HIGH if seg.duration >= self.high_severity_duration else Severity.MEDIUM
                confidence = (
                    Confidence.MEDIUM if seg.duration < self.high_severity_duration else Confidence.HIGH
                )
                interpretation = (
                    "Possible video freeze / signal stall: no visual change and no "
                    "audio activity for a sustained period."
                )

            events.append(
                Event(
                    start=seg.start,
                    end=seg.end,
                    category=Category.VIDEO,
                    type="freeze",
                    severity=severity,
                    confidence=confidence,
                    observations=observations,
                    measurements={
                        "duration": seg.duration,
                        "audio_active_during": audio_active_during,
                    },
                    possible_interpretation=interpretation,
                    detector=self.name,
                    source_files=[ctx.source],
                )
            )
        return events

    @staticmethod
    def _audio_active_during(envelope, start: float, end: float, floor_db: float = -40.0) -> bool:
        overlapping = [w for w in envelope if w.end > start and w.start < end]
        if not overlapping:
            return False
        return any(w.rms_db > floor_db for w in overlapping)
