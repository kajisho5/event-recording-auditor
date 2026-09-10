import shutil
import subprocess

import pytest

from event_recording_auditor.postproduction import compare_source_and_export


def _require_ffmpeg():
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg not available")


@pytest.fixture(scope="module")
def source_and_exports(tmp_path_factory):
    _require_ffmpeg()
    out = tmp_path_factory.mktemp("postprod")
    source = out / "source.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=size=320x240:rate=5:duration=2",
         str(source)],
        check=True, capture_output=True,
    )
    good_export = out / "export_good.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(source), "-vf", "scale=160:120",
         "-c:v", "libx264", "-crf", "18", str(good_export)],
        check=True, capture_output=True,
    )
    bad_export = out / "export_bad.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(source), "-vf", "scale=160:120",
         "-c:v", "libx264", "-b:v", "3k", str(bad_export)],
        check=True, capture_output=True,
    )
    return str(source), str(good_export), str(bad_export)


def test_mild_conversion_is_not_flagged_as_downstream_degradation(source_and_exports):
    source, good_export, _ = source_and_exports
    result = compare_source_and_export(source, good_export)
    assert result.conclusion.value == "source_degradation_already_present"
    assert "resolution" in result.metadata_diff.changed_fields


def test_heavy_compression_is_flagged_as_downstream_degradation(source_and_exports):
    source, _, bad_export = source_and_exports
    result = compare_source_and_export(source, bad_export)
    assert result.conclusion.value == "additional_downstream_degradation"
    assert result.quality.ssim_avg < 0.92
