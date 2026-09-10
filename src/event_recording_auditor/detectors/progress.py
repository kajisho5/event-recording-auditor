"""Tier 2 progression-interruption detector (spec section 5 / 28.7).

Deliberately requires audio inactivity AND visual inactivity AND an
unchanged slide state, all sustained together, before flagging anything.
A presenter speaking normally in front of a static camera on an unchanging
slide must NOT be flagged merely because the slide didn't change -- see
docs/false-positives.md.
"""

from __future__ import annotations

from ..timeline import Category, Confidence, Event, Severity
from .base import Detector
from .context import AnalysisContext


class ProgressionInterruptionDetector(Detector):
    name = "progression_interruption"
    tier = 2
    requires = "video+audio"

    def __init__(
        self,
        min_duration: float = 30.0,
        audio_silence_db: float = -40.0,
        visual_activity_threshold: int = 20,
        bucket: float = 2.0,
    ) -> None:
        self.min_duration = min_duration
        self.audio_silence_db = audio_silence_db
        self.visual_activity_threshold = visual_activity_threshold
        self.bucket = bucket

    def run(self, ctx: AnalysisContext) -> list[Event]:
        if not ctx.media_info.has_video:
            return []

        duration = ctx.media_info.duration
        if duration <= 0:
            return []

        envelope = ctx.level_envelope() if ctx.media_info.has_audio else []
        activity = ctx.visual_activity()
        slide_states = ctx.slide_states()

        n_buckets = int(duration // self.bucket) + 1
        audio_inactive = [self._audio_inactive(envelope, i) for i in range(n_buckets)]
        visual_inactive = [self._visual_inactive(activity, i) for i in range(n_buckets)]
        slide_unchanged = [self._slide_unchanged(slide_states, i) for i in range(n_buckets)]

        has_audio_track = ctx.media_info.has_audio

        events = []
        run_start_bucket = None
        for i in range(n_buckets):
            all_quiet = visual_inactive[i] and slide_unchanged[i] and (
                audio_inactive[i] if has_audio_track else True
            )
            if all_quiet:
                if run_start_bucket is None:
                    run_start_bucket = i
            else:
                if run_start_bucket is not None:
                    events.append(self._maybe_build_event(ctx, run_start_bucket, i, has_audio_track))
                run_start_bucket = None
        if run_start_bucket is not None:
            events.append(
                self._maybe_build_event(ctx, run_start_bucket, n_buckets, has_audio_track)
            )

        return [e for e in events if e is not None]

    def _maybe_build_event(self, ctx, start_bucket, end_bucket, has_audio_track):
        start = start_bucket * self.bucket
        end = end_bucket * self.bucket
        duration = end - start
        if duration < self.min_duration:
            return None

        observations = [
            "No meaningful visual change was detected for the interval.",
            "The slide/presentation state did not change during the interval.",
        ]
        if has_audio_track:
            observations.append("Audio remained near-silent for the interval.")
        else:
            observations.append("No audio track was available to corroborate this.")

        confidence = Confidence.MEDIUM if has_audio_track else Confidence.LOW
        severity = Severity.HIGH if duration >= self.min_duration * 3 else Severity.MEDIUM

        return Event(
            start=start,
            end=end,
            category=Category.PROGRESS,
            type="progression_interruption",
            severity=severity,
            confidence=confidence,
            observations=observations,
            measurements={"duration": duration},
            possible_interpretation=(
                "Possible event progression interruption: no camera motion, no "
                "audio activity, and no slide change were observed together for an "
                "extended period. This could also be an intermission, a technical "
                "pause acknowledged by the room, or a long silent activity (e.g. "
                "audience working on a task) that this recording cannot distinguish."
            ),
            detector=self.name,
            source_files=[ctx.source],
        )

    def _audio_inactive(self, envelope, bucket_index: int) -> bool:
        if not envelope:
            return True
        start = bucket_index * self.bucket
        end = start + self.bucket
        overlapping = [w for w in envelope if w.end > start and w.start < end]
        if not overlapping:
            return True
        return all(w.rms_db <= self.audio_silence_db for w in overlapping)

    def _visual_inactive(self, activity, bucket_index: int) -> bool:
        start = bucket_index * self.bucket
        end = start + self.bucket
        overlapping = [d for t, d in activity if start <= t < end]
        if not overlapping:
            return True
        return max(overlapping) <= self.visual_activity_threshold

    def _slide_unchanged(self, slide_states, bucket_index: int) -> bool:
        start = bucket_index * self.bucket
        end = start + self.bucket
        overlapping_states = {
            s.state_id for s in slide_states if s.end > start and s.start < end
        }
        return len(overlapping_states) <= 1
