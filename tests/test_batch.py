from pathlib import Path

from event_recording_auditor.batch import run_batch


def test_run_batch_processes_multiple_files_independently(
    premature_slide_advance_clip, blackout_clip, tmp_path
):
    results = run_batch(
        [premature_slide_advance_clip, blackout_clip],
        out_dir=str(tmp_path),
        profile="presentation",
        concurrency=2,
    )

    assert len(results) == 2
    # order is preserved regardless of which job finishes first
    assert results[0].source == premature_slide_advance_clip
    assert results[1].source == blackout_clip

    slide_result = results[0]
    assert slide_result.ok
    assert slide_result.total_findings >= 1
    assert Path(slide_result.report_md).exists()
    assert Path(slide_result.report_html).exists()
    assert Path(slide_result.report_json).exists()

    # each venue gets its own subdirectory, not a shared output path
    assert Path(slide_result.report_md).parent != Path(results[1].report_md).parent


def test_run_batch_isolates_a_failing_file(premature_slide_advance_clip, tmp_path):
    missing = str(tmp_path / "does_not_exist.mp4")
    results = run_batch(
        [premature_slide_advance_clip, missing],
        out_dir=str(tmp_path / "out"),
        profile="presentation",
        concurrency=2,
    )

    assert len(results) == 2
    ok_result = next(r for r in results if r.source == premature_slide_advance_clip)
    failed_result = next(r for r in results if r.source == missing)

    assert ok_result.ok is True
    assert failed_result.ok is False
    assert failed_result.error is not None


def test_run_batch_deduplicates_slugs_for_same_basename(premature_slide_advance_clip, tmp_path):
    # two different paths that happen to share a basename after slugifying
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    import shutil

    shutil.copy(premature_slide_advance_clip, a / "clip.mp4")
    shutil.copy(premature_slide_advance_clip, b / "clip.mp4")

    results = run_batch(
        [str(a / "clip.mp4"), str(b / "clip.mp4")],
        out_dir=str(tmp_path / "out"),
        profile="presentation",
        concurrency=2,
    )
    assert len(results) == 2
    assert results[0].ok and results[1].ok
    assert Path(results[0].report_md).parent != Path(results[1].report_md).parent
