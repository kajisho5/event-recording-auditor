"""Collects Event objects from all detectors into one sorted timeline."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .event import Event, Severity


class Timeline:
    def __init__(self) -> None:
        self._events: list[Event] = []

    def add(self, event: Event) -> None:
        self._events.append(event)

    def extend(self, events: Iterable[Event]) -> None:
        self._events.extend(events)

    @property
    def events(self) -> list[Event]:
        return sorted(self._events, key=lambda e: (e.start, e.end))

    def __len__(self) -> int:
        return len(self._events)

    def __iter__(self):
        return iter(self.events)

    def filter(
        self,
        category: str | None = None,
        min_severity: Severity | None = None,
    ) -> list[Event]:
        severity_rank = {Severity.LOW: 0, Severity.MEDIUM: 1, Severity.HIGH: 2}
        out = self.events
        if category is not None:
            out = [e for e in out if e.category.value == category]
        if min_severity is not None:
            threshold = severity_rank[min_severity]
            out = [e for e in out if severity_rank[e.severity] >= threshold]
        return out

    def summary(self) -> dict[str, Any]:
        events = self.events
        by_severity = {"low": 0, "medium": 0, "high": 0}
        by_category: dict[str, int] = {}
        for e in events:
            by_severity[e.severity.value] += 1
            by_category[e.category.value] = by_category.get(e.category.value, 0) + 1
        return {
            "total_events": len(events),
            "by_severity": by_severity,
            "by_category": by_category,
        }

    def to_dicts(self) -> list[dict[str, Any]]:
        return [e.to_dict() for e in self.events]
