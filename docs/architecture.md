# Architecture

## Pipeline

```text
Recording (+ optional reference files)
        |
        v
AnalysisContext  (media/ffprobe.py, audio/levels.py, slides/phash.py)
        |  -- probes the file once, lazily computes and caches:
        |     - windowed audio level envelope (RMS/peak/flat-factor)
        |     - low-res frame-hash sample sequence (video)
        |     - clustered slide-state timeline (derived from the above)
        v
Detectors (detectors/*.py)
        |  -- each takes the shared context and returns Event objects
        |     (see docs/event-schema.md); never raises on "nothing found"
        v
Timeline (timeline/builder.py)
        |  -- sorted, de-duplicated collection of Events
        v
Evidence extraction (evidence/extractor.py)   [optional, per event]
        |  -- before/event/after frames + a short clip, from the
        |     original file only, never modifying it
        v
Reports (reporting/{json,html}_report.py)
```

A second, independent pipeline (`postproduction/`) implements the
source-vs-export investigation (spec sections 26-27): it takes two files
instead of one and produces a `ComparisonResult` rather than a `Timeline`.
It is exposed via the same CLI (`event-recording-auditor compare ...`) but
does not share detector infrastructure with the single-file pipeline,
since it's a fundamentally different comparison, not an anomaly scan.

## Module map

| Module | Responsibility |
|---|---|
| `media/` | ffprobe wrapper, frame/clip extraction. The only place that shells out for basic media I/O. |
| `video/` | Thin wrappers over ffmpeg's `blackdetect`/`freezedetect` filters. |
| `audio/` | `silencedetect` wrapper, `astats`-based windowed level envelope, clipping detection built on that envelope. |
| `slides/` | Frame sampling + a pure-Python average-hash, segment clustering, and slide-state timeline construction (state IDs that survive a return to an earlier slide). |
| `timeline/` | The `Event` schema and `Timeline` collection -- see docs/event-schema.md. |
| `detectors/` | One class per anomaly type; shares an `AnalysisContext` for expensive intermediate data. |
| `evidence/` | Turns a significant `Event` into an `incident-NNNN/` evidence package. |
| `reporting/` | `report.json`, `report.html`, and `report.md` generation. |
| `postproduction/` | Source-vs-export metadata diff + SSIM/PSNR comparison and classification. |
| `pipeline.py` | Named detector profiles (spec section 32) and the run loop that turns exceptions into recorded limitations instead of crashes. |
| `cli.py` | `analyze` and `compare` subcommands. |

## Relationship to FFmpeg (spec section 13)

This project treats FFmpeg/ffprobe as the deterministic foundation and
never reimplements something FFmpeg already does reliably:

- Black-frame detection -> `blackdetect` filter, not custom pixel-loop code.
- Freeze detection -> `freezedetect` filter.
- Silence detection -> `silencedetect` filter.
- Level/clipping measurement -> `astats` filter.
- Objective quality comparison -> `ssim`/`psnr` filters.

Everything *above* that layer -- slide-state clustering, premature-advance
pattern matching, progression-interruption correlation, evidence
packaging, report formatting -- is this project's actual contribution and
is not something FFmpeg (or a general media-QC tool) provides. See
docs/research.md for what already exists and where this project sits
relative to it.

## Dependencies

The design goal is: **ffmpeg/ffprobe binaries + the Python standard
library** for everything except one clearly-scoped exception.

| Dependency | Why | What it provides | Could ffmpeg do it? | Runtime cost | License | Maintenance |
|---|---|---|---|---|---|---|
| `ffmpeg` / `ffprobe` (external binary, required) | Core requirement | All deterministic media measurement | N/A -- this *is* the foundation | Low; native code | LGPL/GPL | Extremely active |
| `numpy` (optional, `feedback` extra only) | Windowed FFT for the experimental feedback/howling detector (`detectors/feedback.py`) | Fast spectral analysis over a full recording; pure-Python DFT is impractically slow at this scale | No -- ffmpeg has no narrow-band spectral-persistence filter | Small; vectorized C under the hood | BSD-3-Clause | Extremely active, ubiquitous |
| `pytest` (dev only) | Test runner | N/A | N/A | Dev-only | MIT | Extremely active |

Explicitly **not** added, and why:

- **OpenCV / PySceneDetect** -- scene-change and slide-boundary detection
  is implemented instead with ffmpeg's own downscale/grayscale filters
  plus a ~30-line pure-Python average hash (`slides/phash.py`). At the
  tiny frame sizes used here (32x32), this is simpler and has zero extra
  install footprint. If a future detector needs a more discriminating
  hash (DCT-based pHash) or motion vectors, that tradeoff should be
  revisited explicitly -- see docs/research.md.
- **imagehash / Pillow** -- same reasoning; ffmpeg already does the
  decode+resize, so only the bit-packing logic is needed.
- **A VAD library (webrtcvad/Silero)** -- the current audio-activity
  signal is an RMS-threshold heuristic over ffmpeg's `astats` output, not
  true speech detection. This is a known limitation (see
  docs/false-positives.md and docs/detection-model.md); adopting a real
  VAD is a reasonable future improvement but is a nontrivial dependency
  (Silero needs a torch/onnxruntime runtime) that was not justified for
  the current detector set.
- **libvmaf-based VMAF scoring** -- requires a libvmaf-enabled ffmpeg
  build, which is not guaranteed to be present. SSIM/PSNR (built into
  stock ffmpeg) are used instead for the post-production comparison mode.

## Localization

`report.html` and `report.md` accept a `language` parameter (`--lang` on
the CLI; `en` default, `ja` also supported today) via
`reporting/i18n.py`. Two things are deliberately in scope and one is out:

- **In scope**: structural labels (headers, table columns, severity/
  confidence/category words) and each finding's `observations`/
  `possible_interpretation` prose. The Japanese versions of the latter are
  hand-written per detector `type` (`i18n._JA_RENDERERS`), reconstructed
  from the same `Event.measurements` data the English text uses -- not a
  runtime machine translation of the English string -- so both languages
  carry the same information, verified in `tests/test_i18n.py` and
  `tests/test_pipeline.py`.
- **Deliberately not translated**: `Event.type` (e.g.
  `slide_rollback_pattern`) is a stable technical identifier documented in
  docs/detection-model.md; giving it per-language names would break that
  cross-reference. `report.json` is entirely untranslated for the same
  reason -- it's the stable machine-readable format (spec section 17).
- **Not yet translated**: the pipeline's free-text `limitations` entries
  (e.g. "Detector 'clipping' skipped: input has no audio stream.") are
  generated directly by `pipeline.py` in English and passed through
  as-is. Localizing these would mean turning them into structured
  (key, params) messages the same way detector observations are handled;
  not done yet because no detector-observation translation existed to
  extend when the limitations mechanism was written.

Adding a third language means: add its code to
`i18n.SUPPORTED_LANGUAGES`, add a column to every entry in `i18n._UI_STRINGS`
/`_SEVERITY`/`_CONFIDENCE`/`_CATEGORY`, and add a `_<lang>_<type>` renderer
per detector type (a missing renderer falls back to English rather than
raising, so partial coverage degrades gracefully).

## Non-goals (spec section 19: no hallucinated capabilities)

This project does not and cannot:

- Identify which specific person/operator/tool caused an anomaly.
- Recover an original switching plan or slide order that was never
  supplied as reference data.
- Perform reliable lip-reading / true audiovisual speech correlation --
  `feedback.py` and the audio-activity heuristics used elsewhere are
  explicitly approximations, documented as such.
- Distinguish, from pixels alone, whether a static shot is a broken
  camera feed or a legitimately static slide/title card. See
  docs/false-positives.md for how this is mitigated (correlating with
  audio and duration) rather than solved.
