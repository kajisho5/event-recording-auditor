# Event Recording Auditor

> **Beta.** Runs fully locally (no network calls -- see "Requirements"
> below; the only hard dependency is the `ffmpeg`/`ffprobe` binaries).
> What's been validated so far: false-positive behavior against a small
> number of real (non-synthetic) recordings, which surfaced and fixed two
> real bugs (see `docs/false-positives.md`). What has **not** been
> validated: detection rate/recall -- whether this actually catches real
> production incidents -- has only been exercised against synthetic test
> fixtures with known-injected anomalies, never against real footage with
> a known, confirmed problem. Treat every finding as a candidate for human
> review, not a confirmed issue, per the design principle below.

Deterministic, evidence-first analysis of recorded event footage
(conferences, seminars, webinars, lectures, hybrid events). It analyzes a
recording as a timeline of production signals -- video, audio,
presentation state -- and reports **anomaly candidates** with evidence and
a timestamp, so a human reviewer can spend less time scrubbing through
footage and more time verifying the moments that actually need it.

This is not an "AI watches a video and guesses what went wrong" system. It
is built on deterministic FFmpeg-based measurement first, with rule-based
correlation on top -- see [`docs/architecture.md`](docs/architecture.md).

**What this does not do:** replace human review, claim to know operator
intent, or assert a finding as fact when the evidence only supports a
hedged candidate. See [`docs/detection-model.md`](docs/detection-model.md)
and [`docs/false-positives.md`](docs/false-positives.md) for exactly what
is and isn't reliable today.

## Requirements

- Python 3.10+
- `ffmpeg` / `ffprobe` on `PATH`
- `numpy` (optional, only for the experimental feedback/howling detector)

## Install

```bash
pip install -e .
# or, for the experimental feedback detector too:
pip install -e ".[feedback]"
```

Or use the prebuilt Docker image (ffmpeg included, nothing else to
install) -- published to GHCR on every tagged release:

```bash
docker run --rm -v "$PWD":/data ghcr.io/kajisho5/event-recording-auditor:latest \
  analyze /data/recording.mp4 --out-dir /data/audit-output
```

`:latest` tracks the newest non-beta release; pin a specific version
(e.g. `:v0.1.0-beta`) for reproducibility.

## Usage

Audit a recording for in-event production incidents:

```bash
event-recording-auditor analyze RECORDING.mp4 --out-dir audit-output
```

Writes `audit-output/report.json`, `audit-output/report.html`,
`audit-output/report.md` (a plain-text/Markdown version with the same
timeline table and per-finding detail -- easy to paste into a chat or
ticket), and (unless
`--no-evidence` is passed) `audit-output/evidence/incident-NNNN/` packages
for each significant finding.

Add `--lang ja` to get `report.html`/`report.md` in Japanese (English is
the default, and the only option today besides Japanese). `report.json`
is always English -- it's the stable machine-readable format. Only the
report's prose (structural labels, and each finding's observations/
interpretation) is translated; the technical `type` identifier (e.g.
`slide_rollback_pattern`) is never translated, since it's a stable
identifier documented in `docs/detection-model.md`. The free-text
`limitations` notes (e.g. "Detector 'clipping' skipped: ...") are also
not yet translated -- see `docs/architecture.md`, "Localization".

Investigate a "the edited footage looks worse" complaint by comparing an
original source file against an exported/edited delivery file:

```bash
event-recording-auditor compare SOURCE.mp4 EXPORT.mp4 --out-dir audit-output
```

Audit several independent recordings at once (e.g. one file per venue for
a multi-venue event day) with the same options as `analyze`, run
concurrently:

```bash
event-recording-auditor batch venue1.mp4 venue2.mp4 venue3.mp4 \
  --out-dir day-audit --concurrency 4
```

Writes `day-audit/<venue>/report.{json,html,md}` per file plus a top-level
`day-audit/index.{md,html}` summarizing every venue's finding counts with
links into each one's report. `--concurrency` defaults to
`min(file count, CPU count)` -- each file is processed in its own worker
process, since the files are fully independent (this is cross-file
parallelism, not splitting one long recording into chunks; see
`docs/architecture.md`, "Batch processing", for why that distinction
matters). A file that fails to analyze (unreadable, corrupt) is recorded
as an error for that one venue in the index rather than aborting the rest
of the batch.

See [`SKILL.md`](SKILL.md) for the full Agent-facing workflow, including
when to ask for additional reference data (expected slide order, switching
plan, delivery spec) and how to phrase findings responsibly.

## Example output

Real `report.md` output (unedited) from running `analyze` against the
`premature_slide_advance` synthetic fixture used in the test suite
(`examples/generate_synthetic_fixtures.py`) -- a slide held for 3s, briefly
advanced for 0.5s, rolled back for 2s, then advanced again for 3s:

```
# Event Recording Audit

**File:** `premature_slide_advance.mp4`
**Duration:** 00:00:08.500
**Total findings:** 4 (high: 0, medium: 4, low: 0)

## Timeline

| Time | Duration | Category | Severity | Confidence | Type |
|---|---|---|---|---|---|
| 00:00:00.000 - 00:00:03.000 | 3.00s | video | medium | medium | freeze |
| 00:00:03.000 - 00:00:03.500 | 0.50s | presentation | medium | low | brief_unexpected_slide |
| 00:00:03.000 - 00:00:05.500 | 2.50s | presentation | medium | medium | slide_rollback_pattern |
| 00:00:03.500 - 00:00:05.500 | 2.00s | video | medium | medium | freeze |
```

The core use case's finding, in full:

```
### 00:00:03.000 - 00:00:05.500 (2.50s) -- MEDIUM / slide_rollback_pattern

- **Category**: presentation
- **Confidence**: medium
- **Detector**: slide_rollback_pattern

**Observed:**
- Slide state 0 was displayed for 3.00s.
- Slide state 1 then appeared for 0.50s.
- The recording returned to slide state 0 for 2.00s.
- Slide state 1 appeared again afterward, this time for 3.00s.

**Possible interpretation:** Consistent with a premature slide advance
followed by an operator/presenter correction: the first appearance of the
later slide was brief compared to its return.

**Human verification required.**

**Evidence:** [before_frame](...) · [event_frame](...) · [after_frame](...)
· [clip](...) · [metadata](...) · [explanation](...)
```

Each finding also links to an `evidence/incident-NNNN/` package (before/
event/after frame stills, a short clip, and metadata) so a reviewer can
verify without re-scrubbing the full recording. Note the two `freeze`
findings alongside the slide finding: this is a static-camera synthetic
clip with no audio, so the frozen-video detector fires on the same
intervals for a different reason -- a real correlated freeze/audio-dropout
incident would look different in practice, and is exactly the kind of
overlap a human reviewer is meant to resolve, per the "what this does not
do" note above.

## What's implemented today

| Category | Detectors |
|---|---|
| Video (Tier 1) | Blackout, freeze (audio-correlated) |
| Audio (Tier 1/2) | Clipping, channel imbalance/missing-channel, context-aware possible audio dropout |
| Presentation (Tier 2) | Slide rollback pattern (an `A -> B -> A` revisit, e.g. `1 -> 2 -> 1 -> 2` or, just as commonly, `2 -> 1 -> 2` when a camera cutaway hides the presenter advancing past the title slide), brief unexpected slide |
| Progress (Tier 2) | Progression interruption (camera + audio + slide correlation) |
| Audio (Tier 3, experimental, opt-in) | Possible feedback/howling |
| Post-production | Source-vs-export metadata diff + SSIM/PSNR comparison |

See [`docs/detection-model.md`](docs/detection-model.md) for the full
picture, including what's deliberately not implemented yet and why.

## Development

```bash
pip install -e ".[dev]"
pytest
ruff check src/ tests/ examples/    # lint
ruff format src/ tests/ examples/   # apply formatting (or --check to only verify)
```

Both `pytest` and `ruff check`/`ruff format --check` run in CI
(`.github/workflows/tests.yml`) on every push and PR. Tests generate their
own small synthetic media fixtures via
[`examples/generate_synthetic_fixtures.py`](examples/generate_synthetic_fixtures.py)
(ffmpeg `lavfi` sources) rather than committing binary test media.
[Dependabot](.github/dependabot.yml) opens weekly update PRs for GitHub
Actions versions and Python dependencies.

### Releasing a version

The usual path: bump `version` in `pyproject.toml` in a PR (e.g.
`"0.1.0-beta"` -> `"0.2.0"`) and merge it to `main`. Everything after that
is automatic:

1. `.github/workflows/tag-on-version-bump.yml` notices the version string
   changed and pushes a `v<version>` tag.
2. That tag push triggers `.github/workflows/release.yml`, which creates
   the GitHub Release with auto-generated notes (from the commits/PRs
   merged since the previous tag -- never hand-written) and prepends an
   entry to [`CHANGELOG.md`](CHANGELOG.md). A tag with a hyphen (e.g.
   `v0.1.0-beta`, semver's pre-release convention) is published as a
   pre-release.
3. The same tag push triggers `.github/workflows/docker.yml`, which
   builds and pushes the image to
   `ghcr.io/kajisho5/event-recording-auditor`, moving the `:latest` tag
   only for non-pre-release versions.

To publish a version without going through a version-bump PR (e.g. to tag
an existing commit), push the tag directly instead and steps 2-3 above
still fire the same way:

```bash
git tag v0.1.0-beta
git push origin v0.1.0-beta
```

## Documentation

- [`docs/architecture.md`](docs/architecture.md) -- pipeline, module map, dependency rationale.
- [`docs/detection-model.md`](docs/detection-model.md) -- severity/confidence model, detector tiers, what's implemented.
- [`docs/event-schema.md`](docs/event-schema.md) -- the `Event` schema every detector emits.
- [`docs/false-positives.md`](docs/false-positives.md) -- false-positive classes and mitigations.
- [`docs/research.md`](docs/research.md) -- prior art / competitive landscape review.
- [`CHANGELOG.md`](CHANGELOG.md) -- auto-generated on every release.

## License

MIT -- see [`LICENSE`](LICENSE).
