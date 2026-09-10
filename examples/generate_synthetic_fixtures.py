"""Generate small synthetic media files for tests and manual experimentation.

Every fixture here is built from ffmpeg `lavfi` sources (color/tone
generators) so no binary media needs to be committed to the repository
(see spec section 18, "Testing Strategy"). Run directly to populate a
directory:

    python examples/generate_synthetic_fixtures.py /tmp/erafixtures

`tests/conftest.py` calls these same functions to build fixtures on demand
for the test suite.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _run(*args: str) -> None:
    subprocess.run(["ffmpeg", "-y", *args, "-loglevel", "error"], check=True)


def make_blackout_clip(out_path: Path) -> Path:
    """3s blue, 1s black, 2s blue: an accidental-looking mid-clip blackout."""
    tmp = out_path.parent
    a, b, c = tmp / "_a.mp4", tmp / "_b.mp4", tmp / "_c.mp4"
    _run("-f", "lavfi", "-i", "color=c=blue:s=320x240:d=3:r=4,format=yuv420p", str(a))
    _run("-f", "lavfi", "-i", "color=c=black:s=320x240:d=1:r=4,format=yuv420p", str(b))
    _run("-f", "lavfi", "-i", "color=c=blue:s=320x240:d=2:r=4,format=yuv420p", str(c))
    _run(
        "-i", str(a), "-i", str(b), "-i", str(c),
        "-filter_complex", "[0:v][1:v][2:v]concat=n=3:v=1:a=0[v]",
        "-map", "[v]", str(out_path),
    )
    for f in (a, b, c):
        f.unlink(missing_ok=True)
    return out_path


def make_silence_gap_audio(out_path: Path) -> Path:
    """2s tone, 1s silence, 2s tone: a silence gap surrounded by activity."""
    _run(
        "-f", "lavfi", "-i", "sine=frequency=440:duration=2:sample_rate=16000",
        "-f", "lavfi", "-i", "anullsrc=r=16000:cl=mono:d=1",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=2:sample_rate=16000",
        "-filter_complex", "[0:a][1:a][2:a]concat=n=3:v=0:a=1[a]",
        "-map", "[a]", str(out_path),
    )
    return out_path


def make_clipped_audio(out_path: Path) -> Path:
    """A sine tone amplified past 0 dBFS so it hard-clips."""
    _run(
        "-f", "lavfi", "-i", "sine=frequency=440:duration=2:sample_rate=16000",
        "-af", "volume=10", str(out_path),
    )
    return out_path


def make_normal_tone_audio(out_path: Path) -> Path:
    """An unclipped sine tone, for false-positive checks."""
    _run(
        "-f", "lavfi", "-i", "sine=frequency=440:duration=2:sample_rate=16000",
        str(out_path),
    )
    return out_path


def make_channel_dropout_audio(out_path: Path) -> Path:
    """Stereo audio with the right channel silent throughout -- a dropped mic/channel."""
    _run(
        "-f", "lavfi", "-i", "sine=frequency=440:duration=2:sample_rate=16000",
        "-f", "lavfi", "-i", "anullsrc=r=16000:cl=mono:d=2",
        "-filter_complex", "[0:a][1:a]amerge=inputs=2[a]",
        "-map", "[a]", "-ac", "2", str(out_path),
    )
    return out_path


def make_channel_balanced_audio(out_path: Path) -> Path:
    """Balanced stereo audio, for false-positive checks."""
    _run(
        "-f", "lavfi", "-i", "sine=frequency=440:duration=2:sample_rate=16000",
        "-ac", "2", str(out_path),
    )
    return out_path


def make_premature_slide_advance_clip(out_path: Path) -> Path:
    """The spec's core use case: slide A (3s) -> B (0.5s, brief) -> A (2s) -> B (3s).

    Uses visually distinct blocks (not just flat colors) so the perceptual
    hash can actually tell the two "slides" apart -- see
    docs/detection-model.md for why a flat-color test would be degenerate.
    """
    tmp = out_path.parent
    parts = [
        (tmp / "_a1.mp4", "drawbox=x=20:y=20:w=120:h=90:color=blue@1.0:t=fill,drawtext=text='Title A':fontsize=24:fontcolor=black:x=160:y=30", 3),
        (tmp / "_b1.mp4", "drawbox=x=180:y=130:w=120:h=90:color=orange@1.0:t=fill,drawtext=text='Title B':fontsize=24:fontcolor=black:x=20:y=200", 0.5),
        (tmp / "_a2.mp4", "drawbox=x=20:y=20:w=120:h=90:color=blue@1.0:t=fill,drawtext=text='Title A':fontsize=24:fontcolor=black:x=160:y=30", 2),
        (tmp / "_b2.mp4", "drawbox=x=180:y=130:w=120:h=90:color=orange@1.0:t=fill,drawtext=text='Title B':fontsize=24:fontcolor=black:x=20:y=200", 3),
    ]
    for path, vf, duration in parts:
        _run(
            "-f", "lavfi", "-i", f"color=c=white:s=320x240:d={duration}:r=4,format=yuv420p",
            "-vf", vf, str(path),
        )
    inputs = []
    for path, _, _ in parts:
        inputs += ["-i", str(path)]
    n = len(parts)
    filter_inputs = "".join(f"[{i}:v]" for i in range(n))
    _run(
        *inputs,
        "-filter_complex", f"{filter_inputs}concat=n={n}:v=1:a=0[v]",
        "-map", "[v]", str(out_path),
    )
    for path, _, _ in parts:
        path.unlink(missing_ok=True)
    return out_path


def make_continuously_changing_clip(out_path: Path, duration: float = 5.0) -> Path:
    """Video that changes every frame, standing in for "ordinary" (non-slide)
    footage such as camera work or broadcast content -- used to check that
    presentation detectors don't flood a report on non-slide input. Real
    validation for this came from testing against an actual TV clip, which
    is not something this repo can commit as a fixture."""
    _run(
        "-f", "lavfi", "-i", f"mandelbrot=size=320x240:rate=4",
        "-t", str(duration), str(out_path),
    )
    return out_path


def make_quiet_static_clip(out_path: Path, duration: float = 40.0) -> Path:
    """A long static, silent clip: a progression-interruption candidate."""
    _run(
        "-f", "lavfi", "-i", f"color=c=gray:s=320x240:d={duration}:r=2,format=yuv420p",
        "-f", "lavfi", "-i", f"anullsrc=r=16000:cl=mono:d={duration}",
        "-shortest", str(out_path),
    )
    return out_path


def generate_all(out_dir: Path) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    return {
        "blackout": make_blackout_clip(out_dir / "blackout.mp4"),
        "silence_gap": make_silence_gap_audio(out_dir / "silence_gap.wav"),
        "clipped": make_clipped_audio(out_dir / "clipped.wav"),
        "normal_tone": make_normal_tone_audio(out_dir / "normal_tone.wav"),
        "channel_dropout": make_channel_dropout_audio(out_dir / "channel_dropout.wav"),
        "channel_balanced": make_channel_balanced_audio(out_dir / "channel_balanced.wav"),
        "premature_slide_advance": make_premature_slide_advance_clip(
            out_dir / "premature_slide_advance.mp4"
        ),
        "quiet_static": make_quiet_static_clip(out_dir / "quiet_static.mp4"),
        "continuously_changing": make_continuously_changing_clip(
            out_dir / "continuously_changing.mp4"
        ),
    }


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("fixtures")
    generated = generate_all(target)
    for name, path in generated.items():
        print(f"{name}: {path}")
