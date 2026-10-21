"""Модели и хранилище тикетов поддержки (SQLite)."""
import sqlite3
import threading
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional


class TicketStatus(str, Enum):
    OPEN = "open"            # новый — ждёт ответа оператора
    ANSWERED = "answered"    # оператор ответил, ждём клиента
    IN_PROGRESS = "in_progress"  # в работе
    CLOSED = "closed"        # решён
    CANCELED = "canceled"    # закрыт клиентом


class MessageType(str, Enum):
    USER = "user"
    ADMIN = "admin"
    SYSTEM = "system"


@dataclass
class Message:
    id: int
    ticket_id: str
    sender_type: str   # user / admin / system
    sender_name: str
    text: str
    ts: float

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Ticket:
    id: str
    user_id: int
    username: str
    full_name: str
    topic: str          # категория проблемы (VPN не работает и т.п.)
    problem: str        # описание из формы мини-приложения
    status: str = TicketStatus.OPEN.value
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)


DB_PATH = "tickets.db"
_lock = threading.Lock()


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init_db() -> None:
    with _lock, _conn() as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS tickets (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                username TEXT,
                full_name TEXT,
                topic TEXT,
                problem TEXT,
                status TEXT DEFAULT 'open',
                created_at REAL,
                updated_at REAL
            );
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id TEXT NOT NULL,
                sender_type TEXT,
                sender_name TEXT,
                text TEXT,
                ts REAL,
                FOREIGN KEY (ticket_id) REFERENCES tickets(id)
            );
            """
        )


def new_ticket_id() -> str:
    """Короткий читаемый id вида T-8F3K2."""
    import secrets
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "T-" + "".join(secrets.choice(alphabet) for _ in range(5))


def create_ticket(t: Ticket, first_message_text: str) -> None:
    with _lock, _conn() as c:
        c.execute(
            "INSERT INTO tickets (id,user_id,username,full_name,topic,problem,status,created_at,updated_at)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (t.id, t.user_id, t.username, t.full_name, t.topic, t.problem,
             t.status, t.created_at, t.updated_at),
        )
        add_msg_in(c, t.id, MessageType.USER.value, t.full_name, first_message_text)


def add_msg_in(conn, ticket_id: str, sender_type: str, sender_name: str, text: str) -> int:
    cur = conn.execute(
        "INSERT INTO messages (ticket_id,sender_type,sender_name,text,ts) VALUES (?,?,?,?,?)",
        (ticket_id, sender_type, sender_name, text, time.time()),
    )
    conn.execute("UPDATE tickets SET updated_at=? WHERE id=?", (time.time(), ticket_id))
    return cur.lastrowid


def add_message(ticket_id: str, sender_type: str, sender_name: str, text: str) -> int:
    with _lock, _conn() as c:
        return add_msg_in(c, ticket_id, sender_type, sender_name, text)


def set_status(ticket_id: str, status: str) -> None:
    with _lock, _conn() as c:
        c.execute("UPDATE tickets SET status=?, updated_at=? WHERE id=?",
                  (status, time.time(), ticket_id))


def get_ticket(ticket_id: str) -> Optional[dict]:
    with _conn() as c:
        row = c.execute("SELECT * FROM tickets WHERE id=?", (ticket_id,)).fetchone()
        return dict(row) if row else None


def find_ticket_by_user(user_id: int) -> Optional[dict]:
    """Последний активный тикет пользователя."""
    with _conn() as c:
        row = c.execute(
            "SELECT * FROM tickets WHERE user_id=? AND status != 'closed' AND status != 'canceled'"
            " ORDER BY updated_at DESC LIMIT 1",
            (user_id,),
        ).fetchone()
        return dict(row) if row else None


def list_tickets(status: Optional[str] = None) -> list[dict]:
    q = "SELECT * FROM tickets"
    args: tuple = ()
    if status:
        q += " WHERE status=?"
        args = (status,)
    q += " ORDER BY updated_at DESC"
    with _conn() as c:
        return [dict(r) for r in c.execute(q, args).fetchall()]


def get_messages(ticket_id: str, after_id: int = 0) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM messages WHERE ticket_id=? AND id>? ORDER BY id ASC",
            (ticket_id, after_id),
        ).fetchall()
        return [dict(r) for r in rows]


def stats() -> dict:
    with _conn() as c:
        res = {}
        for r in c.execute("SELECT status, COUNT(*) n FROM tickets GROUP BY status"):
            res[r["status"]] = r["n"]
        res["total"] = sum(res.values())
        return res
