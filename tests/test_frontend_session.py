from pathlib import Path


APP_JS = (Path(__file__).resolve().parents[1] / "app" / "web" / "app.js").read_text(encoding="utf-8")


def test_frontend_sua_hoi_thoai_cu_thieu_session_id():
    assert "function validSessionId" in APP_JS
    assert "sessionId: validSessionId(conversation.sessionId)" in APP_JS
    assert "missingSessionIds" in APP_JS


def test_frontend_gui_va_nhan_lai_session_id():
    assert "session_id: conversation.sessionId" in APP_JS
    assert "body.session_id" in APP_JS
    assert "body.session_turn_limit" in APP_JS
    assert "conversation.messages.splice" in APP_JS
