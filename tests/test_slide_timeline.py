import pytest

from event_recording_auditor.slides import build_segments, build_slide_timeline, sample_frames


def test_core_use_case_1_2_1_2_pattern(premature_slide_advance_clip):
    """Spec section 3's core use case: recognize 1 -> 2 -> 1 -> 2 with a
    brief first appearance of slide 2 and a longer, later appearance."""
    samples = sample_frames(premature_slide_advance_clip)
    segments = build_segments(samples)
    states = build_slide_timeline(segments)

    assert len(states) == 4
    ids = [s.state_id for s in states]
    assert ids[0] == ids[2]
    assert ids[1] == ids[3]
    assert ids[0] != ids[1]

    # The first appearance of the "next slide" is brief; the second is not.
    assert states[1].duration < states[3].duration
    assert states[1].duration == pytest.approx(0.5, abs=0.3)
    assert states[3].duration == pytest.approx(3.0, abs=0.5)
