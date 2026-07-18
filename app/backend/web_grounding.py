"""Web fallback bằng Tavily Search.

Module này chỉ được gọi khi tool/database/KB nội bộ không có câu trả lời phù hợp.
Một kết quả chỉ được dùng khi Tavily trả cả câu trả lời tổng hợp và ít nhất một
URL nguồn hợp lệ; nếu thiếu nguồn, caller giữ nguyên nhánh abstain hiện có.
"""
from __future__ import annotations

import os
import re
import unicodedata
from typing import Any
from urllib.parse import urlparse

TAVILY_SEARCH_URL = "https://api.tavily.com/search"
DEFAULT_SEARCH_DEPTH = "basic"
DEFAULT_MAX_RESULTS = 5
DEFAULT_TIMEOUT_SECONDS = 20.0
_VALID_SEARCH_DEPTHS = {"basic", "advanced", "fast", "ultra-fast"}

WEB_SEARCH_WARNING = (
    "⚠️ Lưu ý: Câu trả lời này được tổng hợp từ kết quả tìm kiếm trên web, không phải "
    "hoàn toàn từ cơ sở dữ liệu đã được kiểm chứng của hệ thống. Bác nên kiểm tra các "
    "nguồn trích dẫn và tham khảo cán bộ chuyên môn trước khi áp dụng."
)

_REGION_NAMES = {"an_giang": "An Giang", "dak_lak": "Đắk Lắk"}
_PRODUCT_INTENT_RE = re.compile(
    r"\bthuoc\s+(.+?)(?:\s+dung\b|\s+tac\s+dung\b|\s+cong\s+dung\b|\s+tri\b|[?.!,]|$)"
)
_PRODUCT_ORIGINAL_RE = re.compile(
    # Không coi dấu chấm là kết thúc vì formulation thường có dạng ``4.3EC``.
    r"\bthuốc\s+(.+?)(?:\s+(?:dùng(?:\s+để)?|tác\s+dụng|công\s+dụng|trị)\b|[?!,]|$)",
    re.IGNORECASE,
)


def enabled() -> bool:
    """Bật ở mode ``auto/on`` khi có Tavily key; ``off`` luôn vô hiệu hóa."""
    from dotenv import load_dotenv

    load_dotenv()
    mode = os.environ.get("WEB_SEARCH_MODE", "auto").strip().lower()
    if mode in {"off", "0", "false", "disabled"}:
        return False
    return bool(os.environ.get("TAVILY_API_KEY"))


def _api_key() -> str:
    from dotenv import load_dotenv

    load_dotenv()
    value = os.environ.get("TAVILY_API_KEY", "").strip()
    if not value:
        raise RuntimeError("TAVILY_API_KEY is not configured")
    return value


def _search_depth() -> str:
    value = os.environ.get("TAVILY_SEARCH_DEPTH", DEFAULT_SEARCH_DEPTH).strip().lower()
    return value if value in _VALID_SEARCH_DEPTHS else DEFAULT_SEARCH_DEPTH


def _max_results() -> int:
    try:
        value = int(os.environ.get("TAVILY_MAX_RESULTS", DEFAULT_MAX_RESULTS))
    except (TypeError, ValueError):
        return DEFAULT_MAX_RESULTS
    return max(1, min(value, 10))


def _build_query(
    question: str,
    region: str,
    crop: str | None,
    pest: str | None,
    fallback_reason: str,
    on_date: str | None,
) -> str:
    """Tạo search query ngắn; Tavily cho kết quả kém nếu nhồi system prompt vào query."""
    clean_question = " ".join(str(question).split())[:220]
    product_match = _PRODUCT_ORIGINAL_RE.search(clean_question)
    if product_match and _product_anchor(clean_question):
        product_name = _canonical_product_search_name(product_match.group(1).strip())[:120]
        return f"{product_name} công dụng thuốc bảo vệ thực vật"[:390]

    context = [clean_question]
    if crop:
        context.append(f"cây {crop}")
    if pest:
        context.append(f"đối tượng {pest}")
    # Khu vực hữu ích cho tư vấn cây/sâu bệnh, nhưng làm lệch kết quả khi tra tên sản phẩm.
    if crop or pest:
        context.append(_REGION_NAMES.get(region, region))
    context.extend(["Việt Nam", "ưu tiên nguồn chính thức mới nhất"])
    # Đây là metadata điều phối, không đưa vào query vì làm giảm relevance.
    _ = (fallback_reason, on_date)
    return ". ".join(item for item in context if item)[:390]


def _fold(value: Any) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or "")).casefold()
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    normalized = normalized.replace("đ", "d")
    return " ".join(re.findall(r"[a-z0-9]+", normalized))


def _canonical_product_search_name(value: str) -> str:
    """Bổ sung formulation từ registry khi trade name chỉ có đúng một quy cách."""
    try:
        from app.backend import input_resolver

        match = input_resolver._catalogs()["product_by_key"].get(
            input_resolver.fold_text(value)
        )
    except Exception:
        match = None
    if not match:
        return value
    trade_name, formulation = match
    return f"{trade_name} {formulation or ''}".strip()


def _product_anchor(question: str) -> str | None:
    """Lấy tên sản phẩm để chặn câu trả lời Tavily lệch sang thuốc/y tế khác."""
    match = _PRODUCT_INTENT_RE.search(_fold(question))
    if not match:
        return None
    value = match.group(1).strip()
    # Formulation có thể không xuất hiện nguyên văn trong snippet, nên anchor theo trade name.
    value = re.sub(r"\s+\d+(?:\s+\d+)?(?:ec|sc|wp|wg|sl|gr|cs|od|ew)$", "", value)
    if value in {"nao", "gi", "de", "cho"} or len(value) < 4:
        return None
    return value


def _results_support_product(payload: dict[str, Any], anchor: str | None) -> bool:
    if not anchor:
        return True
    anchor_terms = anchor.split()
    for item in payload.get("results") or []:
        if not isinstance(item, dict):
            continue
        haystack = _fold(
            " ".join(
                str(item.get(field) or "")
                for field in ("title", "url", "content", "raw_content")
            )
        )
        if all(term in haystack.split() for term in anchor_terms):
            return True
    return False


def _valid_web_url(value: Any) -> str | None:
    url = str(value or "").strip()
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return url


def _extract_citations(payload: dict[str, Any]) -> list[dict[str, str]]:
    citations: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    for item in payload.get("results") or []:
        if not isinstance(item, dict):
            continue
        url = _valid_web_url(item.get("url"))
        if not url or url in seen_urls:
            continue
        title = str(item.get("title") or urlparse(url).netloc).strip()
        seen_urls.add(url)
        citations.append({"source": title, "url": url})
    return citations


def _post_search(client: Any, headers: dict[str, str], payload: dict[str, Any]):
    response = client.post(
        TAVILY_SEARCH_URL,
        headers=headers,
        json=payload,
        timeout=DEFAULT_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise RuntimeError("Tavily returned an invalid response")
    return data


def search_and_answer(
    question: str,
    region: str,
    *,
    crop: str | None = None,
    pest: str | None = None,
    fallback_reason: str = "internal_source_has_no_answer",
    on_date: str | None = None,
    client=None,
) -> dict[str, Any]:
    """Gọi Tavily Search và trả payload fail-closed có citation."""
    if not enabled() and client is None:
        return {"text": "", "citations": [], "grounded": False}

    query = _build_query(question, region, crop, pest, fallback_reason, on_date)
    request_payload = {
        "query": query,
        "topic": "general",
        "search_depth": _search_depth(),
        "max_results": _max_results(),
        "include_answer": "advanced",
        "include_raw_content": False,
        "include_images": False,
        "country": "vietnam",
        "include_usage": True,
    }
    headers = {
        "Authorization": f"Bearer {_api_key()}",
        "Content-Type": "application/json",
    }

    if client is not None:
        response_payload = _post_search(client, headers, request_payload)
    else:
        import httpx

        # Không kế thừa HTTP_PROXY/HTTPS_PROXY của tiến trình chạy app. Trong môi
        # trường IDE/sandbox các biến này có thể trỏ tới proxy cục bộ không tồn tại
        # (ví dụ 127.0.0.1:9), làm Tavily lỗi ConnectError dù key/quota vẫn hợp lệ.
        with httpx.Client(trust_env=False) as active_client:
            response_payload = _post_search(active_client, headers, request_payload)

    text = str(response_payload.get("answer") or "").strip()
    citations = _extract_citations(response_payload)
    grounded = bool(
        text
        and citations
        and _results_support_product(response_payload, _product_anchor(question))
    )
    if not grounded:
        text = ""
        citations = []
    return {
        "text": text,
        "citations": citations,
        "grounded": grounded,
        "provider": "tavily",
        "request_id": response_payload.get("request_id"),
        "usage": response_payload.get("usage") or {},
    }


def answer_segments(result: dict[str, Any]) -> list[dict]:
    """Render web answer; cảnh báo nằm cuối nội dung text theo yêu cầu UI."""
    if not result.get("grounded"):
        return []
    content = f"{str(result.get('text') or '').strip()}\n\n{WEB_SEARCH_WARNING}"
    segments: list[dict] = [{"type": "text", "content": content}]
    for citation in result.get("citations") or []:
        segments.append(
            {
                "type": "citation",
                "source": citation.get("source") or "Nguồn web",
                "url": citation.get("url") or "",
            }
        )
    return segments
