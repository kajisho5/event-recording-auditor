"""Localization for report output (report.html / report.md).

Scope: this translates report *prose* -- structural labels (headers,
column names, severity/confidence/category words) and each event's
`observations`/`possible_interpretation` text. It deliberately does NOT
translate machine-readable identifiers (`Event.type`, e.g.
"slide_rollback_pattern") -- those are stable technical identifiers
documented in docs/detection-model.md and used to cross-reference the
code; inventing per-language names for them would break that link.
report.json is intentionally not localized for the same reason: it's the
machine-readable format (spec section 17), and downstream tooling should
be able to rely on a single, stable set of strings there.

Adding a language: add its code to `SUPPORTED_LANGUAGES`, add a column to
every entry in `_UI_STRINGS`/`_SEVERITY`/`_CONFIDENCE`/`_CATEGORY`, and add
a `_<lang>_<event.type>` renderer for each detector type below (or accept
the English fallback -- `translate_event_text` never raises on a missing
renderer, it just returns the original English text).
"""

from __future__ import annotations

from ..timeline import Event

SUPPORTED_LANGUAGES = ("en", "ja")
DEFAULT_LANGUAGE = "en"

_UI_STRINGS: dict[str, dict[str, str]] = {
    "title": {"en": "Event Recording Audit", "ja": "収録監査レポート"},
    "file": {"en": "File", "ja": "ファイル"},
    "duration": {"en": "Duration", "ja": "収録時間"},
    "total_findings": {"en": "Total findings", "ja": "検出件数"},
    "timeline": {"en": "Timeline", "ja": "タイムライン"},
    "detailed_findings": {"en": "Detailed findings", "ja": "詳細な検出内容"},
    "no_findings": {
        "en": "No anomaly candidates were detected.",
        "ja": "異常の候補は検出されませんでした。",
    },
    "col_time": {"en": "Time", "ja": "時刻"},
    "col_duration": {"en": "Duration", "ja": "長さ"},
    "col_category": {"en": "Category", "ja": "カテゴリ"},
    "col_severity": {"en": "Severity", "ja": "深刻度"},
    "col_confidence": {"en": "Confidence", "ja": "確信度"},
    "col_type": {"en": "Type", "ja": "種別"},
    "details": {"en": "details", "ja": "詳細"},
    "detector": {"en": "Detector", "ja": "検出器"},
    "observed": {"en": "Observed", "ja": "観測事実"},
    "possible_interpretation": {
        "en": "Possible interpretation",
        "ja": "考えられる解釈",
    },
    "human_verification_required": {
        "en": "Human verification required.",
        "ja": "人間による確認が必要です。",
    },
    "informational_entry": {
        "en": "Informational entry; human verification not required.",
        "ja": "参考情報であり、確認は不要です。",
    },
    "no_interpretation": {
        "en": "(insufficient evidence for an interpretation)",
        "ja": "(解釈を示すには根拠が不十分です)",
    },
    "evidence": {"en": "Evidence", "ja": "証拠"},
    "limitations": {"en": "Limitations", "ja": "制限事項・注意点"},
    "none": {"en": "(none)", "ja": "(なし)"},
    "unknown_file": {"en": "(unknown file)", "ja": "(不明なファイル)"},
    "unknown_duration": {"en": "unknown", "ja": "不明"},
    "batch_title": {
        "en": "Event Recording Audit — Batch Summary",
        "ja": "収録監査レポート — 複数会場サマリー",
    },
    "col_venue": {"en": "Venue / File", "ja": "会場 / ファイル"},
    "col_status": {"en": "Status", "ja": "ステータス"},
    "col_report": {"en": "Report", "ja": "レポート"},
    "status_ok": {"en": "ok", "ja": "正常"},
    "status_error": {"en": "error", "ja": "エラー"},
    "total_venues": {"en": "Venues processed", "ja": "処理した会場数"},
}

_SEVERITY = {
    "low": {"en": "low", "ja": "低"},
    "medium": {"en": "medium", "ja": "中"},
    "high": {"en": "high", "ja": "高"},
}
_CONFIDENCE = _SEVERITY
_CATEGORY = {
    "video": {"en": "video", "ja": "映像"},
    "audio": {"en": "audio", "ja": "音声"},
    "presentation": {"en": "presentation", "ja": "プレゼンテーション"},
    "switching": {"en": "switching", "ja": "切り替え"},
    "progress": {"en": "progress", "ja": "進行"},
    "continuity": {"en": "continuity", "ja": "連続性"},
    "post_production": {"en": "post_production", "ja": "ポストプロダクション"},
}


def _lookup(table: dict[str, dict[str, str]], key: str, lang: str) -> str:
    entry = table.get(key)
    if entry is None:
        return key
    return entry.get(lang, entry[DEFAULT_LANGUAGE])


def t(key: str, lang: str) -> str:
    return _lookup(_UI_STRINGS, key, lang)


def severity_label(value: str, lang: str) -> str:
    return _lookup(_SEVERITY, value, lang)


def confidence_label(value: str, lang: str) -> str:
    return _lookup(_CONFIDENCE, value, lang)


def category_label(value: str, lang: str) -> str:
    return _lookup(_CATEGORY, value, lang)


# --- Per-detector-type Japanese renderers ----------------------------------
# Each takes the full Event (not just `measurements`) so it can disambiguate
# which branch of the detector's logic produced it from fields that are
# already stored on the event (severity/confidence/measurements/observation
# count), without duplicating the detectors' decision logic here.


def _ja_blackout(e: Event) -> tuple[list[str], str]:
    duration = e.measurements.get("duration", e.duration)
    return (
        [f"映像が完全な黒画面として{duration:.2f}秒間計測されました。"],
        "信号断・意図しない黒画面への切り替わりの可能性、または意図的な黒転換の可能性があります。"
        "この録画データだけでは意図の有無は判断できません。",
    )


def _ja_freeze(e: Event) -> tuple[list[str], str]:
    duration = e.measurements.get("duration", e.duration)
    audio_active = e.measurements.get("audio_active_during", False)
    observations = [f"映像に{duration:.2f}秒間、計測可能な変化がありませんでした。"]

    if len(e.observations) == 1:
        # No audio track was available to correlate against.
        interpretation = (
            "映像のフリーズ(信号停止)の可能性、または単に静止したカットの可能性があります。"
            "判別に使える音声トラックがありませんでした。"
        )
    elif audio_active:
        observations.append("この区間、音声は活動を継続していました。")
        interpretation = (
            "通常の静止カットである可能性が高いです。区間中も音声の活動が続いており、"
            "技術的なフリーズとは整合しません。"
        )
    else:
        observations.append("この区間、音声はほぼ無音でした。")
        interpretation = (
            "映像のフリーズ(信号停止)の可能性があります: 一定時間、映像の変化も音声の"
            "活動も検出されませんでした。"
        )
    return observations, interpretation


def _ja_clipping(e: Event) -> tuple[list[str], str]:
    duration = e.measurements.get("duration", e.duration)
    peak = e.measurements.get("max_peak_db")
    flat = e.measurements.get("max_flat_factor")
    return (
        [
            f"音声のピークレベルが{peak:.2f} dBFSに達し、波形の頭打ち(フラット)係数"
            f"{flat:.1f}の状態が{duration:.2f}秒間続きました。"
        ],
        "音声のクリッピング(音割れ)の可能性があります(入力ゲイン過大、または"
        "ミキサー・エンコーダーの過負荷など)。",
    )


def _ja_possible_audio_dropout(e: Event) -> tuple[list[str], str]:
    duration = e.measurements.get("duration", e.duration)
    return (
        [
            f"音声レベルがほぼ無音まで低下し、{duration:.2f}秒間続きました。",
            "この区間の直前、一定時間は音声が活動していました。",
            "この区間の直後も、一定時間は音声が活動を再開していました。",
        ],
        "意図的な間ではなく、マイクや回線の瞬断による音声ドロップアウトの可能性があります"
        "(周囲の音声活動から判断)。ただし、レベル情報だけでは非常に短い意図的な間との"
        "確実な区別はできません。",
    )


def _ja_channel_missing(e: Event) -> tuple[list[str], str]:
    duration = e.measurements.get("duration", e.duration)
    levels = e.measurements.get("channel_rms_db", {})
    levels_str = ", ".join(f"ch{ch}: {lv:.1f} dBFS" for ch, lv in sorted(levels.items()))
    return (
        [f"チャンネル間でレベル差が{duration:.2f}秒間続きました(区間終了時点: {levels_str})。"],
        "マイクやチャンネルの脱落、または回線の不具合の可能性があります: 一方のチャンネルが"
        "活動している間、もう一方はほぼ無音の状態が続きました。意図的にモノラル音声を"
        "片方のチャンネルにルーティングしている場合も同じ見え方になるため、この録画データ"
        "だけでは区別できません。",
    )


def _ja_channel_imbalance(e: Event) -> tuple[list[str], str]:
    duration = e.measurements.get("duration", e.duration)
    levels = e.measurements.get("channel_rms_db", {})
    levels_str = ", ".join(f"ch{ch}: {lv:.1f} dBFS" for ch, lv in sorted(levels.items()))
    return (
        [f"チャンネル間でレベル差が{duration:.2f}秒間続きました(区間終了時点: {levels_str})。"],
        "チャンネル間で持続的なレベル差があります。本当のルーティング/ゲインの問題の"
        "可能性もあれば、意図的なミックス(パンを振った音源など)の可能性もあります。"
        "人間による確認を推奨します。",
    )


def _ja_slide_rollback_pattern(e: Event) -> tuple[list[str], str]:
    seq = e.measurements.get("sequence", [])
    durations = e.measurements.get("sequence_durations", [])
    confirmed_repeat = e.measurements.get("confirmed_repeat", False)
    severity, confidence = e.severity.value, e.confidence.value

    def dur(i: int) -> str:
        return f"{durations[i]:.2f}秒間" if i < len(durations) else ""

    observations = []
    if len(seq) >= 3:
        observations.append(f"スライド状態{seq[0]}が{dur(0)}表示されました。")
        observations.append(f"続いてスライド状態{seq[1]}が{dur(1)}表示されました。")
        observations.append(f"その後、スライド状態{seq[0]}に戻り、{dur(2)}表示されました。")
    if confirmed_repeat and len(seq) >= 4:
        observations.append(f"その後、再びスライド状態{seq[1]}が{dur(3)}表示されました。")

    if severity == "medium" and confidence == "medium":
        interpretation = (
            "早すぎるスライド送りの後、発表者/オペレーターが元に戻して修正した可能性と"
            "一致します: 後のスライドの最初の表示が、戻った後の表示に比べて短時間でした。"
        )
    elif severity == "medium" and confidence == "low":
        interpretation = (
            "早すぎるスライド送りとその修正の可能性と一致しますが、この後同じパターンが"
            "繰り返されておらず、パターンの確証は得られていません。"
        )
    else:
        interpretation = (
            "スライド状態への再訪問が検出されましたが、間に挟まったスライドの表示時間が"
            "長く、修正というより意図的な過去スライドへの遷移である可能性が高いです。"
        )
    return observations, interpretation


def _ja_brief_unexpected_slide(e: Event) -> tuple[list[str], str]:
    duration = e.measurements.get("duration", e.duration)
    prev_state = e.measurements.get("previous_state")
    next_state = e.measurements.get("next_state")
    return (
        [
            f"スライド状態がわずか{duration:.2f}秒間しか表示されませんでした"
            f"(スライド状態{prev_state}とスライド状態{next_state}の間)。"
        ],
        "意図しない短時間のスライド表示の可能性があります(早すぎるスライド送り、"
        "誤操作によるクリック、または別の状態として捉えられたアニメーションの一コマなど)。"
        "参考資料をすばやく意図的にめくった可能性も考えられます。",
    )


def _ja_progression_interruption(e: Event) -> tuple[list[str], str]:
    has_audio_track = e.confidence.value == "medium"
    observations = [
        "この区間、意味のある映像の変化は検出されませんでした。",
        "この区間、スライド/プレゼンテーションの状態は変化しませんでした。",
    ]
    if has_audio_track:
        observations.append("この区間、音声はほぼ無音の状態が続きました。")
    else:
        observations.append("これを裏付けるための音声トラックがありませんでした。")

    interpretation = (
        "イベント進行の中断の可能性があります: カメラの動き・音声の活動・スライドの"
        "変化のいずれも、長時間にわたって観測されませんでした。休憩、会場が把握して"
        "いる技術的な中断、または長時間の無音の作業(観客が課題に取り組んでいる、など)"
        "である可能性も考えられ、この録画データだけでは区別できません。"
    )
    return observations, interpretation


def _ja_possible_feedback_howling(e: Event) -> tuple[list[str], str]:
    freq = e.measurements.get("dominant_frequency_hz", 0.0)
    concentration = e.measurements.get("max_concentration", 0.0)
    duration = e.measurements.get("duration", e.duration)
    return (
        [
            f"約{freq:.0f} Hzの狭帯域スペクトルのピークが{duration:.2f}秒間持続しました。",
            f"ピーク帯域のエネルギー集中度は帯域内全エネルギーの{concentration:.0%}に達しました。",
        ],
        "音声のフィードバック/ハウリングの可能性があります。これは実験的なヒューリスティック"
        "検出器であり、持続的な楽音・テストトーン・部屋の共鳴などとの確実な区別はできません。"
        "人間による確認が必要です。",
    )


_JA_RENDERERS = {
    "blackout": _ja_blackout,
    "freeze": _ja_freeze,
    "clipping": _ja_clipping,
    "possible_audio_dropout": _ja_possible_audio_dropout,
    "channel_missing": _ja_channel_missing,
    "channel_imbalance": _ja_channel_imbalance,
    "slide_rollback_pattern": _ja_slide_rollback_pattern,
    "brief_unexpected_slide": _ja_brief_unexpected_slide,
    "progression_interruption": _ja_progression_interruption,
    "possible_feedback_howling": _ja_possible_feedback_howling,
}

_RENDERERS: dict[str, dict[str, callable]] = {
    "ja": _JA_RENDERERS,
}


def translate_event_text(event: Event, lang: str) -> tuple[list[str], str]:
    """Return (observations, possible_interpretation) for `event` in `lang`.

    Falls back to the event's original (English) text if `lang` is "en",
    unsupported, or has no renderer registered for `event.type` -- this
    must never raise, since an untranslated finding is far better than a
    crashed report.
    """
    if lang == DEFAULT_LANGUAGE:
        return list(event.observations), event.possible_interpretation or ""

    renderer = _RENDERERS.get(lang, {}).get(event.type)
    if renderer is None:
        return list(event.observations), event.possible_interpretation or ""

    try:
        return renderer(event)
    except Exception:  # noqa: BLE001 - a translation bug must not break the report
        return list(event.observations), event.possible_interpretation or ""
