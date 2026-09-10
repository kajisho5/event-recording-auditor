---
name: event-recording-auditor
description: Analyze a recorded event (conference, seminar, webinar, lecture) after the fact to find production incidents worth human review -- black frames, freezes, audio dropouts/clipping, possible feedback, premature/rollback slide transitions, and progression interruptions. Also investigates "the edited/exported footage looks worse than the source" complaints by comparing a source recording against a delivered export. Use when the user asks to check, audit, or review an event recording for problems, or to compare original footage against an edited version. Not for editing or transcoding media, and not for live/real-time monitoring.
---

# Event Recording Auditor

Deterministic, evidence-first analysis of recorded event footage. This
Skill finds **anomaly candidates** and points a human reviewer at the
relevant timestamp with evidence -- it does not replace human review, and
it does not claim to know what an operator or presenter intended. See
`docs/architecture.md` for the full design and `docs/detection-model.md`
for what is and is not implemented.

## When to use this

Trigger phrases include (English or Japanese):

- "Check this event recording for production incidents."
- "この収録をチェックして、本番中のトラブルがあった箇所を出して"
- "The edited footage looks worse than the source, find out why."
- "編集後の映像が荒いと言われた。元素材と比較して原因を調べて。"

There are two distinct modes -- pick based on what the user is asking and
what files they've given you:

1. **Event-time audit** (one recording): find in-recording anomalies.
2. **Post-production / source-vs-export investigation** (two recordings,
   or a complaint about quality after editing): compare a source file
   against an exported/edited file.

## Before running anything

1. Confirm `ffmpeg` and `ffprobe` are on PATH (`ffmpeg -version`). If not,
   tell the user this Skill cannot run without them -- do not attempt a
   substitute analysis.
2. Identify the input file(s) the user means. If ambiguous (multiple video
   files in the working directory, unclear which is "the recording"),
   ask.
3. Do **not** ask for information the recording alone can already answer.
   Only ask for extra context (expected slide order, switching plan,
   session schedule, original presentation file, delivery spec) when it
   would materially change the analysis -- e.g. ask for a delivery spec
   only if a source-vs-export comparison found a format change and the
   user seems surprised by it.
4. Never modify, overwrite, transcode, or move the original recording.
   Every command in this Skill reads the source and writes only to a new
   output directory.

## Event-time audit workflow

```bash
python -m event_recording_auditor.cli analyze RECORDING.mp4 \
  --out-dir audit-output \
  --profile full
```

- `--profile` selects a detector set: `technical` (black/freeze/clipping),
  `production` (freeze/progression-interruption/audio-dropout),
  `presentation` (slide rollback/brief-slide), or `full` (all of the
  above). Default to `full` unless the user's request clearly targets one
  category (e.g. "just check the audio" -> `--profile technical` won't
  cover audio dropout; use judgment, or just run `full` -- it's cheap).
- Add `--experimental-feedback` only if the user specifically asks about
  feedback/howling and numpy is available (`python -c "import numpy"`);
  otherwise leave it off (it's not part of any default profile and is
  explicitly experimental).
- `--no-evidence` skips frame/clip extraction if the user only wants a
  quick pass; otherwise evidence packages (frames + a short clip per
  finding) are written to `audit-output/evidence/`.

Read `audit-output/report.json` for the structured findings and summarize
for the user. Point to `audit-output/report.html` as the human-reviewable
artifact -- offer to open/share it rather than pasting the whole JSON.
`audit-output/report.md` has the same content in Markdown; prefer sending
or quoting that (or the file directly) over reconstructing a summary by
hand when the user wants something to paste elsewhere.

### Reading and reporting results

- Always report findings using the schema's own hedged language: "possible
  X", "candidate", "requires human review" -- never upgrade a finding to a
  confirmed fact yourself.
- Report `severity` and `confidence` as separate values, never merged
  (docs/detection-model.md).
- Surface the `limitations` list from the report (e.g. "clipping detector
  skipped: no audio track") so the user knows what was *not* checked, not
  just what was found.
- If zero anomalies were found, say so plainly -- do not manufacture a
  finding to seem thorough.

## Post-production / quality-complaint workflow

```bash
python -m event_recording_auditor.cli compare SOURCE.mp4 EXPORT.mp4 \
  --out-dir audit-output \
  --delivery-spec delivery-spec.json   # optional
```

Before running this, per spec section 27, convert a complaint into an
investigation:

1. What is being compared -- the original camera file, or an intermediate
   render? Ask if unclear; do not assume a "source" file the user hands
   you is actually the original camera master.
2. If only one file is available (source or export, not both), say so
   explicitly and do not attempt a comparison -- offer observation-only
   analysis of the single file instead (e.g. an `analyze` pass, or just
   `ffprobe`-level facts).
3. If a delivery specification exists (resolution/bitrate/codec the
   export was *supposed* to target), pass it via `--delivery-spec` so a
   format change can be judged against it instead of reported as "unknown
   whether intentional".

The tool's conclusion is always one of exactly three classes:
`source_degradation_already_present`, `additional_downstream_degradation`,
or `inconclusive`. Report the conclusion, the reasoning list, and the
limitations list verbatim in substance -- never assign blame to a person,
tool, or company beyond what `reasoning`/`limitations` actually establish
(spec section 26.5 is explicit about this).

## Hard constraints (do not violate)

- Never claim to know operator intent, who pressed a button, or what the
  original plan was, unless reference data supplied by the user
  establishes it.
- Never state a finding as fact when the underlying event has
  `confidence` below high, or when the detector's own interpretation text
  is hedged.
- Never silently drop the `limitations` section of a report when
  summarizing for the user.
- Never overwrite or delete the input recording(s).
- Do not attempt detectors this project does not implement (see
  docs/detection-model.md, "Deliberately not yet implemented") -- if the
  user asks for one of those (e.g. "which operator caused this",
  "check the captions for name spelling errors"), say plainly that this
  Skill does not yet support that rather than improvising an answer.
