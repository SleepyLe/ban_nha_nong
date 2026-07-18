from unittest.mock import Mock

from app.backend import pipeline, registry_agent, web_grounding


class _Response:
    def __init__(self, payload, error=None):
        self.payload = payload
        self.error = error

    def raise_for_status(self):
        if self.error is not None:
            raise self.error

    def json(self):
        return self.payload


class _Client:
    def __init__(self, payload, error=None):
        self.response = _Response(payload, error)
        self.calls = []

    def post(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.response

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


def _tavily_payload(answer="Dạ, đây là thông tin đã tìm được."):
    return {
        "answer": answer,
        "results": [
            {
                "title": "Cơ quan chuyên môn",
                "url": "https://example.gov.vn/huong-dan",
                "content": "Nội dung nguồn",
            }
        ],
        "request_id": "request-1",
        "usage": {"credits": 1},
    }


def _web_result():
    return {
        "text": "Dạ, theo nguồn mới tìm được, đây là thông tin tham khảo.",
        "citations": [
            {"source": "Cơ quan chuyên môn", "url": "https://example.gov.vn/huong-dan"}
        ],
        "grounded": True,
    }


def test_tavily_search_goi_rest_va_yeu_cau_cau_tra_loi_co_nguon(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "test-key")
    client = _Client(_tavily_payload())

    result = web_grounding.search_and_answer(
        "Cách chăm cây mùa mưa?",
        "dak_lak",
        fallback_reason="internal_rag_not_grounded",
        on_date="2026-07-18",
        client=client,
    )

    assert result["grounded"] is True
    assert result["citations"] == [
        {"source": "Cơ quan chuyên môn", "url": "https://example.gov.vn/huong-dan"}
    ]
    assert result["provider"] == "tavily"
    assert result["usage"] == {"credits": 1}
    assert len(client.calls) == 1
    args, kwargs = client.calls[0]
    assert args[0] == web_grounding.TAVILY_SEARCH_URL
    assert kwargs["headers"]["Authorization"] == "Bearer test-key"
    assert kwargs["json"]["search_depth"] == "basic"
    assert kwargs["json"]["include_answer"] == "advanced"
    assert kwargs["json"]["country"] == "vietnam"
    assert "Việt Nam" in kwargs["json"]["query"]
    assert "nguồn chính thức mới nhất" in kwargs["json"]["query"]


def test_query_ten_thuoc_khong_bi_lech_boi_khu_vuc_va_ngay():
    query = web_grounding._build_query(
        "Thuốc 9X-Actione dùng để làm gì?",
        "an_giang",
        None,
        None,
        "unresolved_product_uses_question",
        "2026-07-18",
    )

    assert "9X-Actione" in query
    assert "4.3EC" in query
    assert "An Giang" not in query
    assert "2026-07-18" not in query
    assert "thuốc bảo vệ thực vật" in query


def test_tavily_tu_choi_ket_qua_khong_nhac_dung_ten_thuoc(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "test-key")
    payload = {
        "answer": "X9 là thực phẩm hỗ trợ giảm cân.",
        "results": [
            {
                "title": "Viên giảm cân X9",
                "url": "https://example.com/x9",
                "content": "Sản phẩm hỗ trợ giảm cân.",
            }
        ],
    }

    result = web_grounding.search_and_answer(
        "Thuốc 9X-Actione 4.3EC dùng để làm gì?",
        "an_giang",
        client=_Client(payload),
    )

    assert result["grounded"] is False
    assert result["text"] == ""
    assert result["citations"] == []


def test_tavily_thieu_citation_thi_fail_closed(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "test-key")
    result = web_grounding.search_and_answer(
        "Câu hỏi",
        "an_giang",
        client=_Client({"answer": "Một câu trả lời không có nguồn.", "results": []}),
    )

    assert result["text"] == ""
    assert result["citations"] == []
    assert result["grounded"] is False


def test_tavily_http_error_duoc_chuyen_cho_pipeline(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "test-key")
    client = _Client({}, error=RuntimeError("429 quota exceeded"))

    try:
        web_grounding.search_and_answer(
            "Câu hỏi",
            "an_giang",
            client=client,
        )
    except RuntimeError as exc:
        assert "429" in str(exc)
    else:
        raise AssertionError("expected Tavily HTTP error")
    assert len(client.calls) == 1


def test_web_search_chi_bat_khi_co_tavily_key(monkeypatch):
    monkeypatch.setenv("WEB_SEARCH_MODE", "auto")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-key-khong-duoc-dung-cho-web")
    # Giá trị rỗng ngăn load_dotenv nạp key thật từ .env trong unit test.
    monkeypatch.setenv("TAVILY_API_KEY", "")
    assert web_grounding.enabled() is False

    monkeypatch.setenv("TAVILY_API_KEY", "test-key")
    assert web_grounding.enabled() is True


def test_tavily_default_client_khong_ke_thua_proxy_moi_truong(monkeypatch):
    import httpx

    monkeypatch.setenv("WEB_SEARCH_MODE", "auto")
    monkeypatch.setenv("TAVILY_API_KEY", "test-key")
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:9")
    client = _Client(_tavily_payload())
    options = {}

    def client_factory(**kwargs):
        options.update(kwargs)
        return client

    monkeypatch.setattr(httpx, "Client", client_factory)
    result = web_grounding.search_and_answer("Cách chăm cây?", "dak_lak")

    assert result["grounded"] is True
    assert options["trust_env"] is False


def test_loi_ket_noi_tavily_khong_bi_bao_nham_la_het_quota(monkeypatch):
    import httpx

    monkeypatch.setattr(web_grounding, "enabled", lambda: True)
    monkeypatch.setattr(
        web_grounding,
        "search_and_answer",
        Mock(side_effect=httpx.ConnectError("proxy refused connection")),
    )

    result = pipeline.answer(
        "Thuốc 9x actinone dùng để làm gì?",
        "an_giang",
        "2026-07-18",
        _skip_input_review=True,
    )
    content = " ".join(
        segment.get("content", "") for segment in result["answer_segments"]
    )

    assert "không thể kết nối" in content
    assert "hết quota" not in content


def test_warning_nam_cuoi_noi_dung_web_search():
    segments = web_grounding.answer_segments(_web_result())

    assert segments[0]["type"] == "text"
    assert segments[0]["content"].endswith(web_grounding.WEB_SEARCH_WARNING)
    assert any(segment["type"] == "citation" for segment in segments)


def test_cau_hoi_cong_dung_san_pham_uu_tien_registry_truoc_tavily(monkeypatch):
    monkeypatch.setenv("WEB_SEARCH_MODE", "auto")
    monkeypatch.setattr(web_grounding, "enabled", lambda: True)
    search = Mock(return_value=_web_result())
    monkeypatch.setattr(web_grounding, "search_and_answer", search)

    result = pipeline.answer(
        "Thuốc 9X-Actione dùng để làm gì?",
        "an_giang",
        "2026-07-18",
        _skip_input_review=True,
    )

    content = " ".join(
        segment.get("content", "") for segment in result["answer_segments"]
    )
    search.assert_not_called()
    assert web_grounding.WEB_SEARCH_WARNING not in content
    assert "sâu cuốn lá" in content
    assert "bắp cải" in content
    assert "hiện còn được phép sử dụng" not in content
    assert any(segment["type"] == "citation" for segment in result["answer_segments"])


def test_ten_thuoc_go_sai_van_di_web_khong_roi_vao_hoi_cay(monkeypatch):
    monkeypatch.setenv("WEB_SEARCH_MODE", "auto")
    monkeypatch.setattr(web_grounding, "enabled", lambda: True)
    search = Mock(return_value=_web_result())
    monkeypatch.setattr(web_grounding, "search_and_answer", search)

    result = pipeline.answer(
        "Thuốc 9x actinone dùng để làm gì?",
        "an_giang",
        "2026-07-18",
        _skip_input_review=True,
    )

    content = " ".join(
        segment.get("content", "") for segment in result["answer_segments"]
    )
    assert search.call_count == 1
    assert search.call_args.kwargs["fallback_reason"] == "unresolved_product_uses_question"
    assert web_grounding.WEB_SEARCH_WARNING in content
    assert "đang trồng cây gì" not in content


def test_web_search_qua_quota_hien_loi_ro_rang_khong_quay_ve_hoi_cay(monkeypatch):
    monkeypatch.setenv("WEB_SEARCH_MODE", "auto")
    monkeypatch.setattr(web_grounding, "enabled", lambda: True)
    monkeypatch.setattr(
        web_grounding,
        "search_and_answer",
        Mock(side_effect=RuntimeError("429 RESOURCE_EXHAUSTED")),
    )

    result = pipeline.answer(
        "Thuốc 9x actinone dùng để làm gì?",
        "an_giang",
        "2026-07-18",
        _skip_input_review=True,
    )

    content = " ".join(
        segment.get("content", "") for segment in result["answer_segments"]
    )
    assert "hết quota" in content
    assert "đang trồng cây gì" not in content
    assert any(segment["type"] == "abstain" for segment in result["answer_segments"])


def test_registry_rong_thi_di_web(monkeypatch):
    monkeypatch.setenv("WEB_SEARCH_MODE", "auto")
    monkeypatch.setattr(web_grounding, "enabled", lambda: True)
    search = Mock(return_value=_web_result())
    monkeypatch.setattr(web_grounding, "search_and_answer", search)

    result = pipeline.answer(
        "Sầu riêng bị ốc bươu vàng thì có thuốc nào được đăng ký không?",
        "dak_lak",
        "2026-07-18",
        _skip_input_review=True,
    )

    assert search.call_count == 1
    assert search.call_args.kwargs["fallback_reason"] == "registry_has_no_registered_products"
    assert web_grounding.WEB_SEARCH_WARNING in result["answer_segments"][0]["content"]


def test_ket_luan_not_registered_khong_bi_web_ghi_de(monkeypatch):
    monkeypatch.setattr(web_grounding, "enabled", lambda: True)
    search = Mock(return_value=_web_result())
    monkeypatch.setattr(web_grounding, "search_and_answer", search)

    result = pipeline.answer(
        "Biocare WP dùng trị thán thư cho cà phê được không?",
        "dak_lak",
        "2026-07-18",
        _skip_input_review=True,
    )

    content = " ".join(
        segment.get("content", "") for segment in result["answer_segments"]
    )
    search.assert_not_called()
    assert "không tìm thấy đăng ký chính thức" in content


def test_loi_database_khong_duoc_che_bang_web_search(monkeypatch):
    monkeypatch.setattr(web_grounding, "enabled", lambda: True)
    search = Mock(return_value=_web_result())
    monkeypatch.setattr(web_grounding, "search_and_answer", search)
    monkeypatch.setattr(
        registry_agent,
        "execute_tool",
        Mock(side_effect=RuntimeError("database unavailable")),
    )

    result = pipeline.answer(
        "Lúa bị rầy nâu thì xịt thuốc gì?",
        "an_giang",
        "2026-07-18",
        _skip_input_review=True,
    )

    search.assert_not_called()
    assert any(segment["type"] == "abstain" for segment in result["answer_segments"])
