from fastapi.testclient import TestClient

from app.backend import history, pipeline
from app.backend.api import app


def _ask(client: TestClient, text: str, session_id: str | None = None) -> dict:
    response = client.post(
        "/api/ask",
        json={"text": text, "region": "an_giang", "session_id": session_id},
    )
    assert response.status_code == 200
    return response.json()


def test_api_tao_session_id_va_echo_lai():
    client = TestClient(app)
    first = _ask(client, "lúa bị rầy nâu xịt thuốc gì")
    assert first["session_id"].startswith("session-")

    second = _ask(client, "còn xử lý thế nào?", first["session_id"])
    assert second["session_id"] == first["session_id"]


def test_cung_session_ke_thua_cay_va_sau_benh():
    client = TestClient(app)
    session_id = "session-context-rice-001"
    _ask(client, "lúa bị rầy nâu xịt thuốc gì", session_id)

    follow_up = _ask(client, "còn xử lý thế nào?", session_id)
    assert follow_up["slots"]["crop"] == "lúa"
    assert follow_up["slots"]["pest"] == "rầy nâu"


def test_session_khac_khong_bi_lan_ngu_canh():
    client = TestClient(app)
    _ask(client, "lúa bị rầy nâu xịt thuốc gì", "session-isolated-a")

    unrelated = _ask(client, "còn xử lý thế nào?", "session-isolated-b")
    assert unrelated["slots"]["crop"] is None
    assert unrelated["slots"]["pest"] is None


def test_thuoc_nay_dung_thuoc_da_xac_thuc_trong_session():
    session_id = "session-product-reference"
    history.record_session_turn(
        session_id,
        "an_giang",
        "9X-Actione 4.3EC dùng để làm gì?",
        {
            "slots": {"crop": None, "pest": None, "region": "an_giang"},
            "products": [],
        },
        explicit_product=("9X-Actione", "4.3EC"),
    )
    context = history.get_session_context(session_id)

    result = pipeline.answer(
        "thuốc này có tác dụng gì?",
        "an_giang",
        "2026-07-18",
        session_id=session_id,
        _conversation_context=context,
    )
    answer_text = " ".join(
        segment.get("content", "") for segment in result["answer_segments"]
    )
    assert "9X-Actione 4.3EC" in answer_text


def test_xoa_conversation_xoa_luon_bo_nho_session():
    client = TestClient(app)
    session_id = "session-delete-context"
    history.record_session_turn(
        session_id,
        "an_giang",
        "lúa bị rầy nâu",
        {"slots": {"crop": "lúa", "pest": "rầy nâu", "region": "an_giang"}},
    )
    conversation = {
        "id": "chat-delete-context",
        "sessionId": session_id,
        "messages": [],
    }
    assert client.put("/api/conversations/chat-delete-context", json=conversation).status_code == 200
    assert client.delete("/api/conversations/chat-delete-context").status_code == 200
    assert history.get_session_context(session_id) is None


def test_chat_cu_tu_khoi_phuc_ngu_canh_tu_payload_da_luu():
    client = TestClient(app)
    session_id = "session-legacy-conversation"
    conversation = {
        "id": "chat-legacy-context",
        "sessionId": session_id,
        "region": "an_giang",
        "messages": [{
            "id": "message-old",
            "text": "lúa bị rầy nâu xịt thuốc gì",
            "status": "done",
            "answer": {
                "risk_class": "A",
                "slots": {"crop": "lúa", "pest": "rầy nâu", "region": "an_giang"},
                "answer_segments": [],
                "products": [],
            },
        }],
    }
    assert client.put("/api/conversations/chat-legacy-context", json=conversation).status_code == 200

    context = history.get_session_context(session_id)
    assert context["crop"] == "lúa"
    assert context["pest"] == "rầy nâu"

    follow_up = _ask(client, "còn xử lý thế nào?", session_id)
    assert follow_up["slots"]["crop"] == "lúa"
    assert follow_up["slots"]["pest"] == "rầy nâu"


def test_luu_nguyen_cau_hoi_attachment_va_toan_bo_response():
    session_id = "session-full-turn"
    response = {
        "risk_class": "A",
        "answer_segments": [{"type": "text", "content": "Câu trả lời đầy đủ"}],
        "slots": {"crop": "lúa", "pest": "rầy nâu", "region": "an_giang"},
        "products": [{
            "trade_name": "9X-Actione",
            "formulation": "4.3EC",
            "active_ingredient": "Emamectin benzoate",
            "cite": "TT75",
        }],
    }
    history.record_session_turn(
        session_id,
        "an_giang",
        "Ảnh này là thuốc gì?",
        response,
        attachment_ids=["image-abc"],
    )

    context = history.get_session_context(session_id)
    assert context["stored_turn_count"] == 1
    assert context["turns"][0]["user_text"] == "Ảnh này là thuốc gì?"
    assert context["turns"][0]["attachment_ids"] == ["image-abc"]
    assert context["turns"][0]["assistant"]["answer_segments"] == response["answer_segments"]
    assert context["turns"][0]["assistant"]["products"] == response["products"]


def test_session_chi_giu_so_turn_gan_nhat(monkeypatch):
    monkeypatch.setenv("SESSION_MAX_TURNS", "2")
    session_id = "session-bounded-turns"
    for index in range(3):
        history.record_session_turn(
            session_id,
            "an_giang",
            f"câu {index}",
            {
                "risk_class": "B",
                "answer_segments": [{"type": "text", "content": f"trả lời {index}"}],
                "slots": {"crop": None, "pest": None, "region": "an_giang"},
                "products": [],
            },
        )

    context = history.get_session_context(session_id)
    assert context["stored_turn_count"] == 2
    assert [turn["user_text"] for turn in context["turns"]] == ["câu 1", "câu 2"]


def test_tham_chieu_san_pham_dau_tien_trong_danh_sach():
    client = TestClient(app)
    session_id = "session-first-listed-product"
    first = _ask(client, "lúa bị rầy nâu thì dùng thuốc gì?", session_id)
    assert len(first["products"]) >= 2
    first_name = first["products"][0]["trade_name"]
    second_name = first["products"][1]["trade_name"]

    follow_up = _ask(
        client,
        "Sản phẩm đầu tiên được liệt kê là của công ty nào?",
        session_id,
    )
    answer_text = " ".join(
        segment.get("content", "") for segment in follow_up["answer_segments"]
    )
    assert first_name in answer_text
    assert second_name not in answer_text
    assert "đơn vị đăng ký" in answer_text.casefold()


def test_tra_loi_ngan_sau_cau_clarify_duoc_ghep_ngu_canh():
    """Bot vừa hỏi lại ("cây gì?") -> câu đáp ngắn "lúa" phải được ghép thành câu
    độc lập thay vì bị coi là câu hỏi mới (bug demo: trả về trivia An Giang)."""
    from app.backend import conversation_resolver

    class _FakeResp:
        text = '{"is_follow_up": true, "standalone_text": "folpal 50WP dùng cho lúa còn được phép sử dụng không?"}'

    class _FakeModels:
        def generate_content(self, **kwargs):
            return _FakeResp()

    class _FakeClient:
        models = _FakeModels()

    context = {
        "turns": [
            {
                "user_text": "folpal 50WP còn dùng được không",
                "assistant": {
                    "answer_segments": [
                        {
                            "type": "text",
                            "content": "Dạ, bác cho em biết đang trồng cây gì (lúa, cà phê, sầu riêng...) để em tra đúng thông tin cho bác nhé?",
                        }
                    ],
                    "slots": {},
                    "products": [],
                },
            }
        ]
    }
    out = conversation_resolver.contextualize("lúa", context, client=_FakeClient())
    assert out == "folpal 50WP dùng cho lúa còn được phép sử dụng không?"


def test_cau_ngan_khong_co_clarify_truoc_khong_bi_ghep():
    """Không có câu hỏi lại ở lượt trước -> câu ngắn giữ nguyên, không gọi model."""
    from app.backend import conversation_resolver

    class _ExplodingClient:
        class models:  # noqa: N801
            @staticmethod
            def generate_content(**kwargs):
                raise AssertionError("không được gọi model khi gate đóng")

    context = {
        "turns": [
            {
                "user_text": "lúa bị rầy nâu xịt thuốc gì",
                "assistant": {
                    "answer_segments": [
                        {"type": "text", "content": "Dạ, em tìm được 627 sản phẩm còn phép dùng."}
                    ],
                    "slots": {},
                    "products": [],
                },
            }
        ]
    }
    assert conversation_resolver.contextualize("lúa", context, client=_ExplodingClient()) == "lúa"
