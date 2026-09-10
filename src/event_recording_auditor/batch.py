"""Batch processing: run the single-file pipeline over many independent
recordings (e.g. one file per venue for a multi-venue event day)
concurrently.

This is deliberately cross-file (process-level) parallelism, not
within-file chunking. The files have no dependency on each other, so
running N of them at once is the simple, safe kind of parallelism: no
detector's boundary logic (a freeze/slide-state run, an audio-dropout
context window, a progression-interruption bucket) risks being split
across a chunk seam, which chunking a single long recording would risk.
See docs/architecture.md, "Batch processing", for the reasoning and the
throughput this is based on.
"""

from __future__ import annotations

import os
import re
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

from .pipeline import run_pipeline
from .reporting import write_html_report, write_json_report, write_markdown_report


def _slugify(name: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("_")
    return slug or "recording"


def _unique_slug(base: str, used: set[str]) -> str:
    slug = base
    i = 2
    while slug in used:
        slug = f"{base}-{i}"
        i += 1
    used.add(slug)
    return slug


@dataclass
class BatchJob:
    """Plain-data description of one venue's job, safe to pickle across
    the process-pool boundary (must not carry any live objects)."""

    source: str
    slug: str
    out_dir: str
    profile: str
    include_feedback_experimental: bool
    no_evidence: bool
    min_severity_for_evidence: str
    lang: str


@dataclass
class BatchJobResult:
    source: str
    slug: str
    ok: bool
    error: str | None = None
    duration: float | None = None
    total_findings: int = 0
    by_severity: dict[str, int] = field(default_factory=dict)
    limitations: list[str] = field(default_factory=list)
    report_json: str | None = None
    report_html: str | None = None
    report_md: str | None = None


def _run_one_job(job: BatchJob) -> BatchJobResult:
    """Runs in a worker process. Must never raise: one venue failing (a
    corrupt file, an unreadable path) is reported as a per-venue error in
    the batch index, not a crash that loses every other venue's results.
    """
    try:
        venue_dir = Path(job.out_dir) / job.slug
        evidence_dir = None if job.no_evidence else venue_dir / "evidence"

        result = run_pipeline(
            job.source,
            profile=job.profile,
            include_feedback_experimental=job.include_feedback_experimental,
            evidence_dir=evidence_dir,
            min_severity_for_evidence=job.min_severity_for_evidence,
        )
        media_summary = {
            "path": result.context.source,
            "duration": result.context.media_info.duration,
            "has_video": result.context.media_info.has_video,
            "has_audio": result.context.media_info.has_audio,
            "resolution": result.context.media_info.resolution,
            "frame_rate": result.context.media_info.frame_rate,
        }
        json_path = write_json_report(
            result.timeline,
            media_summary,
            venue_dir / "report.json",
            result.limitations,
        )
        html_path = write_html_report(
            result.timeline,
            media_summary,
            venue_dir / "report.html",
            result.limitations,
            language=job.lang,
        )
        md_path = write_markdown_report(
            result.timeline,
            media_summary,
            venue_dir / "report.md",
            result.limitations,
            language=job.lang,
        )
        summary = result.timeline.summary()
        return BatchJobResult(
            source=job.source,
            slug=job.slug,
            ok=True,
            duration=result.context.media_info.duration,
            total_findings=summary["total_events"],
            by_severity=summary["by_severity"],
            limitations=result.limitations,
            report_json=str(json_path),
            report_html=str(html_path),
            report_md=str(md_path),
        )
    except Exception as exc:  # noqa: BLE001 - one venue's failure must not sink the batch
        return BatchJobResult(source=job.source, slug=job.slug, ok=False, error=str(exc))


def run_batch(
    sources: list[str],
    out_dir: str,
    profile: str = "full",
    include_feedback_experimental: bool = False,
    no_evidence: bool = False,
    min_severity_for_evidence: str = "medium",
    lang: str = "en",
    concurrency: int | None = None,
) -> list[BatchJobResult]:
    """Analyze every file in `sources` concurrently, each into its own
    `out_dir/<slug>/` subdirectory. Returns results in the same order as
    `sources` regardless of completion order.

    `concurrency` defaults to min(number of files, CPU count) -- running
    more workers than either doesn't help (each job is CPU-bound on
    ffmpeg decode) and just adds contention.
    """
    if not sources:
        return []

    Path(out_dir).mkdir(parents=True, exist_ok=True)

    used_slugs: set[str] = set()
    jobs: list[BatchJob] = []
    for source in sources:
        base = _slugify(Path(source).stem)
        slug = _unique_slug(base, used_slugs)
        jobs.append(
            BatchJob(
                source=source,
                slug=slug,
                out_dir=out_dir,
                profile=profile,
                include_feedback_experimental=include_feedback_experimental,
                no_evidence=no_evidence,
                min_severity_for_evidence=min_severity_for_evidence,
                lang=lang,
            )
        )

    max_workers = max(1, concurrency or min(len(jobs), os.cpu_count() or 4))

    results_by_source: dict[str, BatchJobResult] = {}
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_run_one_job, job): job for job in jobs}
        for future in as_completed(futures):
            job = futures[future]
            try:
                result = future.result()
            except Exception as exc:  # noqa: BLE001 - a worker crash is still one venue's failure
                result = BatchJobResult(source=job.source, slug=job.slug, ok=False, error=str(exc))
            results_by_source[job.source] = result

    return [results_by_source[source] for source in sources]
