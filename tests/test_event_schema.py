import pytest

from event_recording_auditor.timeline import Category, Confidence, Event, Severity, Timeline


def test_event_rejects_end_before_start():
    with pytest.raises(ValueError):
        Event(
            start=5.0,
            end=1.0,
            category=Category.VIDEO,
            type="blackout",
            severity=Severity.LOW,
            confidence=Confidence.LOW,
        )


def test_event_to_dict_keeps_observation_interpretation_separation():
    event = Event(
        start=1.0,
        end=2.0,
        category=Category.PRESENTATION,
        type="slide_rollback_pattern",
        severity=Severity.MEDIUM,
        confidence=Confidence.MEDIUM,
        observations=["Slide 2 appeared briefly."],
        possible_interpretation="Possible premature advance.",
    )
    d = event.to_dict()
    assert d["observations"] == ["Slide 2 appeared briefly."]
    assert d["possible_interpretation"] == "Possible premature advance."
    assert d["requires_human_review"] is True
    assert d["duration"] == pytest.approx(1.0)


def test_timeline_sorts_and_summarizes():
    tl = Timeline()
    tl.add(
        Event(
            start=10.0, end=11.0, category=Category.AUDIO, type="clipping",
            severity=Severity.HIGH, confidence=Confidence.HIGH,
        )
    )
    tl.add(
        Event(
            start=1.0, end=2.0, category=Category.VIDEO, type="blackout",
            severity=Severity.LOW, confidence=Confidence.LOW,
        )
    )
    events = tl.events
    assert [e.start for e in events] == [1.0, 10.0]

    summary = tl.summary()
    assert summary["total_events"] == 2
    assert summary["by_severity"] == {"low": 1, "medium": 0, "high": 1}
    assert summary["by_category"] == {"video": 1, "audio": 1}
