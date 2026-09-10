from event_recording_auditor.detectors import (
    AnalysisContext,
    BlackoutDetector,
    BriefUnexpectedSlideDetector,
    ProgressionInterruptionDetector,
    SlideRollbackPatternDetector,
)


def test_slide_rollback_pattern_detector_finds_core_use_case(premature_slide_advance_clip):
    ctx = AnalysisContext(premature_slide_advance_clip)
    events = SlideRollbackPatternDetector().run(ctx)
    assert len(events) == 1
    event = events[0]
    assert event.type == "slide_rollback_pattern"
    assert event.category.value == "presentation"
    assert event.measurements["confirmed_repeat"] is True
    assert event.requires_human_review is True


def test_brief_unexpected_slide_detector_finds_short_appearance(premature_slide_advance_clip):
    ctx = AnalysisContext(premature_slide_advance_clip)
    events = BriefUnexpectedSlideDetector(brief_duration_threshold=1.2).run(ctx)
    assert len(events) == 1
    assert events[0].duration < 1.2


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


def test_progression_interruption_does_not_flag_normal_recording(premature_slide_advance_clip):
    # Short clip, well under any interruption threshold -> nothing flagged.
    ctx = AnalysisContext(premature_slide_advance_clip)
    events = ProgressionInterruptionDetector(min_duration=10.0).run(ctx)
    assert events == []
