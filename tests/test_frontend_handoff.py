from pathlib import Path


APP_JS = (
    Path(__file__).resolve().parents[1] / "app" / "web" / "app.js"
).read_text(encoding="utf-8")


def test_partial_database_gap_renders_officer_handoff_button() -> None:
    assert 'segment.type === "handoff_warning"' in APP_JS
    assert "renderHandoff(segment, message.answer" in APP_JS
    assert 'button.textContent = "Gửi cán bộ khuyến nông"' in APP_JS


def test_empty_placeholder_note_is_not_rendered() -> None:
    assert "if (segment.note && segment.note !== segment.dose_text)" in APP_JS
