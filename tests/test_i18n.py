from event_recording_auditor.reporting import i18n
from event_recording_auditor.timeline import Category, Confidence, Event, Severity


def _blackout_event() -> Event:
    return Event(
        start=1.0,
        end=3.0,
        category=Category.VIDEO,
        type="blackout",
        severity=Severity.HIGH,
        confidence=Confidence.HIGH,
        observations=["Video was measured as fully black for 2.00s."],
        measurements={"duration": 2.0},
        possible_interpretation=(
            "Possible blackout (signal loss, source cut to black unexpectedly) or "
            "an intentional black transition. The recording alone does not "
            "establish intent."
        ),
        detector="blackout",
    )


def test_translate_event_text_defaults_to_english():
    event = _blackout_event()
    observations, interpretation = i18n.translate_event_text(event, "en")
    assert observations == event.observations
    assert interpretation == event.possible_interpretation


def test_translate_event_text_renders_japanese_for_known_type():
    event = _blackout_event()
    observations, interpretation = i18n.translate_event_text(event, "ja")
    assert observations != event.observations
    assert "2.00秒" in observations[0]
    assert "黒画面" in observations[0]
    assert interpretation != event.possible_interpretation


def test_translate_event_text_falls_back_for_unknown_type_and_language():
    event = _blackout_event()
    event.type = "some_future_detector_type"
    observations, interpretation = i18n.translate_event_text(event, "ja")
    assert observations == event.observations
    assert interpretation == event.possible_interpretation

    # Unsupported language code should also fall back rather than raising.
    observations, interpretation = i18n.translate_event_text(event, "fr")
    assert observations == event.observations


def test_ui_labels_have_both_languages():
    for lang in i18n.SUPPORTED_LANGUAGES:
        assert i18n.t("title", lang)
        assert i18n.severity_label("high", lang)
        assert i18n.category_label("video", lang)
