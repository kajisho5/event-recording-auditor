"""Tier 1/2 audio detectors: clipping (Tier 1) and context-aware dropout (Tier 2).

`AudioDropoutDetector` is deliberately not just "report every silence".
Per docs/false-positives.md, a silence between speakers, during Q&A, or a
long deliberate pause is normal and must not be flagged. Instead it looks
for silence that *interrupts* clearly active audio on both sides and is
short enough to be inconsistent with an intentional pause -- i.e. audio
that looks like it dropped out mid-stream rather than paused.
"""

from __future__ import annotations

from ..audio.clipping import detect_clipping
from ..audio.levels import ChannelLevelWindow, LevelWindow
from ..timeline import Category, Confidence, Event, Severity
from .base import Detector
from .context import AnalysisContext


class ClippingDetector(Detector):
    name = "clipping"
    tier = 1
    requires = "audio"

    def __init__(
        self,
        peak_threshold_db: float = -1.0,
        flat_factor_threshold: float = 0.5,
        min_duration: float = 0.2,
        high_severity_duration: float = 3.0,
    ) -> None:
        self.peak_threshold_db = peak_threshold_db
        self.flat_factor_threshold = flat_factor_threshold
        self.min_duration = min_duration
        self.high_severity_duration = high_severity_duration

    def run(self, ctx: AnalysisContext) -> list[Event]:
        if not ctx.media_info.has_audio:
            return []
        segments = detect_clipping(
            ctx.source,
            peak_threshold_db=self.peak_threshold_db,
            flat_factor_threshold=self.flat_factor_threshold,
            min_duration=self.min_duration,
            envelope=ctx.level_envelope(),
        )
        events = []
        for seg in segments:
            severity = Severity.HIGH if seg.duration >= self.high_severity_duration else Severity.MEDIUM
            events.append(
                Event(
                    start=seg.start,
                    end=seg.end,
                    category=Category.AUDIO,
                    type="clipping",
                    severity=severity,
                    confidence=Confidence.HIGH,
                    observations=[
                        f"Audio peak level reached {seg.max_peak_db:.2f} dBFS with a "
                        f"flat-top waveform factor of {seg.max_flat_factor:.1f} for "
                        f"{seg.duration:.2f}s.",
                    ],
                    measurements={
                        "duration": seg.duration,
                        "max_peak_db": seg.max_peak_db,
                        "max_flat_factor": seg.max_flat_factor,
                    },
                    possible_interpretation=(
                        "Possible audio clipping (input gain too high, or a mixer/encoder overload)."
                    ),
                    detector=self.name,
                    source_files=[ctx.source],
                )
            )
        return events


class AudioDropoutDetector(Detector):
    name = "audio_dropout"
    tier = 2
    requires = "audio"

    def __init__(
        self,
        active_db: float = -35.0,
        silence_db: float = -45.0,
        min_dropout_duration: float = 0.4,
        max_dropout_duration: float = 6.0,
        context_window: float = 2.0,
    ) -> None:
        self.active_db = active_db
        self.silence_db = silence_db
        self.min_dropout_duration = min_dropout_duration
        self.max_dropout_duration = max_dropout_duration
        self.context_window = context_window

    def run(self, ctx: AnalysisContext) -> list[Event]:
        if not ctx.media_info.has_audio:
            return []
        envelope = ctx.level_envelope()
        if not envelope:
            return []

        events: list[Event] = []
        i = 0
        n = len(envelope)
        while i < n:
            if envelope[i].rms_db > self.silence_db:
                i += 1
                continue
            # start of a candidate quiet run
            j = i
            while j < n and envelope[j].rms_db <= self.silence_db:
                j += 1
            run = envelope[i:j]
            duration = run[-1].end - run[0].start

            if self.min_dropout_duration <= duration <= self.max_dropout_duration:
                before_active = self._active_before(envelope, i)
                after_active = self._active_after(envelope, j)
                if before_active and after_active:
                    events.append(self._build_event(ctx, run, before_active, after_active))
            i = j

        return events

    def _active_before(self, envelope: list[LevelWindow], index: int) -> bool:
        window_start_time = envelope[index].start - self.context_window
        context = [w for w in envelope[:index] if w.start >= window_start_time]
        return bool(context) and all(w.rms_db > self.active_db for w in context)

    def _active_after(self, envelope: list[LevelWindow], index: int) -> bool:
        if index >= len(envelope):
            return False
        window_end_time = envelope[index].start + self.context_window
        context = [w for w in envelope[index:] if w.start < window_end_time]
        return bool(context) and all(w.rms_db > self.active_db for w in context)

    def _build_event(self, ctx: AnalysisContext, run, before_active, after_active) -> Event:
        duration = run[-1].end - run[0].start
        severity = Severity.HIGH if duration >= 2.0 else Severity.MEDIUM
        return Event(
            start=run[0].start,
            end=run[-1].end,
            category=Category.AUDIO,
            type="possible_audio_dropout",
            severity=severity,
            confidence=Confidence.MEDIUM,
            observations=[
                f"Audio level dropped to near-silence ({run[0].rms_db:.1f} dBFS or "
                f"below) for {duration:.2f}s.",
                f"Audio was active for at least {self.context_window:.1f}s immediately before this interval.",
                f"Audio was active again for at least {self.context_window:.1f}s "
                "immediately after this interval.",
            ],
            measurements={"duration": duration},
            possible_interpretation=(
                "Possible audio dropout (microphone or channel interruption) rather "
                "than an intentional pause, based on the surrounding audio activity. "
                "This cannot be distinguished from a very short deliberate pause with "
                "certainty from levels alone."
            ),
            detector=self.name,
            source_files=[ctx.source],
        )


class ChannelImbalanceDetector(Detector):
    """Tier 1 detector for spec section 28.3 (audio channel/routing).

    Only meaningful for multi-channel (typically stereo) audio. Classifies
    each window as one channel effectively missing while another is
    active (more severe: likely a dropped mic/feed), a large-but-nonzero
    imbalance between channels (less severe: could be an intentional
    mono-on-one-channel setup), or balanced -- and only reports sustained
    runs, not momentary blips.
    """

    name = "channel_imbalance"
    tier = 1
    requires = "audio (multi-channel)"

    def __init__(
        self,
        active_db: float = -40.0,
        missing_db: float = -55.0,
        imbalance_threshold_db: float = 12.0,
        min_duration: float = 1.0,
    ) -> None:
        self.active_db = active_db
        self.missing_db = missing_db
        self.imbalance_threshold_db = imbalance_threshold_db
        self.min_duration = min_duration
        self.skipped_reason: str | None = None

    def run(self, ctx: AnalysisContext) -> list[Event]:
        if ctx.channel_count() < 2:
            self.skipped_reason = (
                f"input has {ctx.channel_count()} audio channel(s); channel-imbalance "
                "detection needs at least 2."
            )
            return []
        envelope = ctx.channel_level_envelope()
        if not envelope:
            return []

        classified = [self._classify(w) for w in envelope]

        events: list[Event] = []
        i = 0
        n = len(classified)
        while i < n:
            label = classified[i]
            if label is None:
                i += 1
                continue
            j = i
            while j < n and classified[j] == label:
                j += 1
            run = envelope[i:j]
            duration = run[-1].end - run[0].start
            if duration >= self.min_duration:
                events.append(self._build_event(ctx, run, label, duration))
            i = j

        return events

    def _classify(self, window: ChannelLevelWindow) -> str | None:
        levels = list(window.channel_rms_db.values())
        if len(levels) < 2:
            return None
        active_levels = [lv for lv in levels if lv > self.active_db]
        missing_levels = [lv for lv in levels if lv <= self.missing_db]
        if active_levels and missing_levels:
            return "missing"
        if max(levels) - min(levels) >= self.imbalance_threshold_db and active_levels:
            return "imbalance"
        return None

    def _build_event(
        self,
        ctx: AnalysisContext,
        run: list[ChannelLevelWindow],
        label: str,
        duration: float,
    ) -> Event:
        last_levels = run[-1].channel_rms_db
        levels_str = ", ".join(f"ch{ch}: {lv:.1f} dBFS" for ch, lv in sorted(last_levels.items()))

        if label == "missing":
            severity = Severity.HIGH if duration >= 5.0 else Severity.MEDIUM
            confidence = Confidence.MEDIUM
            interpretation = (
                "Possible dropped microphone/channel or a routing fault: one channel "
                "was active while another was near-silent for a sustained period. "
                "This can also be an intentionally mono source routed to a single "
                "channel; the recording alone cannot distinguish these."
            )
        else:
            severity = Severity.LOW
            confidence = Confidence.LOW
            interpretation = (
                "Sustained level imbalance between channels. Could be a genuine "
                "routing/gain issue, or an intentional mix choice (e.g. a panned "
                "source); human review recommended."
            )

        return Event(
            start=run[0].start,
            end=run[-1].end,
            category=Category.AUDIO,
            type=f"channel_{label}",
            severity=severity,
            confidence=confidence,
            observations=[f"Channel levels diverged for {duration:.2f}s (at end of interval: {levels_str})."],
            measurements={"duration": duration, "channel_rms_db": last_levels},
            possible_interpretation=interpretation,
            detector=self.name,
            source_files=[ctx.source],
        )
