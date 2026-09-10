from event_recording_auditor.video import detect_black, detect_freeze


def test_detect_black_finds_inserted_blackout(blackout_clip):
    segments = detect_black(blackout_clip, min_duration=0.1)
    assert len(segments) == 1
    seg = segments[0]
    # 3s blue, 1s black, 2s blue -> black runs from ~3.0 to ~4.0
    assert seg.start == pytest_approx(3.0)
    assert seg.duration == pytest_approx(1.0)


def test_detect_freeze_flags_static_segments(blackout_clip):
    # Every segment in this fixture is a flat color, so freezedetect should
    # find at least the black segment (and typically the solid-color runs
    # too) -- this only asserts the wrapper parses ffmpeg's output at all.
    segments = detect_freeze(blackout_clip, min_duration=0.5)
    assert len(segments) >= 1
    for seg in segments:
        assert seg.end > seg.start
        assert seg.duration > 0


def pytest_approx(value, rel=0.05):
    import pytest

    return pytest.approx(value, rel=rel, abs=0.2)
