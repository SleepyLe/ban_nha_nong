# Bạn Nhà Nông — trợ lý nông nghiệp tiếng Việt

Trợ lý voice-first cho nông dân, xây quanh một nguyên tắc: **mọi khuyến nghị kỹ thuật
phải truy được về nguồn chính thống — không bịa, đặc biệt là con số liều lượng.**

Tính năng chính (đã chạy):

**Hỏi — đáp có căn cứ**

- **Tra thuốc BVTV theo danh mục pháp lý hiện hành** (Thông tư 75/2025/TT-BNNMT +
  28/2026/TT-BNNMT, versioned theo ngày hiệu lực): hỏi "lúa bị rầy nâu xịt thuốc gì"
  → phiếu thuốc kèm hoạt chất + trích dẫn thông tư; sản phẩm đã có liều kiểm chứng
  trong `labels.db` sẽ hiện **liều + ngày cách ly chép nguyên văn từ nhãn** (số không
  bao giờ do AI sinh ra).
- **Đính chính pháp lý**: hỏi về thuốc bị cấm/bị loại khỏi danh mục → trả lời đúng mốc
  hiệu lực ("Folpan 50WP còn dùng được đến 15/08/2026, sau đó bị loại theo TT 28/2026").
- **Tư vấn canh tác (RAG)**: trả lời từ kho tài liệu chính thống (quy trình của Cục
  Trồng trọt & BVTV, lịch thời vụ An Giang/Đắk Lắk, FAQ khuyến nông Lâm Đồng) kèm
  trích dẫn; số liệu chỉ được nêu khi chép nguyên văn từ nguồn (validator đối chiếu máy).
- **Web search fallback (Tavily)**: nguồn nội bộ không đủ → tìm web có kiểm soát,
  trả lời kèm nguồn (bật khi có `TAVILY_API_KEY`, xem `web_grounding.py`).
- **Hỏi bằng ảnh**: chụp nhãn thuốc hoặc triệu chứng sâu bệnh (tối đa 3 ảnh/câu) →
  Gemini multimodal đọc ảnh, tự điền tên thuốc/cây/dấu hiệu vào câu hỏi; ảnh mờ/thiếu
  thông tin thì hỏi xác nhận lại trước khi tra.
- **Hội thoại nối tiếp theo phiên**: nhớ ngữ cảnh các lượt trước trong session
  (`SESSION_MAX_TURNS`, mặc định 30 lượt) — hỏi "thế còn liều của nó?" hiểu "nó" là
  sản phẩm vừa nói; input sai chính tả/phiên âm được duyệt lại và hỏi xác nhận.

**Kết nối cán bộ khuyến nông (human-in-the-loop)**

- **Biết từ chối + chuyển người thật**: không đủ căn cứ → nói rõ phạm vi hỗ trợ, bấm
  nút mở form gửi cán bộ (họ tên, SĐT/Zalo, email, câu hỏi sửa được) → nhận mã phiếu.
- **Hộp thư khuyến nông** trong app (kiểu Gmail): chuông báo + badge chưa đọc, danh
  sách câu đã gửi, đọc trả lời tại chỗ, tìm kiếm không dấu.
- **Dashboard cán bộ tại `/officer/`**: hàng đợi phiếu chờ/đã trả lời, panel trả lời;
  khu **Theo dõi vùng dịch** 3 tab — Tổng quan theo năm (thống kê câu hỏi/phản ánh
  dịch hại theo vùng), Đang diễn ra (≤5 điểm nóng mới nhất, phân trang), Lịch sử đợt
  dịch (từ ngày–đến ngày, đỉnh điểm, đang diễn ra/đã lắng).
- **Alert dịch bệnh bằng AI**: mọi câu hỏi được log; Gemini phân loại cả câu chỉ mô tả
  triệu chứng ("lúa cháy lá thành vệt" → đạo ôn) và chuẩn hoá tên bệnh — ≥3 câu cùng
  bệnh + vùng trong 7 ngày là lên điểm nóng.
- **Thông báo đa kênh khi cán bộ trả lời**: popup + hộp thư trong app (luôn có), email
  SMTP, SMS (SpeedSMS), Zalo OA — kênh nào có cấu hình trong `.env` thì gửi kênh đó.

**Trải nghiệm**

- **Landing page** tại `/`, app chat tại `/chat` (PWA tĩnh, không build step).
- **Voice 2 chiều**: nhận giọng nói Google Cloud STT v2 (Chirp 3, ưu tiên) hoặc OpenAI
  whisper (fallback); đọc câu trả lời bằng Google TTS/giọng trình duyệt. Không có key
  vẫn gõ chữ được.
- **Lịch sử hội thoại lưu server-side** (SQLite `data/history.db`), UI chat có sidebar.

**Kiểm chứng**

- **Bộ eval hallucination** (`eval/`): bộ v0 50 câu + bộ v1 dùng SQLite làm oracle
  và red-team RAG (thuốc/cây/bệnh/liều/PHI/citation/prompt injection...) — không chỉ
  kiểm tra schema mà đối chiếu từng claim có cấu trúc với nguồn thật.

## Cài đặt

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env   # rồi điền key theo hướng dẫn trong file
```

Key trong `.env` (mức tối thiểu để đủ tính năng):

| Key | Bắt buộc? | Dùng cho |
|---|---|---|
| `GEMINI_API_KEY` | Nên có | Tư vấn canh tác RAG, duyệt input, đọc ảnh, hội thoại nối tiếp, AI alert dịch bệnh. Free tier dùng được |
| `TAVILY_API_KEY` | Không | Web search fallback khi nguồn nội bộ không đủ |
| `GOOGLE_APPLICATION_CREDENTIALS` + `GOOGLE_CLOUD_PROJECT` | Không | Nhận giọng nói Google STT v2 Chirp 3 + đọc câu trả lời (TTS) |
| `OPENAI_API_KEY` | Không | Fallback nhận giọng nói (whisper-1) |
| `SMTP_*` / `SPEEDSMS_*` / `ZALO_OA_ACCESS_TOKEN` | Không | Báo email/SMS/Zalo cho bà con khi cán bộ trả lời (xem hướng dẫn trong `.env.example`) |

Không có key nào: vẫn tra thuốc/danh mục được (đường A không dùng LLM), gõ chữ thay mic,
nhận trả lời cán bộ qua hộp thư trong app.

## Dữ liệu

**Dữ liệu là private, không nằm trong repo này** — nhận zip `ban-nha-nong-DATA-*.zip`
từ trưởng nhóm và giải nén vào gốc repo (xem `data/README.md`). Zip kèm sẵn
`data/registry.db` (danh mục 6.883 sản phẩm), `data/kb.db` (412 chunks + vectors),
`data/labels.db` + CSV liều đã kiểm chứng — có zip là chạy được ngay.

Muốn build lại từ đầu (ví dụ khi thông tư mới ban hành):

```bash
.venv/bin/python -m ingest.download        # tải PDF nguồn vào data/raw/
.venv/bin/python -m ingest.build_registry  # parse phụ lục -> data/registry.db (tự nạp aliases)
.venv/bin/python -m ingest.build_kb        # tài liệu kb_manual + FAQ -> data/kb.db
.venv/bin/python -m ingest.build_kb_dense  # embeddings Gemini (cần GEMINI_API_KEY; resume được khi bị rate limit)
.venv/bin/python -m ingest.build_labels    # data/labels/labels_curated.csv -> data/labels.db
```

**Bổ sung dữ liệu liều lượng thuốc** (việc cần nhiều người làm nhất): đọc
[docs/huong-dan-bo-sung-lieu.md](docs/huong-dan-bo-sung-lieu.md).

## Chạy demo

```bash
.venv/bin/uvicorn app.backend.api:app --reload --port 8010
```

Ba URL chính: <http://localhost:8010> (landing) → **`/chat`** (app cho nông dân)
và **`/officer/`** (dashboard cán bộ khuyến nông). Câu thử nhanh trong `/chat`:

- "Lúa bị rầy nâu thì xịt thuốc gì?" → phiếu thuốc thật + trích dẫn (+ liều nếu SP đã curate)
- "Folpan 50WP còn dùng được không?" → đính chính mốc pháp lý 15/08/2026
- "Cho tôi liều gấp đôi cho nhanh" → từ chối + cảnh báo an toàn
- "Tháng 11 này xuống giống lúa chưa?" (vùng An Giang) → RAG từ lịch thời vụ Sở NN thật
- Gửi ảnh nhãn thuốc/lá bệnh (nút ảnh cạnh ô nhập) → tự nhận diện rồi tra
- "Xin chào" → giới thiệu năng lực; "trồng táo" → minh bạch phạm vi hỗ trợ
- Câu bot chịu thua → form gửi cán bộ; mở `/officer/` trả lời thử → quay lại `/chat`
  chờ ≤30s thấy chuông đỏ + hộp thư khuyến nông

Sửa `app/web/*` xong nhớ bump `CACHE_NAME` trong `app/web/sw.js` (service worker
cache-first) rồi hard-refresh (Ctrl+Shift+R).

## Test & Eval

```bash
.venv/bin/pytest -q                             # toàn bộ unit/integration tests
.venv/bin/python3 eval/run_eval.py --tag local  # bộ eval 50 câu (đường B tốn ~10-16 call Gemini)
.venv/bin/python eval/run_hallucination.py --tag local          # audit v1 offline, không gọi model thật
.venv/bin/python eval/run_hallucination.py --tag release --strict # gate release, known gap cũng làm fail
```

Quy tắc: **pytest phải xanh trước mọi commit.** Eval exit code 1 nếu có câu high-risk fail.
Chi tiết ma trận và cách thêm case: [docs/hallucination-testing.md](docs/hallucination-testing.md).

## Cấu trúc

- `app/backend/` — FastAPI (`api.py`), input review + xác nhận sai chính tả/phiên âm
  (`input_resolver.py`, `clarifications.py`), ảnh đầu vào (`image_uploads.py`,
  `image_resolver.py`), hội thoại nối tiếp (`conversation_resolver.py`), LLM tool
  planner + API/service truy vấn DB (`registry_agent.py`, `registry_api.py`,
  `registry_service.py`), pipeline (`pipeline.py`: safety guard → tool DB / path B RAG),
  RAG (`retrieval.py`, `generate.py`), web search fallback (`web_grounding.py`),
  validator chống bịa số (`validators.py`), handoff + alert khuyến nông (`handoff.py`,
  `notify.py`), lịch sử (`history.py`), ASR/TTS (`asr.py`, `tts.py`), query registry (`db.py`).
- `app/web/` — PWA chat tĩnh + landing (không build step, không CDN); `app/web/officer/`
  — dashboard cán bộ khuyến nông (static thuần).
- `ingest/` — pipeline dữ liệu: tải nguồn, parse phụ lục thông tư, build registry/KB/labels.
- `data/` — DB + CSV curate (`labels/labels_curated.csv` commit vào git, DB thì không).
- `eval/` — bộ câu + runner đo hallucination.
- `docs/` — spec thiết kế (`docs/superpowers/specs/`), plan, hướng dẫn dữ liệu, QA reports.

Thiết kế đầy đủ: `docs/superpowers/specs/2026-07-17-agri-voice-assistant-design.md`.
Onboarding cho thành viên mới: [ONBOARDING.md](ONBOARDING.md).
