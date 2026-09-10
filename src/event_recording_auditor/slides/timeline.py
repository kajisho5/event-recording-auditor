"""Assign stable "slide state" IDs to segments, recognizing revisits.

This is what turns a list of visually-distinct segments into the kind of
timeline the spec's core use case needs: recognizing that a brief
appearance of "slide 2" and a later, longer appearance of "slide 2" are the
*same* state, so the sequence can be read as `1 -> 2 -> 1 -> 2` rather than
four unrelated segments.

A new segment is matched against previously-seen state hashes (not just the
immediately preceding one) so that a return to an earlier slide is
recognized even after several intervening states.
"""

from __future__ import annotations

from dataclasses import dataclass

from .boundary import Segment
from .phash import hamming_distance


@dataclass
class SlideState:
    start: float
    end: float
    state_id: int
    hash: int
    sample_count: int

    @property
    def duration(self) -> float:
        return self.end - self.start


def build_slide_timeline(
    segments: list[Segment],
    match_threshold: int = 48,
    min_segment_duration: float = 0.0,
) -> list[SlideState]:
    """Assign a stable integer state_id to each segment.

    Args:
        match_threshold: max Hamming distance to a previously-seen state's
            canonical hash for a segment to be considered a revisit of that
            state rather than a new one. Looser than
            `boundary.build_segments`'s stable_threshold, since two visits
            to "the same slide" can differ slightly (e.g. a highlighted
            bullet, a laser pointer, cursor position) while still clearly
            being the same slide. The default (48) is calibrated for the
            default 32x32+5-bit hash (~4.7% of bits); rescale
            proportionally if a different `grid` is used.
        min_segment_duration: segments shorter than this are still assigned
            a state_id (never dropped -- brief appearances are exactly what
            the premature-advance detector looks for) but are excluded when
            computing a state's canonical hash, since a half-glimpsed frame
            is a noisier fingerprint than a fully-displayed one.
    """
    canonical_hash: dict[int, int] = {}
    next_id = 0
    states: list[SlideState] = []

    for seg in segments:
        best_id = None
        best_distance = None
        for state_id, chash in canonical_hash.items():
            distance = hamming_distance(seg.hash, chash)
            if best_distance is None or distance < best_distance:
                best_distance = distance
                best_id = state_id

        if best_id is not None and best_distance is not None and best_distance <= match_threshold:
            state_id = best_id
            if seg.end - seg.start >= min_segment_duration:
                canonical_hash[state_id] = seg.hash
        else:
            state_id = next_id
            next_id += 1
            canonical_hash[state_id] = seg.hash

        states.append(
            SlideState(
                start=seg.start,
                end=seg.end,
                state_id=state_id,
                hash=seg.hash,
                sample_count=seg.sample_count,
            )
        )

    return states
