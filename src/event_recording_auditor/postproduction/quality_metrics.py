"""Objective source-vs-export quality metrics via ffmpeg's built-in ssim/psnr filters.

No external quality-metrics library is used: ffmpeg already ships SSIM and
PSNR filters, which is exactly the kind of ffmpeg-ecosystem functionality
this project avoids duplicating (see docs/architecture.md). VMAF is
deliberately not used here because it requires a libvmaf-enabled ffmpeg
build, which is not guaranteed to be present -- see docs/research.md for
the tradeoff.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..media.runner import run_ffmpeg

_SSIM_RE = re.compile(r"All:(?P<all>[\d.]+)\s+\((?P<db>[\d.]+|inf)\)")
_PSNR_RE = re.compile(
    r"average:(?P<avg>[\d.]+|inf)\s+min:(?P<min>[\d.]+|inf)\s+max:(?P<max>[\d.]+|inf)"
)


@dataclass
class QualityMetrics:
    ssim_avg: float | None
    psnr_avg_db: float | None
    psnr_min_db: float | None
    compared_resolution: tuple[int, int]


def _to_float(value: str) -> float:
    return float("inf") if value == "inf" else float(value)


def compare_quality(
    source_path: str,
    export_path: str,
    source_resolution: tuple[int, int],
    export_resolution: tuple[int, int],
    max_duration: float | None = 60.0,
    timeout: float | None = 300.0,
) -> QualityMetrics:
    """Compute SSIM/PSNR between `export_path` and `source_path`.

    Whichever file has more total pixels is downscaled to match the
    other's resolution before comparing (comparing at the lower common
    resolution avoids upscale-blur artifacts skewing the score). If
    `max_duration` is set, only the first N seconds are compared -- for a
    quality investigation this is normally sufficient and much faster than
    processing an entire long recording (see requirement: avoid
    unnecessary processing of the entire video when targeted analysis is
    possible).
    """
    source_pixels = source_resolution[0] * source_resolution[1]
    export_pixels = export_resolution[0] * export_resolution[1]
    target = source_resolution if source_pixels <= export_pixels else export_resolution

    args = ["-i", export_path, "-i", source_path]
    if max_duration:
        args = ["-i", export_path, "-t", str(max_duration), "-i", source_path, "-t", str(max_duration)]

    scale_filter = f"scale={target[0]}:{target[1]}"
    filt = f"[0:v]{scale_filter}[a];[1:v]{scale_filter}[b];[a][b]ssim"
    ssim_proc = run_ffmpeg(args + ["-lavfi", filt, "-f", "null", "-"], timeout=timeout)
    ssim_match = _SSIM_RE.search(ssim_proc.stderr)

    filt = f"[0:v]{scale_filter}[a];[1:v]{scale_filter}[b];[a][b]psnr"
    psnr_proc = run_ffmpeg(args + ["-lavfi", filt, "-f", "null", "-"], timeout=timeout)
    psnr_match = _PSNR_RE.search(psnr_proc.stderr)

    return QualityMetrics(
        ssim_avg=float(ssim_match.group("all")) if ssim_match else None,
        psnr_avg_db=_to_float(psnr_match.group("avg")) if psnr_match else None,
        psnr_min_db=_to_float(psnr_match.group("min")) if psnr_match else None,
        compared_resolution=target,
    )
