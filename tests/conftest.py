from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "examples"))

import generate_synthetic_fixtures as gen  # noqa: E402


def _require_ffmpeg():
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("ffmpeg/ffprobe not available in this environment")


@pytest.fixture(scope="session")
def fixtures_dir(tmp_path_factory) -> Path:
    _require_ffmpeg()
    out_dir = tmp_path_factory.mktemp("erafixtures")
    gen.generate_all(out_dir)
    return out_dir


@pytest.fixture(scope="session")
def blackout_clip(fixtures_dir) -> str:
    return str(fixtures_dir / "blackout.mp4")


@pytest.fixture(scope="session")
def silence_gap_audio(fixtures_dir) -> str:
    return str(fixtures_dir / "silence_gap.wav")


@pytest.fixture(scope="session")
def clipped_audio(fixtures_dir) -> str:
    return str(fixtures_dir / "clipped.wav")


@pytest.fixture(scope="session")
def normal_tone_audio(fixtures_dir) -> str:
    return str(fixtures_dir / "normal_tone.wav")


@pytest.fixture(scope="session")
def premature_slide_advance_clip(fixtures_dir) -> str:
    return str(fixtures_dir / "premature_slide_advance.mp4")


@pytest.fixture(scope="session")
def title_slide_missed_clip(fixtures_dir) -> str:
    return str(fixtures_dir / "title_slide_missed.mp4")


@pytest.fixture(scope="session")
def quiet_static_clip(fixtures_dir) -> str:
    return str(fixtures_dir / "quiet_static.mp4")


@pytest.fixture(scope="session")
def continuously_changing_clip(fixtures_dir) -> str:
    return str(fixtures_dir / "continuously_changing.mp4")


@pytest.fixture(scope="session")
def portrait_cutaway_clip(fixtures_dir) -> str:
    return str(fixtures_dir / "portrait_cutaway.mp4")


@pytest.fixture(scope="session")
def channel_dropout_audio(fixtures_dir) -> str:
    return str(fixtures_dir / "channel_dropout.wav")


@pytest.fixture(scope="session")
def channel_balanced_audio(fixtures_dir) -> str:
    return str(fixtures_dir / "channel_balanced.wav")
