"""Freeze / repeated-frame detection via ffmpeg's `freezedetect` filter.

Note: freezedetect flags visually static video (near-zero frame-to-frame
difference). A presenter sitting still in a normal talking-head shot can
trigger this at low sensitivity -- see docs/false-positives.md. Callers
combine this with audio activity before treating a freeze as a technical
failure vs. a normal static shot.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..media.runner import run_ffmpeg

_FREEZE_START_RE = re.compile(r"freeze_start:\s*(?P<start>[\d.]+)")
_FREEZE_DURATION_RE = re.compile(r"freeze_duration:\s*(?P<duration>[\d.]+)")
_FREEZE_END_RE = re.compile(r"freeze_end:\s*(?P<end>[\d.]+)")


@dataclass
class FreezeSegment:
    start: float
    end: float
    duration: float


def detect_freeze(
    source: str,
    noise_threshold_db: float = -60.0,
    min_duration: float = 2.0,
    timeout: float | None = None,
) -> list[FreezeSegment]:
    """Return detected freeze segments using ffmpeg's freezedetect filter.

    Args:
        noise_threshold_db: sensitivity of the "no change" test (ffmpeg `n`).
        min_duration: minimum freeze duration in seconds to report
            (ffmpeg `d`).
    """
    filt = f"freezedetect=n={noise_threshold_db}dB:d={min_duration}"
    args = ["-i", source, "-vf", filt, "-an", "-f", "null", "-"]
    proc = run_ffmpeg(args, timeout=timeout)

    starts = [float(m.group("start")) for m in _FREEZE_START_RE.finditer(proc.stderr)]
    durations = [float(m.group("duration")) for m in _FREEZE_DURATION_RE.finditer(proc.stderr)]
    ends = [float(m.group("end")) for m in _FREEZE_END_RE.finditer(proc.stderr)]

    segments: list[FreezeSegment] = []
    for i, start in enumerate(starts):
        if i < len(durations):
            duration = durations[i]
            end = ends[i] if i < len(ends) else start + duration
        elif i < len(ends):
            end = ends[i]
            duration = end - start
        else:
            # Freeze runs to end of file and ffmpeg never emitted freeze_end.
            continue
        segments.append(FreezeSegment(start=start, end=end, duration=duration))
    return segments
