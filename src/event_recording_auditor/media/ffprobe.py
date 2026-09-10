"""Thin wrapper around ffprobe: the single source of truth for media metadata.

No custom parsing of container formats is implemented here -- ffprobe already
does this reliably, so we shell out to it and normalize its JSON output. This
follows the project's principle of not duplicating FFmpeg-ecosystem
functionality (see docs/architecture.md).
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class FFprobeNotFoundError(RuntimeError):
    pass


class FFprobeError(RuntimeError):
    pass


def _ffprobe_bin() -> str:
    path = shutil.which("ffprobe")
    if not path:
        raise FFprobeNotFoundError(
            "ffprobe was not found on PATH. Install FFmpeg (which bundles ffprobe) "
            "to use event-recording-auditor."
        )
    return path


@dataclass
class MediaInfo:
    """Normalized view over the parts of ffprobe output this project uses."""

    path: str
    duration: float
    format_name: str
    bitrate: int | None
    video_streams: list[dict[str, Any]] = field(default_factory=list)
    audio_streams: list[dict[str, Any]] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def has_video(self) -> bool:
        return len(self.video_streams) > 0

    @property
    def has_audio(self) -> bool:
        return len(self.audio_streams) > 0

    @property
    def primary_video(self) -> dict[str, Any] | None:
        return self.video_streams[0] if self.video_streams else None

    @property
    def frame_rate(self) -> float | None:
        v = self.primary_video
        if not v:
            return None
        rate = v.get("avg_frame_rate") or v.get("r_frame_rate")
        if not rate or rate == "0/0":
            return None
        num, _, den = rate.partition("/")
        try:
            num_f, den_f = float(num), float(den or 1)
            return num_f / den_f if den_f else None
        except ValueError:
            return None

    @property
    def resolution(self) -> tuple[int, int] | None:
        v = self.primary_video
        if not v or "width" not in v or "height" not in v:
            return None
        return int(v["width"]), int(v["height"])


def probe(path: str | Path, timeout: float = 60.0) -> MediaInfo:
    """Run ffprobe on `path` and return normalized MediaInfo.

    Raises FFprobeError if the file cannot be probed (missing, corrupt,
    unsupported container). Callers should surface this as "insufficient
    evidence" rather than guessing.
    """
    path = str(path)
    exe = _ffprobe_bin()
    cmd = [
        exe,
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        path,
    ]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, check=False
        )
    except subprocess.TimeoutExpired as exc:
        raise FFprobeError(f"ffprobe timed out probing {path!r}") from exc

    if proc.returncode != 0:
        raise FFprobeError(
            f"ffprobe failed on {path!r} (exit {proc.returncode}): {proc.stderr.strip()}"
        )

    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise FFprobeError(f"ffprobe returned unparsable output for {path!r}") from exc

    fmt = data.get("format", {})
    streams = data.get("streams", [])
    video_streams = [s for s in streams if s.get("codec_type") == "video"]
    audio_streams = [s for s in streams if s.get("codec_type") == "audio"]

    duration_raw = fmt.get("duration")
    try:
        duration = float(duration_raw) if duration_raw is not None else 0.0
    except ValueError:
        duration = 0.0

    bitrate_raw = fmt.get("bit_rate")
    bitrate = int(bitrate_raw) if bitrate_raw is not None else None

    return MediaInfo(
        path=path,
        duration=duration,
        format_name=fmt.get("format_name", ""),
        bitrate=bitrate,
        video_streams=video_streams,
        audio_streams=audio_streams,
        raw=data,
    )
