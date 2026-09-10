"""Clipping detection built on the windowed level envelope.

Clipping is identified by two corroborating, independent signals rather
than peak level alone (a legitimately loud, unclipped passage can also
approach 0 dBFS briefly):

- `peak_db` close to 0 dBFS (the signal is hitting the ceiling), and
- `flat_factor` > 0 (ffmpeg's astats measure of consecutive samples stuck
  at an extreme value -- the actual waveform signature of clipping).

Both must hold for at least `min_duration` seconds before we report a
segment, to avoid flagging a single loud transient.
"""

from __future__ import annotations

from dataclasses import dataclass

from .levels import LevelWindow, compute_level_envelope


@dataclass
class ClippingSegment:
    start: float
    end: float
    duration: float
    max_peak_db: float
    max_flat_factor: float


def detect_clipping(
    source: str,
    peak_threshold_db: float = -1.0,
    flat_factor_threshold: float = 0.5,
    min_duration: float = 0.2,
    window: float = 0.5,
    envelope: list[LevelWindow] | None = None,
) -> list[ClippingSegment]:
    """Return clipping segments.

    Args:
        peak_threshold_db: peak level (dBFS) at/above which a window is
            "hot enough" to be a clipping candidate.
        flat_factor_threshold: minimum astats Flat_factor to corroborate
            clipping (0 for clean audio; double digits for hard clipping).
        min_duration: minimum sustained duration to report.
        envelope: reuse a precomputed envelope instead of recomputing it.
    """
    windows = envelope if envelope is not None else compute_level_envelope(source, window)

    segments: list[ClippingSegment] = []
    run: list[LevelWindow] = []

    def flush() -> None:
        if not run:
            return
        duration = run[-1].end - run[0].start
        if duration >= min_duration:
            segments.append(
                ClippingSegment(
                    start=run[0].start,
                    end=run[-1].end,
                    duration=duration,
                    max_peak_db=max(w.peak_db for w in run),
                    max_flat_factor=max(w.flat_factor for w in run),
                )
            )
        run.clear()

    for w in windows:
        is_hot = w.peak_db >= peak_threshold_db and w.flat_factor >= flat_factor_threshold
        if is_hot:
            run.append(w)
        else:
            flush()
    flush()

    return segments
