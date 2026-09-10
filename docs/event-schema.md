# Event Schema

Every detector emits `Event` objects (`src/event_recording_auditor/timeline/event.py`).
This is the single schema all reports (`report.json`, `report.html`,
evidence packages) are built from.

```json
{
  "id": "e0e6b24412f8",
  "start": 1234.52,
  "end": 1235.31,
  "duration": 0.79,
  "category": "presentation",
  "type": "slide_rollback_pattern",
  "severity": "medium",
  "confidence": "medium",
  "observations": [
    "Slide state 1 was displayed for 3.00s.",
    "Slide state 2 then appeared for 0.50s.",
    "The recording returned to slide state 1 for 2.00s.",
    "Slide state 2 appeared again afterward, this time for 3.00s."
  ],
  "measurements": {
    "sequence": [1, 2, 1, 2],
    "first_intervening_duration": 0.5,
    "confirmed_repeat": true
  },
  "possible_interpretation": "Consistent with a premature slide advance followed by an operator/presenter correction...",
  "requires_human_review": true,
  "detector": "slide_rollback_pattern",
  "source_files": ["recording.mp4"],
  "evidence": {
    "before_frame": "evidence/incident-0001/before.jpg",
    "event_frame": "evidence/incident-0001/event.jpg",
    "after_frame": "evidence/incident-0001/after.jpg",
    "clip": "evidence/incident-0001/evidence.mp4",
    "metadata": "evidence/incident-0001/metadata.json",
    "explanation": "evidence/incident-0001/explanation.txt"
  }
}
```

## Field rules (never violate these)

- **`observations`** must only contain statements that were actually
  measured (a duration, a level, a detected state ID, a pattern match).
  Never phrase an interpretation as an observation.
- **`possible_interpretation`** must be hedged ("possible", "consistent
  with", "candidate") and must never assert operator intent, blame, or a
  confirmed root cause unless the evidence genuinely establishes it (spec
  section 19 -- almost never, for a single recording alone).
- **`severity`** and **`confidence`** are independent axes (spec section
  31) -- see docs/detection-model.md for the model. Never collapse them
  into one score.
- **`requires_human_review`** defaults to `True` and should only be
  `False` for purely informational timeline entries (none of the current
  detectors emit those).
- **`detector`** is the stable machine name (`Detector.name`), used to
  trace a finding back to the code that produced it and to explain
  "skipped" limitations in the report.
- **`evidence`** is populated by `evidence/extractor.py` after the fact --
  detectors never populate it themselves. An event with no evidence
  package (below the configured severity threshold, or evidence
  extraction failed) simply has an empty dict, or `{"error": "..."}` if
  extraction was attempted and failed (evidence extraction is
  best-effort and must never abort the whole audit).

## Timeline vs. Event

`timeline/builder.py`'s `Timeline` is just a sorted collection of `Event`s
plus a `summary()` (counts by severity/category) and a `filter()` helper.
It intentionally does no de-duplication or merging across detectors: if
two detectors flag overlapping evidence for related reasons (e.g.
`slide_rollback_pattern` and `brief_unexpected_slide` on the same brief
slide), both entries are kept, since they represent different detection
logic and a human reviewer benefits from seeing both signals agreed. This
is a deliberate tradeoff documented in docs/false-positives.md rather than
an oversight.
