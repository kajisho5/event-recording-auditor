"""Tier 2 presentation detectors built on the slide state timeline.

These implement the project's core use case (see docs/detection-model.md
and spec section 3): recognizing a state sequence like `1 -> 2 -> 1 -> 2`
as a candidate premature-advance-and-correction, without ever asserting
that a mistake definitely happened -- some presenters legitimately revisit
a previous slide. See docs/false-positives.md for the calibration
rationale.
"""

from __future__ import annotations

from ..slides.timeline import SlideState
from ..timeline import Category, Confidence, Event, Severity
from .base import Detector
from .context import AnalysisContext

# Below this fraction of "time spent in a stable state", the recording
# does not look like a slide/presentation feed at all (ordinary video
# changes on essentially every sampled frame) -- both detectors below
# skip rather than flood the report. Calibrated against real footage: a
# synthetic slide deck scores ~0.94, an unrelated broadcast video clip
# scored ~0.05. See docs/false-positives.md.
MIN_SLIDE_STABILITY_RATIO = 0.35

# Slide decks and screen shares are landscape (4:3, 16:9, ...); a square or
# portrait video is essentially never one. Found necessary after the
# stability-ratio check alone still passed a portrait short-form video
# edited with a small number of repeated camera angles cut back and forth
# -- visually indistinguishable from slide revisits by duration/stability
# alone. See docs/false-positives.md.
MIN_PRESENTATION_ASPECT_RATIO = 1.2


def _non_presentation_reason(
    ctx: AnalysisContext, min_stability_ratio: float
) -> str | None:
    """Return why `ctx` doesn't look like slide/presentation content, or
    None if the presentation detectors' assumptions plausibly hold."""
    aspect = ctx.aspect_ratio()
    if aspect is not None and aspect < MIN_PRESENTATION_ASPECT_RATIO:
        return (
            f"content is not landscape (aspect ratio {aspect:.2f} < "
            f"{MIN_PRESENTATION_ASPECT_RATIO}); slide decks and screen shares are "
            "virtually always landscape, so this is very unlikely to be one."
        )
    ratio = ctx.slide_stability_ratio()
    if ratio is not None and ratio < min_stability_ratio:
        return (
            f"content does not look slide-like (stability ratio {ratio:.2f} < "
            f"{min_stability_ratio}); this detector assumes long-held slide states "
            "and would otherwise flood the report on ordinary video."
        )
    return None


class SlideRollbackPatternDetector(Detector):
    """Detects A -> B -> A (-> B) revisit patterns in the slide timeline."""

    name = "slide_rollback_pattern"
    tier = 2
    requires = "video"

    def __init__(
        self,
        brief_duration_threshold: float = 2.0,
        min_stability_ratio: float = MIN_SLIDE_STABILITY_RATIO,
    ) -> None:
        self.brief_duration_threshold = brief_duration_threshold
        self.min_stability_ratio = min_stability_ratio
        self.skipped_reason: str | None = None

    def run(self, ctx: AnalysisContext) -> list[Event]:
        states = ctx.slide_states()
        if len(states) < 3:
            return []

        reason = _non_presentation_reason(ctx, self.min_stability_ratio)
        if reason:
            self.skipped_reason = reason
            return []

        events = []
        i = 0
        while i <= len(states) - 3:
            a, b, a2 = states[i], states[i + 1], states[i + 2]
            if a.state_id == a2.state_id and b.state_id != a.state_id:
                events.append(self._build_event(ctx, states, i))
                i += 2  # skip past this pattern's B->A to avoid overlapping duplicates
            else:
                i += 1
        return events

    def _build_event(self, ctx: AnalysisContext, states: list[SlideState], i: int) -> Event:
        a, b, a2 = states[i], states[i + 1], states[i + 2]
        has_repeat = (
            i + 3 < len(states)
            and states[i + 3].state_id == b.state_id
        )
        first_b_brief = b.duration < self.brief_duration_threshold

        sequence_ids = [a.state_id, b.state_id, a2.state_id]
        if has_repeat:
            sequence_ids.append(states[i + 3].state_id)

        observations = [
            f"Slide state {a.state_id} was displayed for {a.duration:.2f}s.",
            f"Slide state {b.state_id} then appeared for {b.duration:.2f}s.",
            f"The recording returned to slide state {a.state_id} "
            f"for {a2.duration:.2f}s.",
        ]
        if has_repeat:
            observations.append(
                f"Slide state {b.state_id} appeared again afterward, this time for "
                f"{states[i + 3].duration:.2f}s."
            )

        if first_b_brief and has_repeat:
            severity = Severity.MEDIUM
            confidence = Confidence.MEDIUM
            interpretation = (
                "Consistent with a premature slide advance followed by an operator/"
                "presenter correction: the first appearance of the later slide was "
                "brief compared to its return."
            )
        elif first_b_brief:
            severity = Severity.MEDIUM
            confidence = Confidence.LOW
            interpretation = (
                "Consistent with a premature slide advance and correction, but the "
                "sequence did not repeat afterward to confirm the pattern."
            )
        else:
            severity = Severity.LOW
            confidence = Confidence.LOW
            interpretation = (
                "Slide state was revisited, but the intervening slide was displayed "
                "for a substantial duration -- this looks more consistent with an "
                "intentional return to a previous slide than a correction."
            )

        return Event(
            start=a.end,
            end=a2.end if not has_repeat else states[i + 3].start,
            category=Category.PRESENTATION,
            type="slide_rollback_pattern",
            severity=severity,
            confidence=confidence,
            observations=observations,
            measurements={
                "sequence": sequence_ids,
                "first_intervening_duration": b.duration,
                "confirmed_repeat": has_repeat,
            },
            possible_interpretation=interpretation,
            detector=self.name,
            source_files=[ctx.source],
        )


class BriefUnexpectedSlideDetector(Detector):
    """Flags any slide state displayed for an unusually short time.

    Distinct from `SlideRollbackPatternDetector`: this fires on any brief
    appearance (including one that does *not* revert to the prior slide,
    e.g. `A -> B(brief) -> C`), which the rollback-pattern detector cannot
    see because it specifically looks for a return to `A`.
    """

    name = "brief_unexpected_slide"
    tier = 2
    requires = "video"

    def __init__(
        self,
        brief_duration_threshold: float = 1.2,
        min_stability_ratio: float = MIN_SLIDE_STABILITY_RATIO,
    ) -> None:
        self.brief_duration_threshold = brief_duration_threshold
        self.min_stability_ratio = min_stability_ratio
        self.skipped_reason: str | None = None

    def run(self, ctx: AnalysisContext) -> list[Event]:
        states = ctx.slide_states()
        if len(states) < 2:
            return []

        reason = _non_presentation_reason(ctx, self.min_stability_ratio)
        if reason:
            self.skipped_reason = reason
            return []

        events = []
        for i in range(1, len(states) - 1):
            state = states[i]
            if state.duration >= self.brief_duration_threshold:
                continue
            prev_state, next_state = states[i - 1], states[i + 1]
            events.append(
                Event(
                    start=state.start,
                    end=state.end,
                    category=Category.PRESENTATION,
                    type="brief_unexpected_slide",
                    severity=Severity.MEDIUM,
                    confidence=Confidence.LOW,
                    observations=[
                        f"Slide state {state.state_id} was displayed for only "
                        f"{state.duration:.2f}s, between slide state "
                        f"{prev_state.state_id} and slide state {next_state.state_id}.",
                    ],
                    measurements={
                        "duration": state.duration,
                        "previous_state": prev_state.state_id,
                        "next_state": next_state.state_id,
                    },
                    possible_interpretation=(
                        "Possible unintended brief slide appearance (premature "
                        "advance, accidental click, or animation step captured as a "
                        "separate state). Could also be a fast, intentional flip "
                        "through reference material."
                    ),
                    detector=self.name,
                    source_files=[ctx.source],
                )
            )
        return events
