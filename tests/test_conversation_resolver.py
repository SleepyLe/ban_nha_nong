import json
from types import SimpleNamespace

from app.backend import conversation_resolver


def _context():
    products = [
        {"trade_name": "9X-Actione", "formulation": "4.3EC"},
        {"trade_name": "A-Z annong", "formulation": "0.15EC"},
    ]
    return {
        "products": products,
        "turns": [{
            "user_text": "lúa bị rầy nâu dùng thuốc gì?",
            "assistant": {
                "answer_segments": [{"type": "text", "content": "Có 2 sản phẩm"}],
                "slots": {"crop": "lúa", "pest": "rầy nâu", "region": "an_giang"},
                "products": products,
            },
        }],
    }


def _client(payload: dict):
    class Models:
        @staticmethod
        def generate_content(**_kwargs):
            return SimpleNamespace(text=json.dumps(payload, ensure_ascii=False))

    return SimpleNamespace(models=Models())


def test_llm_chi_viet_lai_cau_noi_tiep_tu_full_history():
    rewritten = conversation_resolver.contextualize(
        "Sản phẩm đầu tiên là của công ty nào?",
        _context(),
        client=_client({
            "is_follow_up": True,
            "standalone_text": "9X-Actione 4.3EC là của công ty nào đăng ký?",
        }),
    )
    assert rewritten == "9X-Actione 4.3EC là của công ty nào đăng ký?"


def test_tu_choi_ten_thuoc_llm_tu_tao_khong_co_trong_history():
    original = "Sản phẩm đầu tiên là của công ty nào?"
    rewritten = conversation_resolver.contextualize(
        original,
        _context(),
        client=_client({
            "is_follow_up": True,
            "standalone_text": "Amistar 250SC là của công ty nào đăng ký?",
        }),
    )
    assert rewritten == original


def test_cau_doc_lap_khong_goi_llm():
    class Models:
        @staticmethod
        def generate_content(**_kwargs):
            raise AssertionError("Không được gọi LLM cho câu độc lập")

    original = "cà phê bị rệp sáp dùng thuốc gì?"
    assert conversation_resolver.contextualize(
        original, _context(), client=SimpleNamespace(models=Models())
    ) == original
