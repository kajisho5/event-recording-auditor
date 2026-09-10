from pathlib import Path

from event_recording_auditor.pipeline import run_pipeline
from event_recording_auditor.reporting import (
    write_html_report,
    write_json_report,
    write_markdown_report,
)


def test_pipeline_runs_full_profile_and_writes_reports(premature_slide_advance_clip, tmp_path):
    result = run_pipeline(
        premature_slide_advance_clip,
        profile="full",
        evidence_dir=tmp_path / "evidence",
        min_severity_for_evidence="low",
    )

    assert len(result.timeline) >= 1
    assert any(e.type == "slide_rollback_pattern" for e in result.timeline)
    # No audio track in this fixture -> audio-only detectors should be
    # recorded as skipped, not silently dropped.
    assert any("skipped" in note for note in result.limitations)

    media_summary = {
        "path": result.context.source,
        "duration": result.context.media_info.duration,
    }
    json_path = write_json_report(result.timeline, media_summary, tmp_path / "report.json")
    html_path = write_html_report(result.timeline, media_summary, tmp_path / "report.html")
    md_path = write_markdown_report(
        result.timeline, media_summary, tmp_path / "report.md", result.limitations
    )

    assert json_path.exists()
    assert html_path.exists()
    assert "slide_rollback_pattern" in html_path.read_text()

    md_text = md_path.read_text()
    assert "slide_rollback_pattern" in md_text
    assert "| Time | Duration | Category | Severity | Confidence | Type |" in md_text
    assert "## Limitations" in md_text


def test_pipeline_reports_render_in_japanese(premature_slide_advance_clip, tmp_path):
    result = run_pipeline(premature_slide_advance_clip, profile="presentation")
    media_summary = {
        "path": result.context.source,
        "duration": result.context.media_info.duration,
    }

    md_path = write_markdown_report(result.timeline, media_summary, tmp_path / "report.md", language="ja")
    html_path = write_html_report(result.timeline, media_summary, tmp_path / "report.html", language="ja")

    md_text = md_path.read_text()
    assert "収録監査レポート" in md_text
    # the machine-readable type identifier is never translated
    assert "slide_rollback_pattern" in md_text
    assert "Consistent with a premature slide advance" not in md_text

    html_text = html_path.read_text()
    assert 'lang="ja"' in html_text
    assert "収録監査レポート" in html_text


def test_pipeline_populates_evidence_for_qualifying_events(premature_slide_advance_clip, tmp_path):
    result = run_pipeline(
        premature_slide_advance_clip,
        profile="presentation",
        evidence_dir=tmp_path / "evidence",
        min_severity_for_evidence="low",
    )
    assert len(result.timeline) >= 1
    for event in result.timeline:
        assert "event_frame" in event.evidence
        assert Path(event.evidence["event_frame"]).exists()
