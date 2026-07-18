"""Thông báo ticket handoff đã được cán bộ trả lời (email + SMS + Zalo OA).

Nguyên tắc: KHÔNG bao giờ raise ra ngoài endpoint — lỗi chỉ log.
Hàm `notify_ticket_answered` luôn trả về chuỗi notified_via.
"""
from __future__ import annotations

import logging
import os
import smtplib
from email.header import Header
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


def notify_ticket_answered(ticket: dict) -> str:
    """Gửi thông báo khi ticket được cán bộ trả lời.

    Trả về danh sách kênh đã gửi, ví dụ "email,sms", hoặc "none".
    Không bao giờ raise — lỗi chỉ log.
    """
    channels: list[str] = []

    smtp_host = os.getenv("SMTP_HOST", "").strip()
    if smtp_host and ticket.get("contact_email"):
        try:
            _send_email(ticket)
            channels.append("email")
            logger.info("Đã gửi email thông báo ticket %s", ticket.get("id"))
        except Exception:
            logger.exception("Gửi email thất bại cho ticket %s", ticket.get("id"))

    sms_token = os.getenv("SPEEDSMS_ACCESS_TOKEN", "").strip()
    if sms_token and ticket.get("contact_phone"):
        try:
            _send_sms(ticket, sms_token)
            channels.append("sms")
            logger.info("Đã gửi SMS thông báo ticket %s", ticket.get("id"))
        except Exception:
            logger.exception("Gửi SMS thất bại cho ticket %s", ticket.get("id"))
    elif not sms_token:
        logger.debug("sms skipped — SPEEDSMS_ACCESS_TOKEN chưa đặt")

    zalo_token = os.getenv("ZALO_OA_ACCESS_TOKEN", "").strip()
    if zalo_token and ticket.get("contact_phone"):
        try:
            _send_zalo(ticket, zalo_token)
            channels.append("zalo")
            logger.info("Đã gửi Zalo thông báo ticket %s", ticket.get("id"))
        except Exception:
            logger.exception("Gửi Zalo thất bại cho ticket %s", ticket.get("id"))
    else:
        if not zalo_token:
            logger.debug("zalo skipped — ZALO_OA_ACCESS_TOKEN chưa đặt")

    return ",".join(channels) if channels else "none"


# ---------------------------------------------------------------------------
# Helpers nội bộ
# ---------------------------------------------------------------------------

def _body_text(ticket: dict) -> str:
    """Tạo nội dung thông báo tiếng Việt."""
    question = ticket.get("question") or ticket.get("transcript", "")
    answer = ticket.get("answer", "")
    answered_by = ticket.get("answered_by", "Cán bộ khuyến nông")
    contact_name = ticket.get("contact_name", "bác")
    return (
        f"Kính gửi {contact_name},\n\n"
        f"Cán bộ khuyến nông đã trả lời câu hỏi của bác:\n\n"
        f"Câu hỏi: {question}\n\n"
        f"Trả lời: {answer}\n\n"
        f"Cán bộ trả lời: {answered_by}\n\n"
        f"Trân trọng,\nĐội hỗ trợ Bạn Nhà Nông"
    )


def _send_email(ticket: dict) -> None:
    """Gửi email qua SMTP (STARTTLS)."""
    smtp_host = os.getenv("SMTP_HOST", "")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_pass = os.getenv("SMTP_PASS", "")
    smtp_from = os.getenv("SMTP_FROM", smtp_user)

    msg = MIMEText(_body_text(ticket), "plain", "utf-8")
    msg["Subject"] = str(Header("Cán bộ khuyến nông đã trả lời câu hỏi của bác", "utf-8"))
    msg["From"] = smtp_from
    msg["To"] = ticket["contact_email"]

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.ehlo()
        server.starttls()
        if smtp_user and smtp_pass:
            server.login(smtp_user, smtp_pass)
        server.send_message(msg)


def _normalize_sms_phone(value: str) -> str:
    """Normalize a Vietnamese/local phone number for the SpeedSMS API."""
    raw = value.strip()
    if raw.startswith("+"):
        raw = raw[1:]
    digits = "".join(character for character in raw if character.isdigit())
    if digits.startswith("00"):
        digits = digits[2:]
    if digits.startswith("0"):
        digits = "84" + digits[1:]
    if not 9 <= len(digits) <= 15:
        raise ValueError("Số điện thoại nhận SMS không hợp lệ.")
    return digits


def _sms_body_text(ticket: dict) -> str:
    """Keep the notification ASCII-only and short enough for one normal SMS."""
    ticket_id = ticket.get("id", "")
    return (
        f"Ban Nha Nong: Can bo khuyen nong da tra loi cau hoi #{ticket_id}. "
        "Mo ung dung de xem chi tiet."
    )


def _send_sms(ticket: dict, token: str) -> None:
    """Send a notification through SpeedSMS and validate its API response."""
    import httpx

    phone = _normalize_sms_phone(str(ticket.get("contact_phone", "")))
    sms_type = int(os.getenv("SPEEDSMS_SMS_TYPE", "4"))
    sender = os.getenv("SPEEDSMS_SENDER", "Notify").strip() or "Notify"
    response = httpx.post(
        "https://api.speedsms.vn/index.php/sms/send",
        auth=(token, "x"),
        headers={"Content-Type": "application/json"},
        json={
            "to": [phone],
            "content": _sms_body_text(ticket),
            "sms_type": sms_type,
            "sender": sender,
        },
        timeout=10,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("status") != "success" or str(payload.get("code")) != "00":
        raise RuntimeError(
            f"SpeedSMS rejected request: {payload.get('code', 'unknown')}"
        )


def _send_zalo(ticket: dict, token: str) -> None:
    """Gửi tin nhắn Zalo OA CS message (httpx sync, timeout 10s)."""
    import httpx  # import lazily để không block import khi httpx chưa cài

    text = _body_text(ticket)
    httpx.post(
        "https://openapi.zalo.me/v3.0/oa/message/cs",
        headers={"access_token": token},
        json={
            "recipient": {"user_id": ticket.get("contact_phone", "")},
            "message": {"text": text},
        },
        timeout=10,
    )
