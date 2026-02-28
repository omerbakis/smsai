"""
storage.py — SQLite ile kalıcı depolama: usage log ve konuşma geçmişi.
"""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any

_DB_PATH = Path(__file__).resolve().parent.parent / "smsai.db"


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Tabloları oluştur (idempotent)."""
    with _get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS usage_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     TEXT    NOT NULL,
                model       TEXT    NOT NULL,
                input_tokens  INTEGER NOT NULL,
                output_tokens INTEGER NOT NULL,
                total_tokens  INTEGER NOT NULL,
                estimated_cost_usd REAL NOT NULL,
                language    TEXT,
                intent      TEXT,
                complexity  TEXT,
                timestamp   REAL    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS conversations (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     TEXT    NOT NULL,
                role        TEXT    NOT NULL,  -- 'user' or 'assistant'
                content     TEXT    NOT NULL,
                timestamp   REAL    NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_usage_user  ON usage_log(user_id);
            CREATE INDEX IF NOT EXISTS idx_conv_user   ON conversations(user_id);
        """)


def log_usage(
    user_id: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    total_tokens: int,
    estimated_cost_usd: float,
    language: str = "",
    intent: str = "",
    complexity: str = "",
) -> None:
    with _get_conn() as conn:
        conn.execute(
            """INSERT INTO usage_log
               (user_id, model, input_tokens, output_tokens, total_tokens,
                estimated_cost_usd, language, intent, complexity, timestamp)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (user_id, model, input_tokens, output_tokens, total_tokens,
             estimated_cost_usd, language, intent, complexity, time.time()),
        )


def get_usage_log(limit: int = 200) -> list[dict]:
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM usage_log ORDER BY timestamp DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_stats() -> dict[str, Any]:
    with _get_conn() as conn:
        row = conn.execute("""
            SELECT
                COUNT(*)              AS total_requests,
                SUM(total_tokens)     AS total_tokens,
                SUM(estimated_cost_usd) AS total_cost_usd,
                COUNT(DISTINCT user_id) AS unique_users
            FROM usage_log
        """).fetchone()

        model_breakdown = conn.execute("""
            SELECT model, COUNT(*) as count, SUM(total_tokens) as tokens
            FROM usage_log GROUP BY model
        """).fetchall()

    return {
        "total_requests": row["total_requests"] or 0,
        "total_tokens": row["total_tokens"] or 0,
        "total_cost_usd": round(row["total_cost_usd"] or 0, 6),
        "unique_users": row["unique_users"] or 0,
        "model_breakdown": [dict(r) for r in model_breakdown],
    }


def save_message(user_id: str, role: str, content: str) -> None:
    with _get_conn() as conn:
        conn.execute(
            "INSERT INTO conversations (user_id, role, content, timestamp) VALUES (?,?,?,?)",
            (user_id, role, content, time.time()),
        )


def get_history(user_id: str, limit: int = 20) -> list[dict]:
    with _get_conn() as conn:
        rows = conn.execute(
            """SELECT role, content, timestamp FROM conversations
               WHERE user_id=? ORDER BY timestamp DESC LIMIT ?""",
            (user_id, limit),
        ).fetchall()
    return list(reversed([dict(r) for r in rows]))


def get_user_token_usage(user_id: str) -> int:
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(total_tokens),0) AS total FROM usage_log WHERE user_id=?",
            (user_id,),
        ).fetchone()
    return int(row["total"])


def get_global_token_usage() -> int:
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(total_tokens),0) AS total FROM usage_log"
        ).fetchone()
    return int(row["total"])
