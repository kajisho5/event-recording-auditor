"""Windowed audio level envelope via ffmpeg's `astats` filter.

This is the shared building block behind clipping detection, the
"audio activity" signal used for progression-interruption correlation and
context-aware audio-dropout detection, channel-imbalance detection, and
(optionally) the experimental feedback detector. Computing it once and
reusing it avoids re-decoding the audio track for every downstream check.

We resample to a fixed rate/window size so window index -> timestamp is a
simple multiplication, rather than trying to recover per-frame PTS from
whatever the source sample rate happens to be.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..media.runner import run_ffmpeg

_FRAME_RE = re.compile(r"^frame:\d+\s+pts:\d+\s+pts_time:(?P<pts>[\d.]+)")
_KV_RE = re.compile(r"^lavfi\.astats\.(?P<key>[\w.]+)=(?P<value>.+)$")

_SAMPLE_RATE = 16000
NEG_INF_DB = -120.0


def _parse_db(value: str) -> float:
    value = value.strip()
    if value.lower() in ("-inf", "-infinity"):
        return NEG_INF_DB
    try:
        return float(value)
    except ValueError:
        return NEG_INF_DB


def _run_astats_windowed(
    source: str,
    window: float,
    channel_layout: str | None,
    timeout: float | None,
) -> list[tuple[float, dict[str, str]]]:
    """Run astats over fixed-size windows and yield (pts_time, {key: value})
    per window, where key is everything after `lavfi.astats.` (e.g.
    `Overall.RMS_level` or `1.RMS_level` for per-channel stats).

    `channel_layout=None` keeps the source's native channel layout (needed
    for per-channel stats); pass `"mono"` to downmix first.
    """
    n_samples = max(int(window * _SAMPLE_RATE), 1)
    aformat = f"aformat=sample_rates={_SAMPLE_RATE}"
    if channel_layout:
        aformat += f":channel_layouts={channel_layout}"
    filt = (
        f"{aformat},"
        f"asetnsamples=n={n_samples},"
        f"astats=metadata=1:reset=1,"
        f"ametadata=print:file=-"
    )
    args = ["-i", source, "-af", filt, "-f", "null", "-"]
    proc = run_ffmpeg(args, timeout=timeout)

    results: list[tuple[float, dict[str, str]]] = []
    current_pts: float | None = None
    current_kv: dict[str, str] = {}

    def flush() -> None:
        if current_pts is not None:
            results.append((current_pts, current_kv))

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

    return results


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


def compute_level_envelope(
    source: str,
    window: float = 0.5,
    timeout: float | None = None,
) -> list[LevelWindow]:
    """Compute per-window RMS/peak/flat-factor over the whole (downmixed) audio track.

    Args:
        window: window duration in seconds. 0.5s balances temporal
            resolution against noise in short-term RMS estimates.
    """
    raw = _run_astats_windowed(source, window, channel_layout="mono", timeout=timeout)
    windows: list[LevelWindow] = []
    for pts, kv in raw:
        windows.append(
            LevelWindow(
                start=pts,
                end=pts + window,
                rms_db=_parse_db(kv.get("Overall.RMS_level", "-inf")),
                peak_db=_parse_db(kv.get("Overall.Peak_level", "-inf")),
                flat_factor=float(kv.get("Overall.Flat_factor", "0") or 0.0),
            )
        )
    return windows


@dataclass
class ChannelLevelWindow:
    start: float
    end: float
    channel_rms_db: dict[int, float] = field(default_factory=dict)  # 1-indexed, matches ffmpeg


def compute_channel_level_envelope(
    source: str,
    channels: int,
    window: float = 0.5,
    timeout: float | None = None,
) -> list[ChannelLevelWindow]:
    """Compute per-channel RMS over time, without downmixing.

    Used for channel-imbalance / dropped-channel detection (spec section
    28.3). Only meaningful for `channels >= 2`; callers should not call
    this for mono sources.
    """
    raw = _run_astats_windowed(source, window, channel_layout=None, timeout=timeout)
    windows: list[ChannelLevelWindow] = []
    for pts, kv in raw:
        channel_rms = {}
        for ch in range(1, channels + 1):
            key = f"{ch}.RMS_level"
            if key in kv:
                channel_rms[ch] = _parse_db(kv[key])
        windows.append(ChannelLevelWindow(start=pts, end=pts + window, channel_rms_db=channel_rms))
    return windows
