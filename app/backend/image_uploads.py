"""Temporary, validated image attachment storage for multimodal chat."""
from __future__ import annotations

import io
import json
import os
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageOps, UnidentifiedImageError

BASE_DIR = Path(__file__).resolve().parent.parent.parent
UPLOAD_DIR = BASE_DIR / "data" / "image_uploads"
MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_IMAGE_DIMENSION = 2048
MAX_IMAGE_PIXELS = 25_000_000
MAX_IMAGES_PER_QUESTION = 3
ATTACHMENT_TTL_SECONDS = 24 * 60 * 60

_FORMAT_CONFIG = {
    "JPEG": ("image/jpeg", ".jpg", "JPEG"),
    "PNG": ("image/png", ".png", "PNG"),
    "WEBP": ("image/webp", ".webp", "WEBP"),
}


class ImageUploadError(ValueError):
    pass


class AttachmentNotFoundError(LookupError):
    pass


@dataclass(frozen=True)
class StoredImage:
    attachment_id: str
    original_name: str
    media_type: str
    size: int
    width: int
    height: int
    created_at: float
    expires_at: float
    stored_name: str

    @property
    def path(self) -> Path:
        return UPLOAD_DIR / self.stored_name

    def public_dict(self) -> dict:
        return {
            "attachment_id": self.attachment_id,
            "original_name": self.original_name,
            "media_type": self.media_type,
            "size": self.size,
            "width": self.width,
            "height": self.height,
            "expires_at": datetime.fromtimestamp(
                self.expires_at, tz=timezone.utc
            ).isoformat(),
            "url": f"/api/attachments/images/{self.attachment_id}",
        }


@dataclass(frozen=True)
class LoadedImage:
    attachment_id: str
    media_type: str
    data: bytes


def _ensure_dir() -> None:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _metadata_path(attachment_id: str) -> Path:
    return UPLOAD_DIR / f"{attachment_id}.json"


def _validate_id(attachment_id: str) -> str:
    try:
        return str(uuid.UUID(str(attachment_id)))
    except (ValueError, TypeError, AttributeError) as exc:
        raise AttachmentNotFoundError("Ảnh đính kèm không hợp lệ.") from exc


def cleanup_expired(now: float | None = None) -> None:
    _ensure_dir()
    current = time.time() if now is None else now
    for metadata_path in UPLOAD_DIR.glob("*.json"):
        try:
            payload = json.loads(metadata_path.read_text(encoding="utf-8"))
            if float(payload["expires_at"]) > current:
                continue
            stored_name = str(payload.get("stored_name") or "")
            if stored_name:
                (UPLOAD_DIR / stored_name).unlink(missing_ok=True)
            metadata_path.unlink(missing_ok=True)
        except (OSError, ValueError, KeyError, json.JSONDecodeError):
            continue


def _normalize_image(data: bytes) -> tuple[bytes, str, str, int, int]:
    if not data:
        raise ImageUploadError("Tệp ảnh đang trống.")
    if len(data) > MAX_IMAGE_BYTES:
        raise ImageUploadError("Mỗi ảnh chỉ được tối đa 8 MB.")
    try:
        with Image.open(io.BytesIO(data)) as probe:
            image_format = str(probe.format or "").upper()
            if image_format not in _FORMAT_CONFIG:
                raise ImageUploadError("Chỉ hỗ trợ ảnh JPEG, PNG hoặc WebP.")
            if probe.width * probe.height > MAX_IMAGE_PIXELS:
                raise ImageUploadError("Ảnh có độ phân giải quá lớn; tối đa khoảng 25 megapixel.")
            probe.verify()
        with Image.open(io.BytesIO(data)) as source:
            source.load()
            normalized = ImageOps.exif_transpose(source)
            normalized.thumbnail(
                (MAX_IMAGE_DIMENSION, MAX_IMAGE_DIMENSION), Image.Resampling.LANCZOS
            )
            media_type, extension, save_format = _FORMAT_CONFIG[image_format]
            if save_format == "JPEG":
                if normalized.mode not in {"RGB", "L"}:
                    normalized = normalized.convert("RGB")
            elif normalized.mode not in {"RGB", "RGBA", "L", "LA", "P"}:
                normalized = normalized.convert("RGBA")
            output = io.BytesIO()
            save_options = {"format": save_format, "optimize": True}
            if save_format == "JPEG":
                save_options["quality"] = 88
            normalized.save(output, **save_options)
            width, height = normalized.size
    except ImageUploadError:
        raise
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ImageUploadError("Tệp tải lên không phải ảnh hợp lệ hoặc đã bị hỏng.") from exc
    return output.getvalue(), media_type, extension, width, height


def store_image(original_name: str, data: bytes) -> StoredImage:
    cleanup_expired()
    normalized, media_type, extension, width, height = _normalize_image(data)
    attachment_id = str(uuid.uuid4())
    stored_name = f"{attachment_id}{extension}"
    now = time.time()
    record = StoredImage(
        attachment_id=attachment_id,
        original_name=Path(original_name or "image").name[:160],
        media_type=media_type,
        size=len(normalized),
        width=width,
        height=height,
        created_at=now,
        expires_at=now + ATTACHMENT_TTL_SECONDS,
        stored_name=stored_name,
    )
    _ensure_dir()
    record.path.write_bytes(normalized)
    _metadata_path(attachment_id).write_text(
        json.dumps(asdict(record), ensure_ascii=False), encoding="utf-8"
    )
    return record


def get_stored_image(attachment_id: str) -> StoredImage:
    normalized_id = _validate_id(attachment_id)
    metadata_path = _metadata_path(normalized_id)
    try:
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        record = StoredImage(**payload)
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise AttachmentNotFoundError("Không tìm thấy ảnh đính kèm.") from exc
    if record.expires_at <= time.time() or not record.path.is_file():
        record.path.unlink(missing_ok=True)
        metadata_path.unlink(missing_ok=True)
        raise AttachmentNotFoundError("Ảnh đính kèm đã hết hạn.")
    return record


def load_images(attachment_ids: Iterable[str]) -> list[LoadedImage]:
    ids = list(dict.fromkeys(str(value) for value in attachment_ids))
    if len(ids) > MAX_IMAGES_PER_QUESTION:
        raise ImageUploadError("Mỗi câu hỏi chỉ được đính kèm tối đa 3 ảnh.")
    loaded: list[LoadedImage] = []
    for attachment_id in ids:
        record = get_stored_image(attachment_id)
        loaded.append(
            LoadedImage(
                attachment_id=record.attachment_id,
                media_type=record.media_type,
                data=record.path.read_bytes(),
            )
        )
    return loaded
