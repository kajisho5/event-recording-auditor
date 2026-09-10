# Prior Art & Competitive Landscape: Event Recording Auditor

This document surveys existing open-source and well-known tooling relevant to an
event-recording forensic auditor: detection of black frames, freezes, audio
dropouts/clipping, feedback/howling, slide-flash anomalies, abnormal
camera/slide switching, and "progression interruptions," plus a source-vs-edit
comparison mode using resolution/bitrate/codec diffs and SSIM/PSNR. It also
covers the individual signal-detection building blocks (scene detection,
perceptual hashing, VAD) that a from-scratch implementation would otherwise
have to reinvent.

## Tool/Library Landscape

### 1. FFmpeg native filters (the foundation almost everything below is built on)

| Item | Detail |
|---|---|
| **Capability** | `blackdetect` (black-frame/fade intervals), `freezedetect` (frozen/duplicate frames), `silencedetect` (audio silence runs), `astats` (per-channel peak/RMS/clipping-adjacent stats), `ebur128` (EBU R128 / LUFS loudness, true-peak), `signalstats`/`idet` (video signal stats, interlace detection) |
| **License** | LGPL/GPL (FFmpeg project) |
| **Overlap** | Very high — these filters are the primitive detectors for black frames, freezes, silence, and loudness/clipping that this project's audit rules are built on |
| **Maintained** | Yes, core FFmpeg, continuously developed |
| **Dependency decision** | This is not an optional dependency — it is the intended foundation. No wrapper library needed; call `ffmpeg`/`ffprobe` CLI directly via subprocess and parse stderr/JSON output |
| **Source** | https://ffmpeg.org/ffmpeg-filters.html#blackdetect |

### 2. QCTools (MediaArea / BAVC / RiceCapades)

| Field | Detail |
|---|---|
| **URL** | https://github.com/MediaArea/QCTools |
| **License** | GPLv3 |
| **Capability** | Desktop GUI for visualizing FFmpeg-derived signal stats (`signalstats`, `cropdetect`, `psnr`, `ebur128`) over a timeline for archival video QC; built for spotting analog-digitization artifacts (dropouts, timebase errors, luma/chroma range issues) |
| **Overlap** | Medium — same underlying FFmpeg filters and "QC over a timeline" concept, but oriented toward archival/preservation artifacts (tape damage, signal errors) rather than event-production incidents (slide flashes, camera-switch anomalies, progression stalls) and has no notion of a "source vs. edited delivery" comparison mode |
| **Maintained** | Yes, but at a slow cadence; copyright/build activity through 2025, daily builds exist but feature development is sparse | 
| **Dependency vs. prior art** | Prior art only. It's a C++/Qt desktop app, not embeddable as a library, and its detectors don't map to this project's event-specific rules | 
| **Sources** | https://github.com/MediaArea/QCTools ; https://mediaarea.net/QCTools/License ; http://bavc.github.io/qctools/filter_descriptions.html |

### 3. Rendiff Probe (ffprobe-api)

| Field | Detail |
|---|---|
| **URL** | https://github.com/rendiffdev/rendiff-probe (formerly ffprobe-api) |
| **License** | MIT (wraps LGPL/GPL FFmpeg) |
| **Capability** | REST API/CLI over FFprobe exposing "19 professional QC categories" and ~121 parameters (format/stream/frame/packet analysis, `signalstats`, `idet`, `astats`, etc.), pitched as a general broadcast/streaming QC service with "AI-powered insights" |
| **Overlap** | Medium — closest thing found to a general "QC API," but it is a generic metrics/analysis surface (numbers out), not an event-recording-specific rule engine that reasons about presentation flow (slide flash patterns, camera-switch cadence, progression stalls) or does evidence-first incident reporting |
| **Maintained** | Appears actively developed (recent rename/re-scoping from ffprobe-api to rendiff-probe suggests ongoing churn); maturity/community size unclear |
| **Dependency vs. prior art** | Prior art / reference for API shape, not a dependency — it's a full service (DB, API server) which is much heavier than this project's minimal-Python/ffmpeg-first design goal |
| **Sources** | https://github.com/rendiffdev/rendiff-probe ; https://github.com/rendiffdev/ffprobe-api |

### 4. mediadeepa (Media ex Machina)

| Field | Detail |
|---|---|
| **URL** | https://github.com/mediaexmachina/mediadeepa |
| **License** | Apache-2.0 |
| **Capability** | Java CLI wrapping FFmpeg to detect black/blocky/blurred/duplicate/interlaced frames and export FFprobe/media-header data for deep analysis |
| **Overlap** | Medium-low — same detection primitives (black, freeze/duplicate frames) but general-purpose media QA, not event/presentation-aware, and written in Java (mismatched with a Python/ffmpeg-first stack) |
| **Maintained** | Yes, active repo | 
| **Dependency vs. prior art** | Prior art only — different language ecosystem, would add a JVM dependency for functionality FFmpeg's own filters already provide directly |
| **Sources** | https://github.com/mediaexmachina/mediadeepa |

### 5. Stream Monitor

| Field | Detail |
|---|---|
| **URL** | https://streammonitor.app/ |
| **License** | Described as open-source/self-hosted; specific license not confirmed from available pages |
| **Capability** | Real-time (live-stream) monitoring for freeze frames, audio silence, and bitrate drops using FFmpeg ingestion |
| **Overlap** | Low-medium — same detection categories, but targets **live** stream monitoring/alerting, not **post-hoc forensic audit** of a finished recording with an evidence report; no slide/presentation or source-vs-edit comparison logic |
| **Maintained** | Unclear from public info; appears to be a smaller/newer project |
| **Dependency vs. prior art** | Prior art only |
| **Source** | https://streammonitor.app/ |

### 6. PySceneDetect

| Field | Detail |
|---|---|
| **URL** | https://github.com/Breakthrough/PySceneDetect (docs: https://www.scenedetect.com/) |
| **License** | BSD 3-Clause |
| **Capability** | Python/OpenCV scene-cut and transition detection (`ContentDetector`, `AdaptiveDetector` for fast camera motion, `ThresholdDetector` for fades), with FFmpeg/mkvmerge integration for splitting |
| **Overlap** | Medium — directly relevant to "abnormal camera/slide switching" detection (cut cadence, transition timing); its adaptive/content detectors solve a similar problem to what a custom camera-switch-anomaly detector would need |
| **Maintained** | Yes — active, release as recent as July 2025 |
| **Dependency vs. prior art** | Worth evaluating as an *optional* dependency only if a hand-rolled frame-difference approach (via `ffmpeg`'s own `scdet`/`select='gt(scene,...)'` filters, which avoid an OpenCV dependency) proves insufficient. Pulling in PySceneDetect means adding OpenCV/NumPy, which cuts against the "minimal Python deps" goal — FFmpeg's built-in scene-change filter is the leaner first choice, with PySceneDetect noted as a fallback if its adaptive detector's quality is needed |
| **Sources** | https://github.com/Breakthrough/PySceneDetect ; https://github.com/Breakthrough/PySceneDetect/blob/main/README.md ; https://www.scenedetect.com/copyright/ |

### 7. ImageHash (perceptual hashing)

| Field | Detail |
|---|---|
| **URL** | https://github.com/JohannesBuchner/imagehash |
| **License** | BSD-2-Clause |
| **Capability** | Average hash (aHash), perceptual hash (pHash), difference hash (dHash), wavelet hash, color hash, crop-resistant hash for near-duplicate/similarity comparison of images, built on Pillow/NumPy/SciPy |
| **Overlap** | High conceptually — perceptual hashing of extracted frames is the natural mechanism for detecting the "2 → 1 → 2" slide-flash pattern (hash slide N, N+1, and compare to N-1) and for freeze/near-duplicate confirmation | 
| **Maintained** | Yes — ~3.8k stars, commits within the last year, long-lived (12 years) |
| **Dependency vs. prior art** | Reasonable *lightweight* dependency to consider (Pillow + NumPy + SciPy footprint), but the same pHash-style comparison can also be done with a few lines of NumPy on frames already extracted via `ffmpeg`, avoiding the extra dependency entirely. Recommendation: prototype with a minimal hand-rolled DCT/average-hash first; reach for `imagehash` only if hash quality/robustness becomes a real problem |
| **Sources** | https://github.com/JohannesBuchner/imagehash |

### 8. ffmpeg-quality-metrics

| Field | Detail |
|---|---|
| **URL** | https://github.com/slhck/ffmpeg-quality-metrics |
| **License** | MIT |
| **Capability** | Python CLI/wrapper around FFmpeg's `libvmaf`/`ssim`/`psnr` filters to compute PSNR, SSIM, VMAF, VIF, MSAD between a reference and distorted video, with per-frame and summary stats |
| **Overlap** | Very high for the secondary "source vs. edited delivery" comparison mode — this is essentially the exact SSIM/PSNR comparison workflow described in the request, already implemented and battle-tested |
| **Maintained** | Yes — active, recent releases, requires FFmpeg 7.1+ and Python 3.9+ |
| **Dependency vs. prior art** | Worth treating as a *reference implementation to mirror*, not necessarily a hard dependency: it is a thin wrapper (subprocess + parsing) around `ffmpeg -filter_complex ssim;psnr`, which this project can replicate directly in a few dozen lines to keep the dependency count at zero, while crediting the approach. If schedule pressure favors reuse over reimplementation, it is a safe, small, MIT-licensed dependency (no heavy transitive deps beyond FFmpeg itself) |
| **Sources** | https://github.com/slhck/ffmpeg-quality-metrics ; https://pypi.org/project/ffmpeg-quality-metrics |

### 9. Voice Activity Detection: py-webrtcvad / Silero VAD

| Field | Detail |
|---|---|
| **URL** | https://github.com/wiseman/py-webrtcvad ; https://github.com/snakers4/silero-vad |
| **License** | BSD-3-Clause (webrtcvad); MIT (Silero VAD) |
| **Capability** | `webrtcvad` — fast, lightweight silence/speech-frame classification (Google's WebRTC VAD), tuned more for silence detection than speech quality. `silero-vad` — a small pretrained neural VAD, more accurate at detecting actual speech presence across noise/languages, sub-millisecond CPU inference |
| **Overlap** | Medium — relevant to "no speech" detection as one signal feeding "progression interruption," and as a sanity check layered on top of `silencedetect` (which measures amplitude, not speech presence — a loud non-speech hum would pass `silencedetect` but should still count as "no speech") |
| **Maintained** | Both active; webrtcvad is a thin, stable, rarely-changing wrapper; Silero VAD is actively developed |
| **Dependency vs. prior art** | `ffmpeg silencedetect` should remain the first-line, dependency-free signal for audio-dropout detection. `webrtcvad` is small enough (a single C extension, no ML runtime) to be a defensible *optional* dependency if true speech-presence (vs. just non-silence) becomes necessary; Silero VAD (PyTorch runtime) is too heavy for this project's minimal-deps goal and should stay as prior art only |
| **Sources** | https://github.com/wiseman/py-webrtcvad ; https://github.com/snakers4/silero-vad |

### 10. Slide-transition detection (lecture-video research)

| Field | Detail |
|---|---|
| **Representative projects** | `renebrandel/slide-transition-detector` (https://github.com/renebrandel/slide-transition-detector) — simple frame-difference-based slide extractor; SliTraNet (https://arxiv.org/abs/2202.03540, code: https://github.com/asindel/SliTraNet) — CNN-based slide-transition classifier for lecture video |
| **License** | slide-transition-detector: unspecified/check repo; SliTraNet: research code, license per repo |
| **Capability** | Detecting when a presentation slide changes on screen, using frame differencing or 2D/3D CNN classifiers, developed for lecture-video indexing/note generation, not incident detection |
| **Overlap** | Medium — directly relevant prior art for "slide-advance anomaly" detection (the underlying problem of "did the visible slide change" is the same), but none of the published work addresses the specific "flash forward and revert" (2→1→2) pattern as a *quality incident*; it's framed purely as content indexing |
| **Maintained** | Low/unclear — these are largely academic/demo repos, not actively maintained libraries |
| **Dependency vs. prior art** | Prior art only. The frame-differencing technique (perceptual hash or simple pixel-diff on a cropped slide region, sampled at low FPS) is straightforward enough to implement directly with `ffmpeg` frame extraction + a hash comparison, without adopting research code |
| **Sources** | https://github.com/renebrandel/slide-transition-detector ; https://arxiv.org/abs/2202.03540 ; https://link.springer.com/article/10.1007/s11042-014-1990-6 (SIFT-based slide-transition detection, ~86-87% accuracy) |

### 11. Video anomaly detection research (surveillance-domain)

| Field | Detail |
|---|---|
| **Representative work** | `awesome-video-anomaly-detection` survey collections (e.g., https://github.com/fjchange/awesome-video-anomaly-detection, https://github.com/vt-le/Video-Anomaly-Detection); typical implementations use 3D-CNN autoencoders / reconstruction-error models trained on "normal" surveillance footage |
| **License** | Varies per repo, mostly research/academic |
| **Capability** | Detecting anomalous human activity (violence, intrusion, camera tampering) in CCTV-style footage via learned normalcy models |
| **Overlap** | Low — this is a different problem domain (behavioral/activity anomalies vs. production/technical incidents) and a different technique class (trained deep models needing "normal" training footage vs. deterministic signal-processing rules). It is useful only as a reminder that "anomaly detection" in video is a heavily studied but largely orthogonal field; none of it targets production QC for talks/webinars |
| **Maintained** | Mixed; mostly academic snapshots |
| **Dependency vs. prior art** | Not applicable as a dependency — wrong problem domain and far too heavyweight (GPU training pipelines) for a deterministic, explainable, ffmpeg-first auditor |
| **Sources** | https://github.com/fjchange/awesome-video-anomaly-detection ; https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10255829/ (survey) |

### 12. Acoustic feedback/howling detection

| Field | Detail |
|---|---|
| **Findings** | No mature, general-purpose open-source library was found dedicated to detecting feedback/howling in a recorded file after the fact. Available material is almost entirely real-time DSP research on *suppressing* feedback in live sound-reinforcement/hearing-aid systems (e.g., notch-filter-based howling suppression), not post-hoc detection tools |
| **Overlap** | This appears to be a genuine gap: howling has a distinctive signature (a narrow-band frequency sharply dominating and sustaining) that is well-characterized in the DSP literature but not packaged as an off-the-shelf detector |
| **Maintained / dependency** | N/A — nothing concrete to depend on. This project should implement howling detection itself from first principles (e.g., FFT/spectral-flatness analysis via `ffmpeg`'s `showspectrumpic`/`aformat` output or a lightweight NumPy FFT on extracted PCM, looking for a sustained narrow-band peak well above the noise floor) |
| **Sources** | https://link.springer.com/article/10.1186/s13636-025-00399-1 (howling detection via sparsity measure — algorithm description only, no released tool) |

## Conclusion

The building blocks this project needs — black-frame/freeze/silence detection, loudness/clipping stats, scene-cut detection, perceptual image hashing, VAD, and SSIM/PSNR quality comparison — all have solid, independently maintained open-source precedents (FFmpeg's own filters, `ffmpeg-quality-metrics`, PySceneDetect, `imagehash`, `webrtcvad`), and an ffmpeg/ffprobe-first, low-dependency design is consistent with how the most directly comparable tools (`mediadeepa`, `rendiff-probe`) are built. No project found combines these into an **event-recording-specific forensic auditor** that (a) reasons about presentation-flow semantics like slide-flash-and-revert patterns and camera-switch cadence, (b) frames its output as an evidence-first incident report rather than raw metrics or a live-monitoring dashboard, and (c) includes a dedicated source-vs.-edited-delivery attribution mode to determine whether a defect was pre-existing or introduced downstream. QCTools, Rendiff Probe, and Stream Monitor are the closest general-purpose QC tools but are archival-, generic-broadcast-, or live-monitoring-oriented rather than event/presentation-aware; the slide-transition and howling-detection literature confirms the underlying signals are tractable but has not been packaged for this exact use case. This is a gap worth filling, not a claim that no adjacent tools exist — the differentiation is in domain-specific rule design and evidence-based reporting, not in inventing new low-level signal detectors.
