import pytest

from event_recording_auditor.audio import compute_level_envelope, detect_clipping, detect_silence


def test_detect_silence_finds_gap(silence_gap_audio):
    segments = detect_silence(silence_gap_audio, min_duration=0.3)
    assert len(segments) == 1
    seg = segments[0]
    assert seg.start == pytest.approx(2.0, abs=0.05)
    assert seg.duration == pytest.approx(1.0, abs=0.05)


def test_detect_clipping_flags_amplified_tone(clipped_audio):
    envelope = compute_level_envelope(clipped_audio)
    segments = detect_clipping(clipped_audio, envelope=envelope)
    assert len(segments) >= 1
    assert segments[0].max_flat_factor > 1.0


def test_detect_clipping_does_not_flag_normal_tone(normal_tone_audio):
    envelope = compute_level_envelope(normal_tone_audio)
    segments = detect_clipping(normal_tone_audio, envelope=envelope)
    assert segments == []
