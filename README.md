# Event Recording Auditor

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

Investigate a "the edited footage looks worse" complaint by comparing an
original source file against an exported/edited delivery file:

```bash
event-recording-auditor compare SOURCE.mp4 EXPORT.mp4 --out-dir audit-output
```

See [`SKILL.md`](SKILL.md) for the full Agent-facing workflow, including
when to ask for additional reference data (expected slide order, switching
plan, delivery spec) and how to phrase findings responsibly.

## What's implemented today

| Category | Detectors |
|---|---|
| Video (Tier 1) | Blackout, freeze (audio-correlated) |
| Audio (Tier 1/2) | Clipping, channel imbalance/missing-channel, context-aware possible audio dropout |
| Presentation (Tier 2) | Slide rollback pattern (the `1 -> 2 -> 1 -> 2` core use case), brief unexpected slide |
| Progress (Tier 2) | Progression interruption (camera + audio + slide correlation) |
| Audio (Tier 3, experimental, opt-in) | Possible feedback/howling |
| Post-production | Source-vs-export metadata diff + SSIM/PSNR comparison |

See [`docs/detection-model.md`](docs/detection-model.md) for the full
picture, including what's deliberately not implemented yet and why.

## Development

```bash
pip install -e ".[dev]"
pytest
```

Tests generate their own small synthetic media fixtures via
[`examples/generate_synthetic_fixtures.py`](examples/generate_synthetic_fixtures.py)
(ffmpeg `lavfi` sources) rather than committing binary test media.

## Documentation

- [`docs/architecture.md`](docs/architecture.md) -- pipeline, module map, dependency rationale.
- [`docs/detection-model.md`](docs/detection-model.md) -- severity/confidence model, detector tiers, what's implemented.
- [`docs/event-schema.md`](docs/event-schema.md) -- the `Event` schema every detector emits.
- [`docs/false-positives.md`](docs/false-positives.md) -- false-positive classes and mitigations.
- [`docs/research.md`](docs/research.md) -- prior art / competitive landscape review.

## License

MIT -- see [`LICENSE`](LICENSE).
