"""Common interface every detector implements.

Kept deliberately small: a detector is something with a stable machine
name, a maturity tier (see docs/detection-model.md), and a `run` method
that turns shared context into a list of `Event`s. Detectors must not
raise on "nothing found" -- an empty list is the normal, expected result
for a clean recording.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from ..timeline import Event

if TYPE_CHECKING:
    from .context import AnalysisContext


class Detector(ABC):
    #: machine-readable identifier, stable across versions (used in Event.detector)
    name: str = "unnamed_detector"
    #: 1 = highly measurable, 2 = strong contextual, 3 = advanced/probabilistic/experimental
    tier: int = 1
    #: short human-readable description of what evidence this detector needs
    requires: str = "video+audio"

    @abstractmethod
    def run(self, ctx: "AnalysisContext") -> list[Event]:
        """Analyze `ctx` and return any anomaly candidates found."""
        raise NotImplementedError
