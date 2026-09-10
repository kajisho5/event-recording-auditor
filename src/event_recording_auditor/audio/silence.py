"""Silence detection via ffmpeg's built-in `silencedetect` filter."""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..media.runner import run_ffmpeg

_START_RE = re.compile(r"silence_start:\s*(?P<start>-?[\d.]+)")
_END_RE = re.compile(
    r"silence_end:\s*(?P<end>-?[\d.]+)\s*\|\s*silence_duration:\s*(?P<duration>[\d.]+)"
)


@dataclass
class SilenceSegment:
    start: float
    end: float
    duration: float


def detect_silence(
    source: str,
    noise_floor_db: float = -30.0,
    min_duration: float = 0.5,
    timeout: float | None = None,
) -> list[SilenceSegment]:
    """Return silence segments using ffmpeg's silencedetect filter.

    Args:
        noise_floor_db: level below which audio is considered silent
            (ffmpeg `noise`).
        min_duration: minimum silence duration in seconds to report
            (ffmpeg `d`). This is a raw technical measurement -- whether a
            given silence is a "normal pause between speakers" or a
            "possible dropout" is a judgment made by higher-level detectors
            using surrounding context, not by this function.
    """
    args = [
        "-i",
        source,
        "-af",
        f"silencedetect=noise={noise_floor_db}dB:d={min_duration}",
        "-f",
        "null",
        "-",
    ]
    proc = run_ffmpeg(args, timeout=timeout)

    starts = [float(m.group("start")) for m in _START_RE.finditer(proc.stderr)]
    ends = []
    durations = []
    for m in _END_RE.finditer(proc.stderr):
        ends.append(float(m.group("end")))
        durations.append(float(m.group("duration")))

    segments: list[SilenceSegment] = []
    for i, start in enumerate(starts):
        if i < len(ends):
            segments.append(
                SilenceSegment(start=start, end=ends[i], duration=durations[i])
            )
        # else: silence runs to EOF without an explicit silence_end line;
        # skip rather than guess an end time.
    return segments
