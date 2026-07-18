from __future__ import annotations

import io
import json
from types import SimpleNamespace
from unittest.mock import Mock

from fastapi.testclient import TestClient
from PIL import Image

from app.backend import api, clarifications, image_resolver, image_uploads, input_resolver


client = TestClient(api.app)


def _png_bytes(size=(64, 48), color=(40, 130, 70)) -> bytes:
    output = io.BytesIO()
    Image.new("RGB", size, color).save(output, format="PNG")
    return output.getvalue()


def _analysis(**overrides) -> image_resolver.ImageAnalysis:
    payload = {
        "image_type": "plant_symptom",
        "quality": "good",
        "crop_candidates": ["sầu riêng"],
        "pest_candidates": ["thán thư"],
        "visible_symptoms": ["đốm nâu trên lá"],
        "summary_vi": "Lá có đốm nâu.",
        "confidence": 0.82,
        "needs_confirmation": True,
    }
    payload.update(overrides)
    return image_resolver.ImageAnalysis(**payload)


def test_upload_chuan_hoa_anh_va_doc_lai_duoc(tmp_path, monkeypatch):
    monkeypatch.setattr(image_uploads, "UPLOAD_DIR", tmp_path)

    response = client.post(
        "/api/attachments/images",
        files={"images": ("la-sau-rieng.png", _png_bytes(), "image/png")},
    )

    assert response.status_code == 200
    attachment = response.json()["attachments"][0]
    assert attachment["media_type"] == "image/png"
    assert attachment["width"] == 64
    assert attachment["height"] == 48
    assert attachment["url"].endswith(attachment["attachment_id"])
    fetched = client.get(attachment["url"])
    assert fetched.status_code == 200
    assert fetched.headers["content-type"].startswith("image/png")
    with Image.open(io.BytesIO(fetched.content)) as image:
        assert image.size == (64, 48)


def test_upload_tu_choi_file_gia_anh(tmp_path, monkeypatch):
    monkeypatch.setattr(image_uploads, "UPLOAD_DIR", tmp_path)

    response = client.post(
        "/api/attachments/images",
        files={"images": ("fake.jpg", b"not-an-image", "image/jpeg")},
    )

    assert response.status_code == 422
    assert "không phải ảnh" in response.json()["detail"]


def test_anh_het_han_khong_doc_duoc(tmp_path, monkeypatch):
    monkeypatch.setattr(image_uploads, "UPLOAD_DIR", tmp_path)
    record = image_uploads.store_image("leaf.png", _png_bytes())
    metadata_path = tmp_path / f"{record.attachment_id}.json"
    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    payload["expires_at"] = 0
    metadata_path.write_text(json.dumps(payload), encoding="utf-8")

    response = client.get(f"/api/attachments/images/{record.attachment_id}")

    assert response.status_code == 404
    assert not record.path.exists()


def test_ask_co_attachment_dung_noi_dung_da_duoc_resolve(tmp_path, monkeypatch):
    monkeypatch.setattr(image_uploads, "UPLOAD_DIR", tmp_path)
    record = image_uploads.store_image("label.png", _png_bytes())
    analysis = _analysis(
        image_type="product_label",
        product_name="9X-Actione",
        formulation="4.3EC",
        crop_candidates=[],
        pest_candidates=[],
        visible_symptoms=[],
    )
    monkeypatch.setattr(
        api.image_resolver,
        "resolve_images",
        lambda *_args, **_kwargs: image_resolver.MultimodalResolution(
            analysis=analysis,
            augmented_text="Thuốc 9X-Actione 4.3EC dùng để làm gì?",
        ),
    )
    answer = {
        "risk_class": "B",
        "answer_segments": [{"type": "text", "content": "Đã tra cứu."}],
        "slots": {"crop": None, "pest": None, "region": "an_giang"},
        "products": [],
    }
    pipeline_answer = Mock(return_value=answer)
    monkeypatch.setattr(api.pipeline, "answer", pipeline_answer)

    response = client.post(
        "/api/ask",
        json={
            "text": "Thuốc này dùng để làm gì?",
            "region": "an_giang",
            "session_id": "image-label-session",
            "attachment_ids": [record.attachment_id],
        },
    )

    assert response.status_code == 200
    assert pipeline_answer.call_args.args[0] == "Thuốc 9X-Actione 4.3EC dùng để làm gì?"


def test_gia_thuyet_tu_anh_bat_buoc_xac_nhan_va_duoc_luu(tmp_path, monkeypatch):
    monkeypatch.setattr(image_uploads, "UPLOAD_DIR", tmp_path / "uploads")
    monkeypatch.setenv("CLARIFICATION_DB_PATH", str(tmp_path / "clarifications.db"))
    record = image_uploads.store_image("leaf.png", _png_bytes())
    crop = input_resolver.EntityCandidate(
        "crop:sau rieng", "crop", "sầu riêng", score=82, match_type="image_hypothesis"
    )
    pest = input_resolver.EntityCandidate(
        "pest:than thu", "pest", "thán thư", score=82, match_type="image_hypothesis"
    )
    review = input_resolver.InputReview(
        action="confirm",
        original_text="Cây bị gì vậy?",
        product=None,
        crop=crop,
        pest=pest,
        message="Bác xác nhận đây có thể là sầu riêng bị thán thư không ạ?",
        reason_code="image_symptom_hypothesis",
    )
    monkeypatch.setattr(
        api.image_resolver,
        "resolve_images",
        lambda *_args, **_kwargs: image_resolver.MultimodalResolution(
            analysis=_analysis(), review=review
        ),
    )

    response = client.post(
        "/api/ask",
        json={
            "text": "Cây bị gì vậy?",
            "region": "dak_lak",
            "session_id": "image-symptom-session",
            "attachment_ids": [record.attachment_id],
        },
    )

    assert response.status_code == 200
    assert "xác nhận" in response.json()["answer_segments"][0]["content"]
    pending = clarifications.get("image-symptom-session")
    assert pending["crop"]["canonical"] == "sầu riêng"
    assert pending["pest"]["canonical"] == "thán thư"


def test_gemini_multimodal_nhan_text_va_bytes_anh(monkeypatch):
    class Models:
        def generate_content(self, **kwargs):
            assert kwargs["model"] == "gemini-3.1-flash-lite"
            content = kwargs["contents"][0]
            assert len(content.parts) == 2
            assert content.parts[1].inline_data.mime_type == "image/png"
            return SimpleNamespace(text=_analysis().model_dump_json())

    monkeypatch.setenv("IMAGE_REVIEW_MODE", "auto")
    result = image_resolver.analyze_images(
        "Lá bị gì?",
        [image_uploads.LoadedImage("id", "image/png", _png_bytes())],
        client=SimpleNamespace(models=Models()),
    )

    assert result.image_type == "plant_symptom"
    assert result.needs_confirmation is True


def test_schema_multimodal_khong_gui_additional_properties_google_khong_ho_tro():
    assert "additionalProperties" not in image_resolver.ImageAnalysis.model_json_schema()


def test_resolver_nhan_dien_nhan_thuoc_chi_dua_ten_da_doi_chieu():
    analysis = _analysis(
        image_type="product_label",
        product_name="9X-Actione",
        formulation="4.3EC",
        crop_candidates=[],
        pest_candidates=[],
        visible_symptoms=[],
    )

    resolution = image_resolver._product_resolution(
        "Thuốc này dùng để làm gì?", analysis
    )

    assert resolution.review is None
    assert "9X-Actione 4.3EC" in resolution.augmented_text
