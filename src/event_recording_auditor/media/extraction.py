"""Evidence extraction primitives: grab a still frame or a short clip.

These always write to a *new* output path and never touch the source file,
per the "never silently modify or overwrite the original recording"
requirement.
"""

from __future__ import annotations

from pathlib import Path

from .runner import run_ffmpeg


def extract_frame(source: str | Path, timestamp: float, out_path: str | Path) -> Path:
    """Extract a single JPEG frame at `timestamp` seconds into `out_path`."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    args = [
        "-y",
        "-ss",
        f"{max(timestamp, 0.0):.3f}",
        "-i",
        str(source),
        "-frames:v",
        "1",
        "-q:v",
        "3",
        str(out_path),
    ]
    run_ffmpeg(args, check_returncode=True)
    return out_path


def extract_clip(
    source: str | Path,
    start: float,
    end: float,
    out_path: str | Path,
    pad: float = 1.5,
    reencode: bool = True,
) -> Path:
    """Extract a short evidence clip covering [start - pad, end + pad].

    `reencode=True` (default) re-encodes so the clip starts on a clean
    keyframe and plays back correctly in any viewer; stream-copy (`False`)
    is faster but may snap to the nearest keyframe before `start`.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    clip_start = max(start - pad, 0.0)
    duration = max((end - start) + 2 * pad, 0.5)

    args = [
        "-y",
        "-ss",
        f"{clip_start:.3f}",
        "-i",
        str(source),
        "-t",
        f"{duration:.3f}",
    ]
    if reencode:
        args += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-c:a", "aac"]
    else:
        args += ["-c", "copy"]
    args.append(str(out_path))

    run_ffmpeg(args, check_returncode=True)
    return out_path
