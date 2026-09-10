"""Tier 3 EXPERIMENTAL detector: possible audio feedback / howling.

Not part of any default profile (see pipeline.py) -- must be explicitly
enabled. This is the one detector in the project that needs a dependency
beyond ffmpeg: a windowed FFT to measure spectral concentration and
dominant-frequency persistence, which pure Python cannot do efficiently
over a full recording. NumPy is added for exactly this (see
docs/architecture.md, "Dependencies", for the justification -- BSD
license, minimal footprint, ubiquitous). If NumPy is not installed, this
detector reports that it was skipped rather than failing the whole run.

Per spec section 4.2/28.4: this must never assert "howling detected", only
"possible feedback/howling" -- music, sustained tones, and normal speech
harmonics must not be misclassified without strong, multi-signal evidence.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..media.runner import FFmpegError, run_ffmpeg_binary
from ..timeline import Category, Confidence, Event, Severity
from .base import Detector
from .context import AnalysisContext


class FeedbackDependencyMissing(RuntimeError):
    pass


@dataclass
class _SpectralWindow:
    time: float
    dominant_freq: float
    concentration: float
    rms: float


def _decode_pcm(source: str, sample_rate: int = 22050) -> "list[int]":
    args = ["-i", source, "-ac", "1", "-ar", str(sample_rate), "-f", "s16le", "-"]
    stdout, stderr, returncode = run_ffmpeg_binary(args)
    if returncode != 0:
        raise FFmpegError(f"ffmpeg failed decoding PCM from {source!r}: {stderr}")
    return stdout


def _analyze_windows(
    pcm_bytes: bytes,
    sample_rate: int,
    window_seconds: float,
    hop_seconds: float,
    band_low_hz: float,
    band_high_hz: float,
) -> list[_SpectralWindow]:
    try:
        import numpy as np
    except ImportError as exc:
        raise FeedbackDependencyMissing(
            "numpy is required for the experimental feedback/howling detector "
            "but is not installed."
        ) from exc

    samples = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float64)
    if samples.size == 0:
        return []
    samples /= 32768.0

    window_size = max(int(window_seconds * sample_rate), 256)
    hop_size = max(int(hop_seconds * sample_rate), 1)
    hann = np.hanning(window_size)
    freqs = np.fft.rfftfreq(window_size, d=1.0 / sample_rate)
    band_mask = (freqs >= band_low_hz) & (freqs <= band_high_hz)

    windows: list[_SpectralWindow] = []
    for start in range(0, max(len(samples) - window_size, 0) + 1, hop_size):
        chunk = samples[start : start + window_size]
        if len(chunk) < window_size:
            break
        spectrum = np.abs(np.fft.rfft(chunk * hann))
        band_energy = spectrum[band_mask]
        total = float(band_energy.sum())
        rms = float(np.sqrt(np.mean(chunk**2)))
        if total <= 1e-9:
            windows.append(_SpectralWindow(start / sample_rate, 0.0, 0.0, rms))
            continue
        peak_idx = int(np.argmax(band_energy))
        # concentration = energy in a narrow window around the peak bin vs. total band energy
        lo = max(peak_idx - 2, 0)
        hi = min(peak_idx + 3, len(band_energy))
        peak_energy = float(band_energy[lo:hi].sum())
        concentration = peak_energy / total
        dominant_freq = float(freqs[band_mask][peak_idx])
        windows.append(_SpectralWindow(start / sample_rate, dominant_freq, concentration, rms))

    return windows


class FeedbackHowlingDetector(Detector):
    name = "feedback_howling_experimental"
    tier = 3
    requires = "audio (numpy)"

    def __init__(
        self,
        sample_rate: int = 22050,
        window_seconds: float = 0.5,
        hop_seconds: float = 0.25,
        band_low_hz: float = 300.0,
        band_high_hz: float = 8000.0,
        concentration_threshold: float = 0.45,
        min_rms: float = 0.02,
        freq_tolerance_hz: float = 80.0,
        min_duration: float = 1.0,
    ) -> None:
        self.sample_rate = sample_rate
        self.window_seconds = window_seconds
        self.hop_seconds = hop_seconds
        self.band_low_hz = band_low_hz
        self.band_high_hz = band_high_hz
        self.concentration_threshold = concentration_threshold
        self.min_rms = min_rms
        self.freq_tolerance_hz = freq_tolerance_hz
        self.min_duration = min_duration
        self.skipped_reason: str | None = None

    def run(self, ctx: AnalysisContext) -> list[Event]:
        if not ctx.media_info.has_audio:
            return []
        try:
            pcm = _decode_pcm(ctx.source, self.sample_rate)
            windows = _analyze_windows(
                pcm,
                self.sample_rate,
                self.window_seconds,
                self.hop_seconds,
                self.band_low_hz,
                self.band_high_hz,
            )
        except FeedbackDependencyMissing as exc:
            self.skipped_reason = str(exc)
            return []

        candidates = [
            w
            for w in windows
            if w.concentration >= self.concentration_threshold and w.rms >= self.min_rms
        ]
        if not candidates:
            return []

        events = []
        run: list[_SpectralWindow] = []

        def flush():
            if not run:
                return None
            duration = (run[-1].time + self.hop_seconds) - run[0].time
            if duration < self.min_duration:
                return None
            avg_freq = sum(w.dominant_freq for w in run) / len(run)
            max_concentration = max(w.concentration for w in run)
            return Event(
                start=run[0].time,
                end=run[-1].time + self.hop_seconds,
                category=Category.AUDIO,
                type="possible_feedback_howling",
                severity=Severity.MEDIUM,
                confidence=Confidence.MEDIUM if max_concentration >= 0.6 else Confidence.LOW,
                observations=[
                    f"A narrow-band spectral peak near {avg_freq:.0f} Hz persisted "
                    f"for {duration:.2f}s.",
                    f"Peak-band energy concentration reached {max_concentration:.0%} "
                    "of total in-band energy.",
                ],
                measurements={
                    "duration": duration,
                    "dominant_frequency_hz": avg_freq,
                    "max_concentration": max_concentration,
                },
                possible_interpretation=(
                    "Possible audio feedback/howling. This is an experimental, "
                    "heuristic detector based on narrow-band spectral persistence; "
                    "it cannot reliably distinguish this from a sustained musical "
                    "note, test tone, or room resonance, and requires human review."
                ),
                detector=self.name,
                source_files=[ctx.source],
            )

        prev_time = None
        for w in candidates:
            if run and prev_time is not None:
                gap = w.time - prev_time
                freq_jump = abs(w.dominant_freq - run[-1].dominant_freq)
                if gap > self.hop_seconds * 1.5 or freq_jump > self.freq_tolerance_hz:
                    ev = flush()
                    if ev:
                        events.append(ev)
                    run = []
            run.append(w)
            prev_time = w.time
        ev = flush()
        if ev:
            events.append(ev)

        return events
