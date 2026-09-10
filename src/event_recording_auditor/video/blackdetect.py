"""Black-frame / blackout detection via ffmpeg's built-in `blackdetect` filter.

We deliberately do not reimplement black-frame detection ourselves --
blackdetect is a mature, well-tested part of the FFmpeg ecosystem (see
docs/architecture.md, section "Relationship to FFmpeg"). This module only
runs it and parses its stderr output into structured segments.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..media.runner import run_ffmpeg

_BLACK_RE = re.compile(
    r"black_start:(?P<start>[\d.]+)\s+black_end:(?P<end>[\d.]+)\s+"
    r"black_duration:(?P<duration>[\d.]+)"
)


@dataclass
class BlackSegment:
    start: float
    end: float
    duration: float


def detect_black(
    source: str,
    pixel_black_threshold: float = 0.10,
    picture_black_ratio_threshold: float = 0.98,
    min_duration: float = 0.10,
    timeout: float | None = None,
) -> list[BlackSegment]:
    """Return detected black segments using ffmpeg's blackdetect filter.

    Args:
        pixel_black_threshold: fraction of max luma below which a pixel is
            "black" (ffmpeg `pix_th`).
        picture_black_ratio_threshold: fraction of black pixels needed to
            call the whole frame black (ffmpeg `pic_th`).
        min_duration: minimum black duration in seconds to report
            (ffmpeg `d`). Short flashes below this are ignored as noise.
    """
    filt = (
        f"blackdetect=d={min_duration}:"
        f"pic_th={picture_black_ratio_threshold}:"
        f"pix_th={pixel_black_threshold}"
    )
    args = ["-i", source, "-vf", filt, "-an", "-f", "null", "-"]
    proc = run_ffmpeg(args, timeout=timeout)

    segments: list[BlackSegment] = []
    for match in _BLACK_RE.finditer(proc.stderr):
        segments.append(
            BlackSegment(
                start=float(match.group("start")),
                end=float(match.group("end")),
                duration=float(match.group("duration")),
            )
        )
    return segments
