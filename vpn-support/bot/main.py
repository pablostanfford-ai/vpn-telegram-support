"""Telegram-бот технической поддержки VPN.

Пользователь: жмёт «🆘 Создать тикет» → открывается Web App с формой →
после отправки с ним можно переписываться прямо в чате бота.
Админ (ADMIN_ID): /tickets, /open <id>, /msg <id> <текст>, /close <id> и т.д.
"""
import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    WebAppInfo,
)
from dotenv import load_dotenv

import db

load_dotenv()

BOT_TOKEN = os.environ["BOT_TOKEN"]
ADMIN_ID = int(os.environ["ADMIN_ID"])
WEB_APP_URL = os.environ.get("WEB_APP_URL", "http://localhost:8000")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("bot")

user_router = Router()
admin_router = Router()

# ---------- Клавиатуры ----------

MAIN_KB = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🆘 Создать тикет", web_app=WebAppInfo(url=WEB_APP_URL))],
        [KeyboardButton(text="🎧 Моя поддержка")],
    ],
    resize_keyboard=True,
)

STATUS_LABELS = {
    "open": "🔴 Открыт",
    "answered": "🟡 Ответили — ждём вас",
    "in_progress": "🔵 В работе",
    "closed": "✅ Решён",
    "canceled": "⚪ Закрыт",
}


def ticket_kb(ticket_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Проблема решена", callback_data=f"resolve|{ticket_id}"),
            InlineKeyboardButton(text="✖️ Отменить тикет", callback_data=f"cancel|{ticket_id}"),
        ]
    ])


# ---------- Пользователь ----------

@user_router.message(CommandStart())
async def cmd_start(m: Message):
    await m.answer(
        "Привет! Я бот технической поддержки VPN. 🛡️\n\n"
        "Если у вас проблемы с подключением, скоростью или подпиской — "
        "нажмите кнопку «🆘 Создать тикет», опишите проблему, и оператор ответит здесь в чате.",
        reply_markup=MAIN_KB,
    )


@user_router.message(F.text == "🎧 Моя поддержка")
async def my_support(m: Message):
    t = db.find_ticket_by_user(m.from_user.id)
    if not t:
        await m.answer("У вас пока нет активных тикетов. Создайте новый кнопкой «🆘 Создать тикет».",
                       reply_markup=MAIN_KB)
        return
    msgs = db.get_messages(t["id"])[-5:]
    history = "\n".join(
        f"• {'Вы' if x['sender_type']=='user' else 'Оператор'}: {x['text'][:120]}" for x in msgs
    )
    await m.answer(
        f"🎫 Тикет {t['id']} — {STATUS_LABELS.get(t['status'], t['status'])}\n"
        f"Тема: {t['topic']}\n\nПоследние сообщения:\n{history}\n\n"
        "Просто напишите сообщение сюда — оно уйдёт оператору.",
        reply_markup=ticket_kb(t["id"]),
    )


NON_TICKET_BUTTONS = ("🆘 Создать тикет", "🎧 Моя поддержка")


@user_router.message(F.text)
async def user_message_to_ticket(m: Message):
    """Любое текстовое сообщение пользователя уходит в его активный тикет."""
    if m.text in NON_TICKET_BUTTONS or m.commands:
        return
    t = db.find_ticket_by_user(m.from_user.id)
    if not t:
        await m.answer("Сначала создайте тикет кнопкой «🆘 Создать тикет» 🙂", reply_markup=MAIN_KB)
        return
    db.add_message(t["id"], "user", m.from_user.full_name, m.text)
    db.set_status(t["id"], "open")  # ждёт ответа оператора
    await notify_admin(
        f"📩 Новое сообщение по тикету {t['id']}\n"
        f"От: {m.from_user.full_name} (@{m.from_user.username or '—'})\n\n{m.text}"
    )
    await m.answer("✅ Сообщение передано оператору. Ответ придёт сюда.")


@user_router.callback_query(F.data.startswith("resolve|"))
async def cb_resolve(cb: CallbackQuery):
    tid = cb.data.split("|")[1]
    t = db.get_ticket(tid)
    if not t or t["user_id"] != cb.from_user.id:
        await cb.answer("Тикет не найден", show_alert=True)
        return
    db.set_status(tid, "closed")
    db.add_message(tid, "system", "system", "Пользователь подтвердил решение. Тикет закрыт.")
    await cb.message.edit_text(f"🎫 Тикет {tid} закрыт. Рады были помочь! Если проблема вернётся — создайте новый тикет.")
    await notify_admin(f"✅ Тикет {tid} закрыт пользователем (проблема решена).")
    await cb.answer()


@user_router.callback_query(F.data.startswith("cancel|"))
async def cb_cancel(cb: CallbackQuery):
    tid = cb.data.split("|")[1]
    t = db.get_ticket(tid)
    if not t or t["user_id"] != cb.from_user.id:
        await cb.answer("Тикет не найден", show_alert=True)
        return
    db.set_status(tid, "canceled")
    db.add_message(tid, "system", "system", "Тикет отменён пользователем.")
    await cb.message.edit_text(f"🎫 Тикет {tid} отменён.")
    await notify_admin(f"✖️ Тикет {tid} отменён пользователем.")
    await cb.answer()


# ---------- Админ ----------

@admin_router.message(Command("tickets"))
async def admin_tickets(m: Message):
    status = None
    if len(m.text.split()) > 1:
        status = m.text.split()[1]
    tickets = db.list_tickets(status)
    if not tickets:
        await m.answer("Тикетов нет 🎉")
        return
    lines = []
    for t in tickets[:30]:
        lines.append(
            f"{t['id']} | {STATUS_LABELS.get(t['status'], t['status'])} | "
            f"{t['topic']} | {t['full_name']}"
        )
    st = db.stats()
    await m.answer(
        f"📊 Всего: {st.get('total', 0)} | 🔴 {st.get('open', 0)} | "
        f"🔵 {st.get('in_progress', 0)} | ✅ {st.get('closed', 0)}\n\n" + "\n".join(lines) +
        "\n\n/open <id> — открыть диалог\n/msg <id> <текст> — ответить\n"
        "/progress <id> — взять в работу\n/close <id> — решить\n/history <id> — вся переписка"
    )


@admin_router.message(Command("open"))
async def admin_open(m: Message):
    tid = _arg(m)
    t = db.get_ticket(tid)
    if not t:
        await m.answer("Тикет не найден")
        return
    msgs = db.get_messages(tid)
    hist = "\n".join(
        f"[{x['sender_type']}] {x['text'][:200]}" for x in msgs[-20:]
    ) or "(пусто)"
    await m.answer(
        f"🎫 {t['id']} — {STATUS_LABELS.get(t['status'])}\n"
        f"User id: <code>{t['user_id']}</code>\n"
        f"Имя: {t['full_name']} (@{t['username'] or '—'})\n"
        f"Тема: {t['topic']}\n"
        f"Описание: {t['problem']}\n\n"
        f"Переписка:\n{hist}\n\n"
        f"Ответ: /msg {t['id']} <текст>",
    )


@admin_router.message(Command("history"))
async def admin_history(m: Message):
    tid = _arg(m)
    if not db.get_ticket(tid):
        await m.answer("Тикет не найден")
        return
    msgs = db.get_messages(tid)
    out = "\n".join(f"[{x['sender_type']}] {x['text']}" for x in msgs) or "(пусто)"
    await m.answer(out[:4000] or "(пусто)")


@admin_router.message(Command("msg"))
async def admin_msg(m: Message):
    parts = m.text.split(maxsplit=2)
    if len(parts) < 3:
        await m.answer("Формат: /msg <id> <текст>")
        return
    tid, text = parts[1], parts[2]
    t = db.get_ticket(tid)
    if not t:
        await m.answer("Тикет не найден")
        return
    db.add_message(tid, "admin", m.from_user.full_name, text)
    db.set_status(tid, "answered")
    try:
        await m.bot.send_message(
            t["user_id"],
            f"💬 Ответ по тикету {tid}:\n\n{text}",
            reply_markup=ticket_kb(tid),
        )
        await m.answer(f"✅ Ответ отправлен пользователю по тикету {tid}")
    except Exception as e:
        await m.answer(f"⚠️ Не удалось отправить: {e}. Сообщение сохранено в тикете.")


async def _set_status_cmd(m: Message, status: str, label: str):
    tid = _arg(m)
    t = db.get_ticket(tid)
    if not t:
        await m.answer("Тикет не найден")
        return
    db.set_status(tid, status)
    db.add_message(tid, "system", "admin", label)
    await m.answer(f"{label}: {tid}")
    try:
        await m.bot.send_message(t["user_id"], f"🎫 Статус тикета {tid}: {label}")
    except Exception:
        pass


@admin_router.message(Command("progress"))
async def admin_progress(m: Message):
    await _set_status_cmd(m, "in_progress", "🔵 Взято в работу")


@admin_router.message(Command("close"))
async def admin_close(m: Message):
    await _set_status_cmd(m, "closed", "✅ Тикет закрыт (проблема решена)")


def _arg(m: Message) -> str:
    parts = m.text.split(maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else ""


# ---------- Уведомление админа о новых тикетах (вызывается из FastAPI) ----------

async def notify_admin(text: str):
    bot = getattr(notify_admin, "bot", None)
    if bot is None:
        log.warning("Bot instance not set; admin notification skipped: %s", text)
        return
    try:
        await bot.send_message(ADMIN_ID, text)
    except Exception as e:
        log.error("Failed to notify admin: %s", e)


async def main():
    db.init_db()

    # Сначала поднимаем веб-сервер (панель/mini app доступны даже без Telegram)
    import web_server
    import uvicorn
    cfg = uvicorn.Config(web_server.app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), log_level="info")
    server = uvicorn.Server(cfg)
    web_server.notify_admin_hook = notify_admin
    web_task = asyncio.create_task(server.serve())

    try:
        bot = Bot(token=BOT_TOKEN)
        notify_admin.bot = bot
        dp = Dispatcher()
        dp.include_router(admin_router)
        dp.include_router(user_router)
        await bot.delete_webhook(drop_pending_updates=True)
        await asyncio.gather(web_task, dp.start_polling(bot))
    except Exception as e:
        log.error("Бот не запустился: %s. Веб-сервер продолжает работать.", e)
        await web_task


if __name__ == "__main__":
    asyncio.run(main())
