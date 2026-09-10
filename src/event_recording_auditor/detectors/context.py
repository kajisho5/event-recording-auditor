"""Shared, lazily-computed, cached analysis state for one input file.

Several detectors need the same expensive intermediate data (the audio
level envelope, the sampled-frame hash sequence). Computing each once here
and sharing it means running the full detector suite decodes the file's
audio/video once each, not once per detector.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..audio.levels import LevelWindow, compute_level_envelope
from ..media.ffprobe import MediaInfo, probe
from ..slides.boundary import Segment, build_segments
from ..slides.phash import FrameSample, hamming_distance, sample_frames
from ..slides.timeline import SlideState, build_slide_timeline


@dataclass
class AnalysisContext:
    source: str
    media_info: MediaInfo = field(init=False)

    _level_envelope: list[LevelWindow] | None = field(default=None, init=False, repr=False)
    _frame_samples: list[FrameSample] | None = field(default=None, init=False, repr=False)
    _slide_segments: list[Segment] | None = field(default=None, init=False, repr=False)
    _slide_states: list[SlideState] | None = field(default=None, init=False, repr=False)

    # sampling parameters used to build the cached frame samples; if a
    # detector needs different parameters it should sample independently
    # rather than mutate these.
    slide_fps: float = 2.0
    slide_grid: int = 32
    level_window: float = 0.5

    def __post_init__(self) -> None:
        self.media_info = probe(self.source)

    def level_envelope(self) -> list[LevelWindow]:
        if self._level_envelope is None:
            if not self.media_info.has_audio:
                self._level_envelope = []
            else:
                self._level_envelope = compute_level_envelope(
                    self.source, window=self.level_window
                )
        return self._level_envelope

    def frame_samples(self) -> list[FrameSample]:
        if self._frame_samples is None:
            if not self.media_info.has_video:
                self._frame_samples = []
            else:
                self._frame_samples = sample_frames(
                    self.source, fps=self.slide_fps, grid=self.slide_grid
                )
        return self._frame_samples

    def visual_activity(self) -> list[tuple[float, int]]:
        """Per-sample-interval (time, hamming_distance_from_previous_sample).

        A coarse, deterministic proxy for "how much the picture changed"
        between consecutive low-res samples. Used as supporting evidence for
        progression-interruption detection -- it does not distinguish
        camera motion from a slide change, so it is only meaningful
        combined with the slide timeline and audio activity, never alone.
        """
        samples = self.frame_samples()
        out: list[tuple[float, int]] = []
        for prev, cur in zip(samples, samples[1:]):
            out.append((cur.time, hamming_distance(prev.hash, cur.hash)))
        return out

    def slide_states(
        self, stable_threshold: int = 24, match_threshold: int = 48
    ) -> list[SlideState]:
        if self._slide_states is None:
            samples = self.frame_samples()
            segments = build_segments(samples, stable_threshold=stable_threshold)
            self._slide_segments = segments
            self._slide_states = build_slide_timeline(
                segments, match_threshold=match_threshold
            )
        return self._slide_states
