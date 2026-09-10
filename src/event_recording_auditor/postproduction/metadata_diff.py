"""Deterministic metadata comparison between a source and an exported file.

This never decides whether a difference is "bad" -- see docs/architecture.md,
"Delivery Specification Awareness" (spec section 26.4): a resolution or
bit-depth reduction can be a perfectly correct delivery conversion. It only
records what actually changed, for `compare.py` (and, when supplied, a
delivery specification) to interpret.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..media.ffprobe import MediaInfo


@dataclass
class MetadataDiff:
    source: dict[str, Any]
    export: dict[str, Any]
    changed_fields: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "export": self.export,
            "changed_fields": self.changed_fields,
        }


def _video_fields(info: MediaInfo) -> dict[str, Any]:
    v = info.primary_video or {}
    return {
        "resolution": info.resolution,
        "frame_rate": info.frame_rate,
        "codec_name": v.get("codec_name"),
        "pix_fmt": v.get("pix_fmt"),
        "bits_per_raw_sample": v.get("bits_per_raw_sample"),
        "color_space": v.get("color_space"),
        "color_transfer": v.get("color_transfer"),
        "bitrate": info.bitrate,
        "duration": round(info.duration, 3),
    }


def diff_metadata(source: MediaInfo, export: MediaInfo) -> MetadataDiff:
    source_fields = _video_fields(source)
    export_fields = _video_fields(export)
    changed = [
        key
        for key in source_fields
        if source_fields[key] != export_fields.get(key)
    ]
    return MetadataDiff(source=source_fields, export=export_fields, changed_fields=changed)
