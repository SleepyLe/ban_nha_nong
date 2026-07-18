"""FastAPI app — API contract v0 (xem .superpowers/sdd/app-skeleton-brief.md).

Chạy demo: `uvicorn app.backend.api:app --reload` rồi mở http://localhost:8000
"""
from __future__ import annotations

import logging
import os
import sqlite3
import uuid
from datetime import date

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.backend import (
    asr,
    clarifications,
    conversation_resolver,
    handoff,
    history,
    image_resolver,
    image_uploads,
    pipeline,
    product_guard,
    registry_api,
    tts,
)
from app.backend.handoff import HANDOFF_DB  # re-export for backward-compatible tests
from app.backend.schemas import (
    AskRequest,
    AskResponse,
    ImageUploadResponse,
    TranscribeResponse,
    TtsRequest,
)

load_dotenv()

BASE_DIR = __import__("pathlib").Path(__file__).resolve().parent.parent.parent
WEB_DIR = BASE_DIR / "app" / "web"

TRANSCRIBE_UNAVAILABLE_MSG = "Dạ hiện em chưa nhận diện được giọng nói, bác gõ chữ giúp em nhé."
TRANSCRIBE_FAILED_MSG = "Dạ em nhận diện giọng nói bị lỗi, bác thử lại hoặc gõ chữ giúp em nhé."
TTS_UNAVAILABLE_MSG = "Dạ thiết bị chưa có giọng Việt và máy chủ chưa cấu hình Google Text-to-Speech."
TTS_FAILED_MSG = "Dạ em chưa tạo được giọng đọc tiếng Việt, bác thử lại sau nhé."

logger = logging.getLogger(__name__)

app = FastAPI(title="Trợ lý nông nghiệp — API v0")
app.include_router(history.router)
app.include_router(registry_api.router)
app.include_router(handoff.router)


@app.post("/api/ask", response_model=AskResponse)
def ask(req: AskRequest) -> AskResponse:
    text = req.text.strip()
    original_text = text
    session_id = req.session_id or f"session-{uuid.uuid4()}"
    conversation_context = history.get_session_context(session_id)
    pending_confirmation = clarifications.get(session_id)

    def finish(result: dict) -> AskResponse:
        explicit_product = None
        mention = product_guard.find_product_or_ai_mention(text)
        if mention is not None and mention[0] == "product":
            explicit_product = mention[1]
        elif conversation_context:
            explicit_product = pipeline.resolve_product_reference(text, conversation_context)
        if explicit_product is None and (
            pending_confirmation
            and clarifications.confirmation_intent(original_text) == "yes"
            and pending_confirmation.get("product")
        ):
            pending_product = pending_confirmation["product"]
            explicit_product = (
                pending_product.get("canonical"),
                pending_product.get("formulation"),
            )
        try:
            history.record_session_turn(
                session_id,
                req.region,
                original_text,
                result,
                explicit_product=explicit_product,
                attachment_ids=req.attachment_ids,
            )
        except sqlite3.Error:
            logger.exception("Could not persist conversation session context")
        response = AskResponse(
            session_id=session_id,
            session_turn_limit=history.session_turn_limit(),
            **result,
        )
        # Dashboard analytics are best-effort and must never block the answer.
        handoff.log_question(
            region=response.slots.region,
            crop=response.slots.crop,
            pest=response.slots.pest,
            text=original_text,
        )
        return response

    if not text and not req.attachment_ids:
        raise HTTPException(status_code=422, detail="Bác nhập câu hỏi hoặc chọn ít nhất một ảnh nhé.")
    if req.attachment_ids:
        try:
            images = image_uploads.load_images(req.attachment_ids)
        except image_uploads.ImageUploadError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except image_uploads.AttachmentNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        try:
            resolution = image_resolver.resolve_images(text, images)
        except Exception:
            logger.exception("Gemini multimodal input review failed")
            return finish({
                "risk_class": "B",
                "answer_segments": [{
                    "type": "text",
                    "content": (
                        "Dạ, em chưa phân tích được ảnh lúc này. Bác thử gửi lại ảnh hoặc "
                        "gõ tên cây, dấu hiệu hay tên thuốc trên nhãn giúp em nhé."
                    ),
                }],
                "slots": {"crop": None, "pest": None, "region": req.region},
                "products": [],
            })
        if resolution.review is not None:
            review = resolution.review
            if review.action == "confirm":
                clarifications.save(session_id, review.pending_payload())
            return finish({
                "risk_class": "B",
                "answer_segments": [{"type": "text", "content": review.message}],
                "slots": {
                    "crop": review.slots["crop"],
                    "pest": review.slots["pest"],
                    "region": req.region,
                },
                "products": [],
            })
        if resolution.message is not None:
            return finish({
                "risk_class": "B",
                "answer_segments": [{"type": "text", "content": resolution.message}],
                "slots": {"crop": None, "pest": None, "region": req.region},
                "products": [],
            })
        text = resolution.augmented_text or text
    text = conversation_resolver.contextualize(text, conversation_context)
    result = pipeline.answer(
        text,
        req.region,
        date.today().isoformat(),
        session_id=session_id,
        _conversation_context=conversation_context,
    )
    return finish(result)


@app.post("/api/attachments/images", response_model=ImageUploadResponse)
async def upload_images(images: list[UploadFile] = File(...)) -> ImageUploadResponse:
    if not images or len(images) > image_uploads.MAX_IMAGES_PER_QUESTION:
        raise HTTPException(status_code=422, detail="Mỗi câu hỏi được gửi từ 1 đến 3 ảnh.")
    attachments = []
    for image in images:
        data = await image.read(image_uploads.MAX_IMAGE_BYTES + 1)
        try:
            record = image_uploads.store_image(image.filename or "image", data)
        except image_uploads.ImageUploadError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        attachments.append(record.public_dict())
    return ImageUploadResponse(attachments=attachments)


@app.get("/api/attachments/images/{attachment_id}")
def get_uploaded_image(attachment_id: str) -> FileResponse:
    try:
        record = image_uploads.get_stored_image(attachment_id)
    except image_uploads.AttachmentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return FileResponse(
        path=record.path,
        media_type=record.media_type,
        headers={"Cache-Control": "private, max-age=3600"},
    )


@app.post("/api/transcribe", response_model=TranscribeResponse)
async def transcribe(audio: UploadFile = File(...)) -> TranscribeResponse:
    audio_bytes = await audio.read()

    # Ưu tiên (a) Google STT v2 Chirp 3 nếu có creds thật -> (b) whisper-1 stopgap
    # nếu chỉ có OPENAI_API_KEY -> (c) 503 tiếng Việt nếu không có gì.
    if asr.google_credentials_available():
        try:
            text = await asr.transcribe_google(audio_bytes)
        except Exception:
            logger.exception("Google Speech-to-Text transcription failed")
            raise HTTPException(status_code=502, detail=TRANSCRIBE_FAILED_MSG)
        return TranscribeResponse(text=text)

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail=TRANSCRIBE_UNAVAILABLE_MSG)

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://api.openai.com/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {api_key}"},
            data={"model": "whisper-1", "language": "vi"},
            files={"file": (audio.filename or "audio.webm", audio_bytes, audio.content_type or "audio/webm")},
        )
    if resp.status_code >= 400:
        raise HTTPException(status_code=502, detail=TRANSCRIBE_FAILED_MSG)
    data = resp.json()
    return TranscribeResponse(text=data.get("text", ""))


@app.post("/api/tts", response_class=Response)
async def synthesize_speech(req: TtsRequest) -> Response:
    if not asr.google_credentials_available():
        raise HTTPException(status_code=503, detail=TTS_UNAVAILABLE_MSG)
    try:
        audio = await tts.synthesize_google(req.text)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except tts.TtsServiceDisabledError as exc:
        raise HTTPException(
            status_code=503,
            detail="Cloud Text-to-Speech API chưa được bật. Hãy bật API này trong Google Cloud Console rồi thử lại.",
        ) from exc
    except Exception:
        logger.exception("Google Text-to-Speech synthesis failed")
        raise HTTPException(status_code=502, detail=TTS_FAILED_MSG)
    return Response(
        content=audio,
        media_type="audio/mpeg",
        headers={"Cache-Control": "private, max-age=3600"},
    )


# Trang landing ở "/" — app chat chuyển sang "/chat" (endpoint handoff cũ đã
# chuyển vào app/backend/handoff.py router).
@app.get("/")
def landing():
    return FileResponse(WEB_DIR / "landing.html")


@app.get("/chat")
def chat():
    return FileResponse(
        WEB_DIR / "index.html",
        headers={
            "Cache-Control": "no-store, max-age=0",
            "Pragma": "no-cache",
        },
    )


@app.get("/sw.js")
def service_worker():
    return FileResponse(
        WEB_DIR / "sw.js",
        media_type="application/javascript",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
        },
    )



# Đăng ký API routes xong mới mount static — mount "/" chỉ bắt các path không khớp
# route nào ở trên (Starlette thử theo thứ tự đăng ký), đồng thời cho sw.js scope "/".
app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
