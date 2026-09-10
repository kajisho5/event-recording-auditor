"""Unified anomaly event schema.

Every detector in this project emits `Event` objects. The schema keeps a
hard separation between what was measured (`observations`, `measurements`)
and what a detector believes it might mean (`possible_interpretation`).
Detectors must never collapse that distinction -- see docs/event-schema.md
and section 8 ("Evidence-First Reporting") of the design spec.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Severity(str, Enum):
    """Estimated operational impact if the event is real. Independent of confidence."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Confidence(str, Enum):
    """How strongly the deterministic evidence supports this being a real anomaly."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Category(str, Enum):
    VIDEO = "video"
    AUDIO = "audio"
    PRESENTATION = "presentation"
    SWITCHING = "switching"
    PROGRESS = "progress"
    CONTINUITY = "continuity"
    POST_PRODUCTION = "post_production"


@dataclass
class Event:
    """A single anomaly candidate on the unified event timeline.

    Attributes:
        start: start time in seconds from the start of the analyzed file.
        end: end time in seconds (>= start; use start == end for instants).
        category: which detection category produced this event.
        type: machine-readable detector-specific type, e.g. "blackout",
            "slide_rollback_pattern".
        severity: estimated impact if real (see docs/detection-model.md).
        confidence: how strongly the evidence supports the finding.
        observations: plain-language statements of *measured fact*. No
            interpretation belongs here.
        measurements: raw numeric/structured evidence (durations, levels,
            frequencies, slide IDs, etc.) backing the observations.
        possible_interpretation: a hedged, human-readable hypothesis. Must
            never be phrased as a confirmed fact.
        requires_human_review: almost always True; set False only for
            purely informational timeline entries.
        detector: name of the detector/module that produced this event.
        source_files: input file(s) this event was derived from.
        evidence: paths to extracted evidence artifacts (frames, clips),
            populated by the evidence-extraction stage, not the detector.
    """

    start: float
    end: float
    category: Category
    type: str
    severity: Severity
    confidence: Confidence
    observations: list[str] = field(default_factory=list)
    measurements: dict[str, Any] = field(default_factory=dict)
    possible_interpretation: str | None = None
    requires_human_review: bool = True
    detector: str = ""
    source_files: list[str] = field(default_factory=list)
    evidence: dict[str, str] = field(default_factory=dict)
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    def __post_init__(self) -> None:
        if self.end < self.start:
            raise ValueError(f"Event end ({self.end}) precedes start ({self.start})")

    @property
    def duration(self) -> float:
        return self.end - self.start

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "start": round(self.start, 3),
            "end": round(self.end, 3),
            "duration": round(self.duration, 3),
            "category": self.category.value,
            "type": self.type,
            "severity": self.severity.value,
            "confidence": self.confidence.value,
            "observations": list(self.observations),
            "measurements": self.measurements,
            "possible_interpretation": self.possible_interpretation,
            "requires_human_review": self.requires_human_review,
            "detector": self.detector,
            "source_files": list(self.source_files),
            "evidence": dict(self.evidence),
        }
