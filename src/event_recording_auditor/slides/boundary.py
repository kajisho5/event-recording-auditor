"""Group a raw frame-hash sample stream into visually-stable segments.

This is the first clustering pass: it only merges consecutive samples that
look the same, without trying to recognize a *return* to an earlier visual
state (that's `timeline.py`'s job). Keeping the two passes separate keeps
each one simple to reason about and test independently.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .phash import FrameSample, hamming_distance


@dataclass
class Segment:
    start: float
    end: float
    hash: int  # representative hash: the first sample's hash in the segment
    sample_count: int
    max_internal_distance: int = 0
    representative_hashes: list[int] = field(default_factory=list)


def build_segments(
    samples: list[FrameSample],
    stable_threshold: int = 24,
    frame_step: float | None = None,
) -> list[Segment]:
    """Merge consecutive frame samples into stable visual segments.

    Args:
        stable_threshold: max Hamming distance between a sample and the
            segment's representative hash for it to still count as "the
            same picture". Small changes (cursor, minor animation,
            compression noise) stay under this; an actual slide change does
            not. The default (24) is calibrated for the default 32x32+5-bit
            hash from `phash.sample_frames` (~2.3% of bits); rescale
            proportionally if a different `grid` is used.
        frame_step: time between samples; defaults to inferring from the
            first two samples so the final segment's `end` extends one
            sample-interval past its last sample rather than stopping short.
    """
    if not samples:
        return []

    if frame_step is None:
        frame_step = samples[1].time - samples[0].time if len(samples) > 1 else 0.5

    segments: list[Segment] = []
    current = Segment(
        start=samples[0].time,
        end=samples[0].time,
        hash=samples[0].hash,
        sample_count=1,
        representative_hashes=[samples[0].hash],
    )

    for sample in samples[1:]:
        distance = hamming_distance(current.hash, sample.hash)
        if distance <= stable_threshold:
            current.sample_count += 1
            current.max_internal_distance = max(current.max_internal_distance, distance)
            current.representative_hashes.append(sample.hash)
            current.end = sample.time
        else:
            current.end = sample.time
            segments.append(current)
            current = Segment(
                start=sample.time,
                end=sample.time,
                hash=sample.hash,
                sample_count=1,
                representative_hashes=[sample.hash],
            )

    current.end = current.end + frame_step
    segments.append(current)
    return segments
