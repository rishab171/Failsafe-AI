"""SQLite session storage (stdlib sqlite3, schema created on startup)."""
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL,
  role TEXT NOT NULL,
  content TEXT NOT NULL,
  metadata TEXT,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, id);
CREATE TABLE IF NOT EXISTS sessions (
  session_id TEXT PRIMARY KEY,
  system_prompt TEXT,
  created_at TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Database:
    def __init__(self, path: str) -> None:
        self.path = path
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with self.conn() as c:
            c.executescript(SCHEMA)

    @contextmanager
    def conn(self):
        c = sqlite3.connect(self.path, timeout=15)
        c.row_factory = sqlite3.Row
        try:
            c.execute("PRAGMA journal_mode=WAL")
            yield c
            c.commit()
        except Exception:
            c.rollback()
            raise
        finally:
            c.close()

    def ping(self) -> bool:
        with self.conn() as c:
            c.execute("SELECT 1")
        return True

    def get_system_prompt(self, session_id: str) -> str | None:
        with self.conn() as c:
            row = c.execute("SELECT system_prompt FROM sessions WHERE session_id=?", (session_id,)).fetchone()
        return row["system_prompt"] if row else None

    def get_history(self, session_id: str) -> list[dict]:
        """Oldest first, role/content only (what is sent to the LLM)."""
        with self.conn() as c:
            rows = c.execute(
                "SELECT role, content FROM messages WHERE session_id=? ORDER BY id", (session_id,)
            ).fetchall()
        return [{"role": r["role"], "content": r["content"]} for r in rows]

    def get_messages(self, session_id: str) -> list[dict] | None:
        with self.conn() as c:
            rows = c.execute(
                "SELECT role, content, metadata FROM messages WHERE session_id=? ORDER BY id", (session_id,)
            ).fetchall()
        if not rows:
            return None
        out = []
        for r in rows:
            m = {"role": r["role"], "content": r["content"]}
            if r["role"] == "assistant" and r["metadata"]:
                m["metadata"] = json.loads(r["metadata"])
            out.append(m)
        return out

    def save_exchange(self, session_id: str, system_prompt: str | None, user_msg: str,
                      reply: str, metadata: dict) -> None:
        """Atomically store the user message and assistant reply (only called on success)."""
        now = _now()
        with self.conn() as c:
            c.execute(
                "INSERT INTO sessions(session_id, system_prompt, created_at) VALUES (?,?,?) "
                "ON CONFLICT(session_id) DO UPDATE SET system_prompt=COALESCE(excluded.system_prompt, sessions.system_prompt)",
                (session_id, system_prompt, now),
            )
            c.execute(
                "INSERT INTO messages(session_id, role, content, metadata, created_at) VALUES (?,?,?,?,?)",
                (session_id, "user", user_msg, None, now),
            )
            c.execute(
                "INSERT INTO messages(session_id, role, content, metadata, created_at) VALUES (?,?,?,?,?)",
                (session_id, "assistant", reply, json.dumps(metadata), _now()),
            )
