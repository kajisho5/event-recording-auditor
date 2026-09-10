# Detection Model

## Severity vs. confidence (spec section 31)

These are independent axes and are never combined into one score.

- **Severity** -- how significant this would be *if real*. Judged from
  measured properties (duration, level, pattern) of the event itself.
- **Confidence** -- how strongly the deterministic evidence supports the
  finding actually being a real anomaly (as opposed to normal behavior
  this detector cannot fully distinguish it from).

Example: a 3-second video freeze with no concurrent audio activity is
`severity=high, confidence=medium` -- if real, a 3s dead feed matters, but
freeze detection alone cannot rule out "the source genuinely had nothing
to show for 3 seconds." The same freeze *with* concurrent audio activity
is downgraded to `severity=low, confidence=low`, because active audio
during a "frozen" video signal is strong evidence this is just a normal
static camera shot, not a technical failure.

Confidence is capped per detector tier: no Tier 2 or Tier 3 detector in
this codebase ever emits `confidence=high`, because none of them have
grounds for certainty -- the underlying signal is always heuristic or
context-dependent. Only Tier 1 measurements (blackout, clipping) reach
`confidence=high`, and only when the measurement itself is unambiguous
(e.g. a sustained flat-top waveform for clipping).

## Tiers (spec section 34)

- **Tier 1 -- highly measurable.** Directly wraps an ffmpeg filter or a
  simple threshold on ffmpeg-provided measurements. Implemented: blackout,
  freeze, clipping.
- **Tier 2 -- strong contextual detection.** Correlates two or more Tier-1-
  level signals (slide state + duration, audio level + surrounding
  context, audio + video + slide together). Implemented: slide rollback
  pattern (`2 -> 1 -> 2`), brief unexpected slide, context-aware audio
  dropout, progression interruption.
- **Tier 3 -- advanced / probabilistic / experimental.** Requires a
  heuristic model beyond direct thresholding and is explicitly not
  presented as production-reliable. Implemented (opt-in only): feedback/
  howling candidate (`--experimental-feedback`).

## Implemented detectors

| Detector | Tier | Category | Needs | Notes |
|---|---|---|---|---|
| `blackout` | 1 | video | video | Wraps `blackdetect`. |
| `freeze` | 1 | video | video (+audio improves confidence) | Wraps `freezedetect`; downgrades confidence/severity when audio was active throughout (normal static shot). See "Known false-positive class" below. |
| `clipping` | 1 | audio | audio | `astats` peak level + flat-factor, both required, sustained. |
| `channel_imbalance` / `channel_missing` | 1 | audio | audio (2+ channels) | Per-channel `astats` RMS. `channel_missing`: one channel active while another is near-silent (MEDIUM/HIGH). `channel_imbalance`: sustained level gap between channels that are both somewhat active (LOW/LOW, since this can be an intentional mono-on-one-channel mix). Skips gracefully (with a recorded limitation) on mono audio. |
| `slide_rollback_pattern` | 2 | presentation | video | The spec's core use case: `A -> B -> A(-> B)`. Confidence never exceeds medium. Skips (with a recorded limitation) on content that doesn't look slide-like (low stability ratio, or non-landscape aspect ratio) -- see docs/false-positives.md. |
| `brief_unexpected_slide` | 2 | presentation | video | Any short-duration slide state, independent of whether it reverts. Same non-slide-content skip as above. |
| `audio_dropout` (possible) | 2 | audio | audio | Silence run bracketed by active audio on both sides, duration-bounded to exclude natural pauses. |
| `progression_interruption` | 2 | progress | video (+audio) | Requires audio inactivity AND visual inactivity AND unchanged slide state, all sustained together (spec section 5). |
| `feedback_howling_experimental` | 3 | audio | audio + numpy | Off by default. Narrow-band spectral concentration + dominant-frequency persistence. Never asserts "howling", only "possible". |

## Post-production comparison (separate pipeline, spec sections 26-27)

Not a `Detector` -- a two-file comparison producing one of three
conclusions (`source_degradation_already_present`,
`additional_downstream_degradation`, `inconclusive`), based on:

- Metadata diff (resolution, frame rate, codec, pixel format/chroma,
  bit depth, bitrate) via ffprobe.
- SSIM/PSNR at the lower of the two files' resolutions, over the first
  N seconds (default 60s) of each file.

The SSIM/PSNR thresholds (0.92 / 35 dB) are a coarse, documented
calibration point, not a perceptual-quality standard -- they mark "the
files differ by more than typical re-encoding noise", not "this looks bad
to a viewer". A delivery specification, when supplied, is used to say
whether an observed format change was expected; without one, format
changes are reported as observations only (spec section 26.4).

## Deliberately not yet implemented

Per spec section 35 ("do everything does not mean implement everything at
once"), these backlog items from spec sections 4.4 and 28 are not
implemented, with the reason each was deferred rather than faked:

| Capability | Why deferred |
|---|---|
| Camera/slide source-switching timeline (4.4, 28.2) | Requires being able to tell "this frame is a camera shot" from "this frame is a slide" from pixels alone, or a separately-tagged source feed. Neither is reliably available from a single switched program recording; building this without one of those inputs would be guessing, which section 19 forbids. |
| Presenter/speech visual correlation (6, 28.6) | Needs face/mouth-activity estimation, which needs a real computer-vision dependency (e.g. a face-landmark model) well beyond the ffmpeg-first design. Not added without an explicit dependency-tradeoff decision. |
| Camera framing/focus/exposure quality (28.1, 28.14) | Needs reference-free image-quality estimation (blur/exposure metrics) that has real false-positive risk (shallow depth of field, intentional reframing) and was not prototyped against real footage yet. |
| Caption/lower-third/OCR checks (28.12) | Needs OCR; spec explicitly warns never to invent a name from uncertain OCR, so this needs careful confidence-gating before it's worth shipping. |
| Multi-file continuity / long-recording integrity (28.9, 28.10) | Metadata-only checks (gaps, codec/resolution changes between segments) are straightforward given ffprobe and are a reasonable near-term addition; not yet implemented because the current pipeline is single-file. |
| Speaker/session transition detection (28.11) | Needs a schedule/reference input to be meaningful (without one, this degenerates into "something changed", already covered by other detectors); no schedule-comparison support exists yet. |
| Recording start/end gap vs. schedule (28.8) | Same as above -- needs a schedule input; the comparison logic itself is simple once a schedule format is defined. |

None of these are claimed as implemented anywhere in this repository's
docs, `SKILL.md`, or CLI help text.

## Known false-positive class worth calling out explicitly

Freeze detection cannot, from pixels alone, distinguish a technically
frozen feed from a legitimately static slide or steady camera shot -- both
look like "no change" to `freezedetect`. This project mitigates this by
correlating with audio (a freeze with active audio underneath is almost
certainly not a technical failure) rather than solving it, since solving
it would require information (e.g. a tagged camera-only source) this
project cannot assume it has. See docs/false-positives.md for the full
list of mitigations and their limits.
