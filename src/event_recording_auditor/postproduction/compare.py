"""Source-vs-export investigation (spec sections 26 and 27).

Classifies into exactly the three conclusion classes the spec defines:
"source degradation already present", "additional downstream degradation",
or "inconclusive". Never assigns blame to a person, tool, or company --
only reports what is measurable and what it is consistent with.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from ..media.ffprobe import MediaInfo, probe
from .metadata_diff import MetadataDiff, diff_metadata
from .quality_metrics import QualityMetrics, compare_quality


class Conclusion(str, Enum):
    SOURCE_DEGRADATION_PRESENT = "source_degradation_already_present"
    ADDITIONAL_DOWNSTREAM_DEGRADATION = "additional_downstream_degradation"
    INCONCLUSIVE = "inconclusive"


# Below this, SSIM indicates a visually noticeable quality difference at the
# compared resolution. This is a coarse, documented threshold, not a
# perceptual-quality standard -- see docs/detection-model.md.
_SSIM_DEGRADATION_THRESHOLD = 0.92
_PSNR_DEGRADATION_THRESHOLD_DB = 35.0


@dataclass
class ComparisonResult:
    source_path: str
    export_path: str
    metadata_diff: MetadataDiff
    quality: QualityMetrics | None
    delivery_spec: dict[str, Any] | None
    conclusion: Conclusion
    reasoning: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_path": self.source_path,
            "export_path": self.export_path,
            "metadata_diff": self.metadata_diff.to_dict(),
            "quality": (
                {
                    "ssim_avg": self.quality.ssim_avg,
                    "psnr_avg_db": self.quality.psnr_avg_db,
                    "psnr_min_db": self.quality.psnr_min_db,
                    "compared_resolution": list(self.quality.compared_resolution),
                }
                if self.quality
                else None
            ),
            "delivery_spec": self.delivery_spec,
            "conclusion": self.conclusion.value,
            "reasoning": self.reasoning,
            "limitations": self.limitations,
        }


def compare_source_and_export(
    source_path: str,
    export_path: str,
    delivery_spec: dict[str, Any] | None = None,
    run_quality_metrics: bool = True,
    max_compare_duration: float | None = 60.0,
) -> ComparisonResult:
    source_info = probe(source_path)
    export_info = probe(export_path)
    metadata_diff = diff_metadata(source_info, export_info)

    quality: QualityMetrics | None = None
    if run_quality_metrics and source_info.has_video and export_info.has_video:
        quality = compare_quality(
            source_path,
            export_path,
            source_info.resolution or (0, 0),
            export_info.resolution or (0, 0),
            max_duration=max_compare_duration,
        )

    reasoning: list[str] = []
    limitations: list[str] = []

    format_changed = bool(
        set(metadata_diff.changed_fields) & {"resolution", "bits_per_raw_sample", "pix_fmt"}
    )
    if format_changed and delivery_spec:
        reasoning.append(
            "A format change was observed (resolution/bit-depth/chroma), and a "
            "delivery specification was supplied -- checking whether it matches."
        )
    elif format_changed:
        reasoning.append(
            "A format change was observed (resolution/bit-depth/chroma), but no "
            "delivery specification was supplied, so it is not possible to say "
            "whether this conversion was expected."
        )
        limitations.append(
            "No delivery specification was provided; format changes are reported "
            "as observations only, not as errors."
        )

    if quality is None:
        limitations.append(
            "Objective quality metrics (SSIM/PSNR) were not computed (missing "
            "video stream or metrics disabled)."
        )
        conclusion = Conclusion.INCONCLUSIVE
        reasoning.append(
            "Insufficient evidence to classify: no objective quality comparison "
            "was available."
        )
        return ComparisonResult(
            source_path=source_path,
            export_path=export_path,
            metadata_diff=metadata_diff,
            quality=quality,
            delivery_spec=delivery_spec,
            conclusion=conclusion,
            reasoning=reasoning,
            limitations=limitations,
        )

    reasoning.append(
        f"SSIM (export vs. source, compared at {quality.compared_resolution[0]}x"
        f"{quality.compared_resolution[1]}): {quality.ssim_avg}."
    )
    reasoning.append(f"PSNR average: {quality.psnr_avg_db} dB, minimum: {quality.psnr_min_db} dB.")

    degraded = (
        quality.ssim_avg is not None and quality.ssim_avg < _SSIM_DEGRADATION_THRESHOLD
    ) or (
        quality.psnr_avg_db is not None and quality.psnr_avg_db < _PSNR_DEGRADATION_THRESHOLD_DB
    )

    if not degraded:
        conclusion = Conclusion.SOURCE_DEGRADATION_PRESENT
        reasoning.append(
            "Objective metrics do not show a material quality difference between "
            "source and export at the compared resolution."
        )
    else:
        conclusion = Conclusion.ADDITIONAL_DOWNSTREAM_DEGRADATION
        reasoning.append(
            "Objective metrics show a material quality difference between source "
            "and export beyond what the resolution/format change alone would "
            "explain."
        )

    limitations.append(
        "SSIM/PSNR were computed on the first "
        f"{max_compare_duration}s of each file with no explicit content alignment "
        "beyond matching start times; if source and export do not start at the "
        "same point in the event, this comparison is not meaningful."
        if max_compare_duration
        else "No explicit content alignment was performed beyond matching start times."
    )
    limitations.append(
        "This does not identify which specific tool, operator, or export step "
        "introduced any observed degradation."
    )

    return ComparisonResult(
        source_path=source_path,
        export_path=export_path,
        metadata_diff=metadata_diff,
        quality=quality,
        delivery_spec=delivery_spec,
        conclusion=conclusion,
        reasoning=reasoning,
        limitations=limitations,
    )
