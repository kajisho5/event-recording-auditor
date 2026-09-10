"""Frame sampling + a simple average-hash perceptual fingerprint.

Why a hand-rolled average hash instead of a library (e.g. `imagehash`,
which depends on Pillow/NumPy/SciPy)? At the tiny grid sizes used here
(default 16x16 = 256 pixels, hashed with a single global threshold) the
algorithm is a few lines of pure Python and ffmpeg already provides the
downscale/grayscale conversion, so no extra dependency is justified for
this project's needs (see docs/architecture.md, "Dependencies"). If a
future detector needs a more discriminating hash (pHash/DCT-based, for
robustness against compression noise) that tradeoff should be revisited
explicitly rather than assumed.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..media.runner import FFmpegError, run_ffmpeg_binary


@dataclass
class FrameSample:
    time: float
    hash: int  # grid*grid-bit integer, 1 = pixel above frame mean


def hamming_distance(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


_BRIGHTNESS_BUCKETS = 32  # 5 bits


def _average_hash(pixels: bytes) -> int:
    """Average hash plus a quantized overall-brightness bucket.

    Plain average-hash encodes only *texture relative to the frame's own
    mean* -- two frames that are each a single flat color (a blank title
    slide, an inter-slide black frame) hash identically regardless of which
    color, because every pixel equals the mean by definition. Folding in a
    coarse brightness bucket lets those frames still be told apart.
    """
    mean = sum(pixels) / len(pixels)
    bits = 0
    for value in pixels:
        bits = (bits << 1) | (1 if value >= mean else 0)
    bucket = min(int(mean / 256 * _BRIGHTNESS_BUCKETS), _BRIGHTNESS_BUCKETS - 1)
    return (bucket << (len(pixels))) | bits


def sample_frames(
    source: str,
    fps: float = 2.0,
    grid: int = 32,
    start: float | None = None,
    duration: float | None = None,
    timeout: float | None = None,
) -> list[FrameSample]:
    """Sample `source` at `fps` frames/sec and compute an average-hash per frame.

    A low fps (default 2/sec) is intentional: slide-timeline detection does
    not need per-frame video resolution, and sampling less means analyzing
    less of the file (see requirement: avoid unnecessary processing of the
    entire video when targeted analysis is possible).
    """
    filt = f"fps={fps},scale={grid}:{grid}:flags=area,format=gray"
    args = []
    if start is not None:
        args += ["-ss", f"{start:.3f}"]
    args += ["-i", source]
    if duration is not None:
        args += ["-t", f"{duration:.3f}"]
    args += ["-vf", filt, "-an", "-f", "rawvideo", "-pix_fmt", "gray", "-"]

    stdout, stderr, returncode = run_ffmpeg_binary(args, timeout=timeout)
    if returncode != 0:
        raise FFmpegError(f"ffmpeg failed sampling frames from {source!r}: {stderr}")

    frame_size = grid * grid
    n_frames = len(stdout) // frame_size
    base_time = start or 0.0
    samples: list[FrameSample] = []
    for i in range(n_frames):
        chunk = stdout[i * frame_size : (i + 1) * frame_size]
        samples.append(FrameSample(time=base_time + i / fps, hash=_average_hash(chunk)))
    return samples
