"""Windowed audio level envelope via ffmpeg's `astats` filter.

This is the shared building block behind clipping detection, the
"audio activity" signal used for progression-interruption correlation and
context-aware audio-dropout detection, and (optionally) the experimental
feedback detector. Computing it once and reusing it avoids re-decoding the
audio track for every downstream check.

We resample to a fixed rate/window size so window index -> timestamp is a
simple multiplication, rather than trying to recover per-frame PTS from
whatever the source sample rate happens to be.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..media.runner import run_ffmpeg

_FRAME_RE = re.compile(r"^frame:\d+\s+pts:\d+\s+pts_time:(?P<pts>[\d.]+)")
_KV_RE = re.compile(r"^lavfi\.astats\.Overall\.(?P<key>\w+)=(?P<value>.+)$")

_SAMPLE_RATE = 16000


@dataclass
class LevelWindow:
    start: float
    end: float
    rms_db: float  # -inf represented as a very low float (see NEG_INF_DB)
    peak_db: float
    flat_factor: float

    @property
    def is_silent_floor(self) -> bool:
        return self.rms_db <= -90.0


NEG_INF_DB = -120.0


def _parse_db(value: str) -> float:
    value = value.strip()
    if value.lower() in ("-inf", "-infinity"):
        return NEG_INF_DB
    try:
        return float(value)
    except ValueError:
        return NEG_INF_DB


def compute_level_envelope(
    source: str,
    window: float = 0.5,
    timeout: float | None = None,
) -> list[LevelWindow]:
    """Compute per-window RMS/peak/flat-factor over the whole audio track.

    Args:
        window: window duration in seconds. 0.5s balances temporal
            resolution against noise in short-term RMS estimates.
    """
    n_samples = max(int(window * _SAMPLE_RATE), 1)
    filt = (
        f"aformat=sample_rates={_SAMPLE_RATE}:channel_layouts=mono,"
        f"asetnsamples=n={n_samples},"
        f"astats=metadata=1:reset=1,"
        f"ametadata=print:file=-"
    )
    args = ["-i", source, "-af", filt, "-f", "null", "-"]
    proc = run_ffmpeg(args, timeout=timeout)

    windows: list[LevelWindow] = []
    current_pts: float | None = None
    current_kv: dict[str, str] = {}

    def flush() -> None:
        if current_pts is None:
            return
        rms = _parse_db(current_kv.get("RMS_level", "-inf"))
        peak = _parse_db(current_kv.get("Peak_level", "-inf"))
        flat = float(current_kv.get("Flat_factor", "0") or 0.0)
        windows.append(
            LevelWindow(
                start=current_pts,
                end=current_pts + window,
                rms_db=rms,
                peak_db=peak,
                flat_factor=flat,
            )
        )

    for line in proc.stdout.splitlines():
        frame_match = _FRAME_RE.match(line)
        if frame_match:
            flush()
            current_pts = float(frame_match.group("pts"))
            current_kv = {}
            continue
        kv_match = _KV_RE.match(line)
        if kv_match:
            current_kv[kv_match.group("key")] = kv_match.group("value")
    flush()

    return windows
