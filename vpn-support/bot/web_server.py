"""FastAPI: отдаёт Web App и принимает данные тикета с валидацией initData."""
import hashlib
import hmac
import json
import os
import urllib.parse

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

import db

load_dotenv()

APP_SECRET = os.environ.get("APP_SECRET", "change-me-to-a-long-random-string")
WEB_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "web"))

app = FastAPI(title="VPN Support Mini App")

# Ставится ботом при старте: async def notify_admin(text)
notify_admin_hook = None


def require_token(token: str = Query("")) -> str:
    """Простая защита панели оператора: пароль = ADMIN_PANEL_TOKEN (или APP_SECRET)."""
    expected = os.environ.get("ADMIN_PANEL_TOKEN") or APP_SECRET
    if not hmac.compare_digest(token, expected):
        raise HTTPException(401, "unauthorized")
    return token


def validate_init_data(init_data: str) -> dict:
    """Валидация Telegram WebApp initData по официальной схеме (HMAC-SHA256)."""
    parsed = dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))
    hash_ = parsed.pop("hash", None)
    if not hash_:
        raise HTTPException(400, "no hash in initData")
    data_check = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
    secret_key = hmac.new(b"WebAppData", APP_SECRET.encode(), hashlib.sha256).digest()
    computed = hmac.new(secret_key, data_check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(computed, hash_):
        raise HTTPException(403, "invalid initData hash")
    user = parsed.get("user")
    return json.loads(user) if user else {}


class TicketPayload(BaseModel):
    init_data: str
    topic: str = Field(min_length=1, max_length=100)
    problem: str = Field(min_length=3, max_length=2000)
    device: str = Field(default="", max_length=100)


@app.get("/")
async def index():
    return FileResponse(os.path.join(WEB_DIR, "index.html"))


@app.get("/admin")
async def admin_panel():
    return FileResponse(os.path.join(WEB_DIR, "admin.html"))


@app.post("/api/ticket")
async def create_ticket(p: TicketPayload):
    user = validate_init_data(p.init_data)
    uid = int(user.get("id", 0))
    if not uid:
        raise HTTPException(400, "no user in initData")

    existing = db.find_ticket_by_user(uid)
    if existing:
        return {"ok": True, "ticket_id": existing["id"], "existing": True}

    tid = db.new_ticket_id()
    full_name = user.get("first_name", "") + (" " + user.get("last_name", "") if user.get("last_name") else "")
    ticket = db.Ticket(
        id=tid, user_id=uid, username=user.get("username", ""),
        full_name=full_name.strip() or f"user{uid}",
        topic=p.topic, problem=p.problem,
    )
    first_msg = f"Тема: {p.topic}\nУстройство: {p.device or '—'}\n\n{p.problem}"
    db.create_ticket(ticket, first_msg)

    if notify_admin_hook:
        await notify_admin_hook(
            f"🆕 Новый тикет {tid}\nОт: {ticket.full_name} (@{ticket.username or '—'})\n"
            f"Тема: {p.topic}\n\n{p.problem[:500]}\n\n/open {tid}"
        )
    return {"ok": True, "ticket_id": tid}


@app.get("/api/tickets")
async def api_tickets(status: str | None = None, _: str = Depends(require_token)):
    """Список тикетов для панели админа."""
    return db.list_tickets(status)


@app.get("/api/ticket/{tid}/messages")
async def api_messages(tid: str, after: int = 0, _: str = Depends(require_token)):
    if not db.get_ticket(tid):
        raise HTTPException(404, "not found")
    return db.get_messages(tid, after)


class AdminReply(BaseModel):
    ticket_id: str
    text: str


class AdminStatus(BaseModel):
    ticket_id: str
    status: str


@app.post("/api/admin/reply")
async def api_admin_reply(p: AdminReply, _: str = Depends(require_token)):
    """Ответ из веб-панели → уходит пользователю через бота."""
    t = db.get_ticket(p.ticket_id)
    if not t:
        raise HTTPException(404, "ticket not found")
    db.add_message(p.ticket_id, "admin", "Оператор", p.text)
    db.set_status(p.ticket_id, "answered")
    bot = getattr(notify_admin_hook, "bot", None) if notify_admin_hook else None
    sent = False
    if bot is not None:
        try:
            from main import ticket_kb  # общая клавиатура «проблема решена»
            await bot.send_message(t["user_id"], f"💬 Ответ по тикету {t['id']}:\n\n{p.text}",
                                   reply_markup=ticket_kb(t["id"]))
            sent = True
        except Exception as e:
            print("send failed:", e)
    return {"ok": True, "delivered_to_user": sent}


@app.post("/api/admin/status")
async def api_admin_status(p: AdminStatus, _: str = Depends(require_token)):
    t = db.get_ticket(p.ticket_id)
    if not t:
        raise HTTPException(404, "ticket not found")
    if p.status not in {"open", "answered", "in_progress", "closed", "canceled"}:
        raise HTTPException(400, "bad status")
    db.set_status(p.ticket_id, p.status)
    db.add_message(p.ticket_id, "system", "system", f"Статус изменён на: {p.status}")
    bot = getattr(notify_admin_hook, "bot", None) if notify_admin_hook else None
    if bot is not None and p.status in ("closed", "in_progress"):
        labels = {"closed": "✅ Тикет закрыт (проблема решена)", "in_progress": "🔵 Взято в работу"}
        try:
            await bot.send_message(t["user_id"], f"🎫 Статус тикета {t['id']}: {labels[p.status]}")
        except Exception:
            pass
    return {"ok": True}
