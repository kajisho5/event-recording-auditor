from event_recording_auditor.detectors import (
    AnalysisContext,
    BlackoutDetector,
    BriefUnexpectedSlideDetector,
    ProgressionInterruptionDetector,
    SlideRollbackPatternDetector,
)


def test_slide_rollback_pattern_detector_finds_core_use_case(
    premature_slide_advance_clip,
):
    ctx = AnalysisContext(premature_slide_advance_clip)
    events = SlideRollbackPatternDetector().run(ctx)
    assert len(events) == 1
    event = events[0]
    assert event.type == "slide_rollback_pattern"
    assert event.category.value == "presentation"
    assert event.measurements["confirmed_repeat"] is True
    assert event.requires_human_review is True


def test_brief_unexpected_slide_detector_finds_short_appearance(
    premature_slide_advance_clip,
):
    ctx = AnalysisContext(premature_slide_advance_clip)
    events = BriefUnexpectedSlideDetector(brief_duration_threshold=1.2).run(ctx)
    assert len(events) == 1
    assert events[0].duration < 1.2


def test_slide_rollback_pattern_detector_is_symmetric_in_which_state_comes_first(
    title_slide_missed_clip,
):
    """Regression test for the more common real-world variant of the core
    use case: a camera cutaway hides the presenter advancing past the title
    slide, so the recording's slide feed comes on already showing the next
    slide (B), then briefly rolls back to the title (A) before returning to
    B -- i.e. `B -> A -> B`, not the spec's literal `A -> B -> A(-> B)`. The
    detector only checks for a revisited state_id (see slide_detectors.py),
    so it should catch this regardless of which state appears first."""
    ctx = AnalysisContext(title_slide_missed_clip)
    events = SlideRollbackPatternDetector().run(ctx)
    assert len(events) == 1
    assert events[0].type == "slide_rollback_pattern"


def test_presentation_detectors_skip_on_non_slide_footage(continuously_changing_clip):
    """Regression test for a real false-positive flood found running against
    an actual (non-slide) video clip: content that changes on every sampled
    frame used to produce one brief_unexpected_slide finding per sample."""
    ctx = AnalysisContext(continuously_changing_clip)

    rollback = SlideRollbackPatternDetector()
    assert rollback.run(ctx) == []
    assert rollback.skipped_reason is not None

    brief = BriefUnexpectedSlideDetector()
    assert brief.run(ctx) == []
    assert brief.skipped_reason is not None


def test_presentation_detectors_skip_on_portrait_video(portrait_cutaway_clip):
    """Regression test for a second real false-positive class: a portrait
    video cutting back and forth between two static shots produces the same
    A -> B -> A revisit signature as a slide rollback (high stability ratio
    included), so the stability-ratio gate alone doesn't catch it. Slide
    decks/screen shares are landscape, so an aspect-ratio check does."""
    ctx = AnalysisContext(portrait_cutaway_clip)
    assert ctx.slide_stability_ratio() > 0.35  # would pass the other gate

    rollback = SlideRollbackPatternDetector()
    assert rollback.run(ctx) == []
    assert "landscape" in rollback.skipped_reason


def test_blackout_detector_emits_high_severity_for_long_black(blackout_clip):
    ctx = AnalysisContext(blackout_clip)
    events = BlackoutDetector(min_duration=0.1, high_severity_duration=0.8).run(ctx)
    assert len(events) == 1
    assert events[0].severity.value == "high"
    assert events[0].confidence.value == "high"


def test_progression_interruption_flags_quiet_static_clip(quiet_static_clip):
    ctx = AnalysisContext(quiet_static_clip)
    events = ProgressionInterruptionDetector(min_duration=10.0).run(ctx)
    assert len(events) == 1
    assert events[0].type == "progression_interruption"


def test_progression_interruption_does_not_flag_normal_recording(
    premature_slide_advance_clip,
):
    # Short clip, well under any interruption threshold -> nothing flagged.
    ctx = AnalysisContext(premature_slide_advance_clip)
    events = ProgressionInterruptionDetector(min_duration=10.0).run(ctx)
    assert events == []
