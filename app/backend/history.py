"""Lưu lịch sử hội thoại vào SQLite (data/history.db) — thay cho localStorage phía trình duyệt.

Thiết kế doc-store: mỗi hội thoại là 1 JSON payload nguyên trạng đúng shape mà
app/web/app.js đang dùng (id, sessionId, title, region, createdAt, updatedAt,
messages[]...) — server không diễn giải nội dung messages (kể cả các field UI như
status/revisions), chỉ đảm bảo bền vững + thứ tự. Nhờ vậy frontend đổi shape không
cần migration phía server, và swap từ localStorage sang API là 1-1.
"""

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent.parent.parent
HISTORY_DB = BASE_DIR / "data" / "history.db"
MAX_CONVERSATIONS = 200
DEFAULT_SESSION_MAX_TURNS = 30
ABSOLUTE_SESSION_MAX_TURNS = 100

router = APIRouter()

_DDL = """
CREATE TABLE IF NOT EXISTS conversations(
  id TEXT PRIMARY KEY,
  payload TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
"""

_SESSION_DDL = """
CREATE TABLE IF NOT EXISTS conversation_sessions(
  session_id TEXT PRIMARY KEY,
  region TEXT NOT NULL,
  crop TEXT,
  pest TEXT,
  product TEXT,
  formulation TEXT,
  products_json TEXT NOT NULL DEFAULT '[]',
  last_user_text TEXT NOT NULL,
  turn_count INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
"""

_SESSION_TURNS_DDL = """
CREATE TABLE IF NOT EXISTS conversation_turns(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL,
  user_text TEXT NOT NULL,
  attachments_json TEXT NOT NULL DEFAULT '[]',
  assistant_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);
"""


def session_turn_limit() -> int:
    try:
        value = int(os.environ.get("SESSION_MAX_TURNS", DEFAULT_SESSION_MAX_TURNS))
    except (TypeError, ValueError):
        value = DEFAULT_SESSION_MAX_TURNS
    return max(1, min(value, ABSOLUTE_SESSION_MAX_TURNS))


def _conn() -> sqlite3.Connection:
    HISTORY_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(HISTORY_DB)
    conn.row_factory = sqlite3.Row
    conn.execute(_DDL)
    conn.execute(_SESSION_DDL)
    conn.execute(_SESSION_TURNS_DDL)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_conversation_turns_session "
        "ON conversation_turns(session_id, id)"
    )
    columns = {row[1] for row in conn.execute("PRAGMA table_info(conversation_sessions)")}
    if "products_json" not in columns:
        conn.execute(
            "ALTER TABLE conversation_sessions "
            "ADD COLUMN products_json TEXT NOT NULL DEFAULT '[]'"
        )
    conn.commit()
    return conn


class ConversationPayload(BaseModel):
    # Chỉ ràng buộc tối thiểu để bắt lỗi client rõ ràng; phần còn lại giữ nguyên trạng.
    model_config = {"extra": "allow"}
    id: str
    sessionId: str | None = None
    messages: list


def _safe_product_list(items: list) -> list[dict]:
    products: list[dict] = []
    for item in items[:20]:
        if not isinstance(item, dict):
            continue
        trade_name = str(item.get("trade_name") or "").strip()
        if not trade_name:
            continue
        formulation = str(item.get("formulation") or "").strip() or None
        products.append({"trade_name": trade_name, "formulation": formulation})
    return products


def get_session_context(session_id: str | None) -> dict | None:
    """Return the latest structured context for one conversation."""
    if not session_id:
        return None
    conn = _conn()
    try:
        row = conn.execute(
            """SELECT session_id, region, crop, pest, product, formulation, products_json,
                      last_user_text, turn_count, updated_at
               FROM conversation_sessions WHERE session_id=?""",
            (session_id,),
        ).fetchone()
        turn_rows = conn.execute(
            """SELECT user_text, attachments_json, assistant_json, created_at
               FROM conversation_turns WHERE session_id=?
               ORDER BY id DESC LIMIT ?""",
            (session_id, session_turn_limit()),
        ).fetchall()
        turns = []
        for turn_row in reversed(turn_rows):
            try:
                attachments = json.loads(turn_row["attachments_json"] or "[]")
                assistant = json.loads(turn_row["assistant_json"] or "{}")
            except (json.JSONDecodeError, TypeError):
                continue
            turns.append({
                "user_text": turn_row["user_text"],
                "attachment_ids": attachments,
                "assistant": assistant,
                "created_at": turn_row["created_at"],
            })
        if row is not None:
            context = dict(row)
            try:
                context["products"] = json.loads(context.pop("products_json") or "[]")
            except (json.JSONDecodeError, TypeError):
                context["products"] = []
            context["turns"] = turns
            context["stored_turn_count"] = len(turns)
            return context
        payload_rows = conn.execute(
            "SELECT payload FROM conversations ORDER BY updated_at DESC LIMIT ?",
            (MAX_CONVERSATIONS,),
        ).fetchall()
    finally:
        conn.close()

    for payload_row in payload_rows:
        try:
            conversation = json.loads(payload_row["payload"])
        except (json.JSONDecodeError, TypeError):
            continue
        if conversation.get("sessionId") == session_id:
            return _context_from_saved_conversation(conversation)
    return None


def _context_from_saved_conversation(conversation: dict) -> dict | None:
    """Rebuild context lazily for conversations created before session memory existed."""
    from app.backend import product_guard

    crop = pest = product = formulation = None
    products: list[dict] = []
    last_user_text = ""
    turn_count = 0
    saved_messages = (conversation.get("messages") or [])[-session_turn_limit():]
    turns: list[dict] = []
    for message in saved_messages:
        if not isinstance(message, dict) or not message.get("answer"):
            continue
        user_text = str(message.get("text") or "").strip()
        answer = message.get("answer") or {}
        turns.append({
            "user_text": user_text,
            "attachment_ids": [
                item.get("attachment_id")
                for item in (message.get("attachments") or [])
                if isinstance(item, dict) and item.get("attachment_id")
            ],
            "assistant": answer,
            "created_at": message.get("createdAt"),
        })
        slots = answer.get("slots") or {}
        slot_crop = slots.get("crop")
        slot_pest = slots.get("pest")
        if slot_crop and crop and slot_crop != crop:
            pest = slot_pest
            product = formulation = None
            products = []
        else:
            pest = slot_pest or pest
        crop = slot_crop or crop
        mention = product_guard.find_product_or_ai_mention(user_text)
        if mention is not None and mention[0] == "product":
            product, formulation = mention[1]
        answer_products = answer.get("products") or []
        if answer_products:
            products = _safe_product_list(answer_products)
        last_user_text = user_text
        turn_count += 1

    if not any((crop, pest, product, products)):
        return None
    return {
        "session_id": conversation.get("sessionId"),
        "region": conversation.get("region") or "an_giang",
        "crop": crop,
        "pest": pest,
        "product": product,
        "formulation": formulation,
        "products": products,
        "last_user_text": last_user_text,
        "turn_count": turn_count,
        "stored_turn_count": len(turns),
        "turns": turns,
        "updated_at": conversation.get("updatedAt"),
    }


def record_session_turn(
    session_id: str,
    region: str,
    user_text: str,
    response: dict,
    *,
    explicit_product: tuple[str, str | None] | None = None,
    attachment_ids: list[str] | None = None,
) -> None:
    """Persist the complete turn plus trusted entities in a bounded session."""
    now = datetime.now(timezone.utc).isoformat()
    slots = response.get("slots") or {}
    slot_crop = slots.get("crop")
    slot_pest = slots.get("pest")
    conn = _conn()
    try:
        current = conn.execute(
            "SELECT crop, pest, product, formulation, products_json, turn_count, created_at "
            "FROM conversation_sessions WHERE session_id=?",
            (session_id,),
        ).fetchone()
        old_crop = current["crop"] if current else None
        old_pest = current["pest"] if current else None
        old_product = current["product"] if current else None
        old_formulation = current["formulation"] if current else None
        try:
            old_products = json.loads(current["products_json"] or "[]") if current else []
        except (json.JSONDecodeError, TypeError):
            old_products = []
        response_products = _safe_product_list(response.get("products") or [])

        crop = slot_crop or old_crop
        if slot_crop and old_crop and slot_crop != old_crop:
            pest = slot_pest
            if explicit_product is None:
                old_product = None
                old_formulation = None
            if not response_products:
                old_products = []
        else:
            pest = slot_pest or old_pest

        product, formulation = explicit_product or (old_product, old_formulation)
        products = response_products or old_products
        created_at = current["created_at"] if current else now
        turn_count = (int(current["turn_count"]) if current else 0) + 1
        conn.execute(
            """INSERT INTO conversation_sessions(
                   session_id, region, crop, pest, product, formulation, products_json,
                   last_user_text, turn_count, created_at, updated_at
               ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(session_id) DO UPDATE SET
                   region=excluded.region, crop=excluded.crop, pest=excluded.pest,
                   product=excluded.product, formulation=excluded.formulation,
                   products_json=excluded.products_json,
                   last_user_text=excluded.last_user_text,
                   turn_count=excluded.turn_count, updated_at=excluded.updated_at""",
            (
                session_id, region, crop, pest, product, formulation,
                json.dumps(products, ensure_ascii=False), user_text[:2000],
                turn_count, created_at, now,
            ),
        )
        stored_response = dict(response)
        stored_response["session_id"] = session_id
        conn.execute(
            """INSERT INTO conversation_turns(
                   session_id, user_text, attachments_json, assistant_json, created_at
               ) VALUES(?,?,?,?,?)""",
            (
                session_id,
                user_text[:2000],
                json.dumps((attachment_ids or [])[:3], ensure_ascii=False),
                json.dumps(stored_response, ensure_ascii=False),
                now,
            ),
        )
        conn.execute(
            """DELETE FROM conversation_turns
               WHERE session_id=? AND id NOT IN (
                   SELECT id FROM conversation_turns WHERE session_id=?
                   ORDER BY id DESC LIMIT ?
               )""",
            (session_id, session_id, session_turn_limit()),
        )
        conn.commit()
    finally:
        conn.close()


@router.get("/api/conversations")
def list_conversations() -> list[dict]:
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT payload FROM conversations ORDER BY updated_at DESC LIMIT ?",
            (MAX_CONVERSATIONS,),
        ).fetchall()
        return [json.loads(r[0]) for r in rows]
    finally:
        conn.close()


@router.put("/api/conversations/{conversation_id}")
def upsert_conversation(conversation_id: str, payload: ConversationPayload) -> dict:
    if payload.id != conversation_id:
        raise HTTPException(status_code=400, detail="id trong body không khớp với id trên URL.")
    now = datetime.now(timezone.utc).isoformat()
    doc = payload.model_dump()
    doc["messages"] = doc["messages"][-session_turn_limit():]
    conn = _conn()
    try:
        conn.execute(
            "INSERT INTO conversations(id, payload, updated_at) VALUES(?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET payload=excluded.payload, updated_at=excluded.updated_at",
            (conversation_id, json.dumps(doc, ensure_ascii=False), now),
        )
        conn.commit()
    finally:
        conn.close()
    return {"ok": True, "updated_at": now}


@router.delete("/api/conversations/{conversation_id}")
def delete_conversation(conversation_id: str) -> dict:
    conn = _conn()
    try:
        row = conn.execute("SELECT payload FROM conversations WHERE id=?", (conversation_id,)).fetchone()
        session_id = None
        if row is not None:
            try:
                session_id = json.loads(row["payload"]).get("sessionId")
            except (json.JSONDecodeError, AttributeError):
                session_id = None
        cur = conn.execute("DELETE FROM conversations WHERE id=?", (conversation_id,))
        if session_id:
            conn.execute("DELETE FROM conversation_sessions WHERE session_id=?", (session_id,))
            conn.execute("DELETE FROM conversation_turns WHERE session_id=?", (session_id,))
        conn.commit()
        return {"deleted": cur.rowcount > 0}
    finally:
        conn.close()
