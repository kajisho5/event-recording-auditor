"""Shared subprocess helper for invoking the `ffmpeg` binary.

Centralized here so every detector/extractor shells out the same way and
raises the same error type on failure.
"""

from __future__ import annotations

import shutil
import subprocess


class FFmpegNotFoundError(RuntimeError):
    pass


class FFmpegError(RuntimeError):
    pass


def ffmpeg_bin() -> str:
    path = shutil.which("ffmpeg")
    if not path:
        raise FFmpegNotFoundError(
            "ffmpeg was not found on PATH. Install FFmpeg to use "
            "event-recording-auditor's detectors."
        )
    return path


def run_ffmpeg(
    args: list[str], timeout: float | None = None, check_returncode: bool = False
) -> subprocess.CompletedProcess:
    """Run ffmpeg with the given args (excluding the binary itself).

    Most ffmpeg analysis filters (blackdetect, freezedetect, silencedetect,
    astats) print their findings to stderr regardless of exit code, so by
    default we do not raise on nonzero exit -- callers inspect stderr and
    decide. Pass check_returncode=True for extraction calls where a nonzero
    exit really does mean failure.
    """
    cmd = [ffmpeg_bin(), *args]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, check=False
        )
    except subprocess.TimeoutExpired as exc:
        raise FFmpegError(f"ffmpeg timed out: {' '.join(cmd)}") from exc

    if check_returncode and proc.returncode != 0:
        raise FFmpegError(
            f"ffmpeg failed (exit {proc.returncode}): {' '.join(cmd)}\n{proc.stderr}"
        )
    return proc


def run_ffmpeg_binary(
    args: list[str], timeout: float | None = None
) -> tuple[bytes, str, int]:
    """Like run_ffmpeg, but returns raw stdout bytes (for rawvideo/PCM pipes)
    alongside decoded stderr text and the return code.
    """
    cmd = [ffmpeg_bin(), *args]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, timeout=timeout, check=False
        )
    except subprocess.TimeoutExpired as exc:
        raise FFmpegError(f"ffmpeg timed out: {' '.join(cmd)}") from exc
    stderr_text = proc.stderr.decode("utf-8", errors="replace")
    return proc.stdout, stderr_text, proc.returncode
