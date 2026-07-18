from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_JS = (ROOT / "app" / "web" / "app.js").read_text(encoding="utf-8")
INDEX = (ROOT / "app" / "web" / "index.html").read_text(encoding="utf-8")


def test_frontend_co_input_anh_va_preview():
    assert 'id="imageInput"' in INDEX
    assert 'accept="image/jpeg,image/png,image/webp"' in INDEX
    assert 'id="imagePreview"' in INDEX
    assert 'id="imageBtn"' in INDEX


def test_frontend_upload_truoc_roi_gui_attachment_ids():
    assert 'fetch("/api/attachments/images"' in APP_JS
    assert "attachment_ids:" in APP_JS
    assert "message.attachments" in APP_JS
    assert "renderPendingImages" in APP_JS


def test_frontend_cho_phep_gui_chi_co_anh():
    assert 'text || "Nhờ em xem giúp ảnh này."' in APP_JS
    assert "!state.pendingImages.length" in APP_JS
