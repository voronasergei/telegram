# -*- coding: utf-8 -*-
"""Состояние пользователей в SQLite (aiosqlite)."""
import time
import aiosqlite

import config

DB_PATH = config.DB_PATH

FIELDS = [
    "age", "pain", "plan_efir", "plan_block", "time_opt", "goal_phrase",
    "stage", "converted", "quiz_started_at", "quiz_done", "reached_offer_at",
    "clicked_cta_at", "gift_or_question_at", "last_sent_date",
    "a_idx", "b_idx", "c_idx", "d_idx",
]

async def init():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users(
            user_id INTEGER PRIMARY KEY,
            age TEXT, pain TEXT, plan_efir TEXT, plan_block TEXT,
            time_opt TEXT, goal_phrase TEXT, stage TEXT,
            converted INTEGER DEFAULT 0,
            quiz_started_at REAL, quiz_done INTEGER DEFAULT 0,
            reached_offer_at REAL, clicked_cta_at REAL, gift_or_question_at REAL,
            last_sent_date TEXT,
            a_idx INTEGER DEFAULT 0, b_idx INTEGER DEFAULT 0,
            c_idx INTEGER DEFAULT 0, d_idx INTEGER DEFAULT 0
        )""")
        await db.commit()

async def ensure(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users(user_id, quiz_started_at) VALUES(?, ?)",
            (user_id, time.time()),
        )
        await db.commit()

async def get(user_id: int) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
        row = await cur.fetchone()
        return dict(row) if row else {}

async def set_fields(user_id: int, **kw):
    if not kw:
        return
    keys = ", ".join(f"{k}=?" for k in kw)
    vals = list(kw.values()) + [user_id]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE users SET {keys} WHERE user_id=?", vals)
        await db.commit()

async def all_active() -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM users WHERE converted=0")
        rows = await cur.fetchall()
        return [dict(r) for r in rows]

async def stats() -> dict:
    """Сводка по воронке: счётчики этапов + разбивка по возрасту."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("""
            SELECT
              COUNT(*) AS total,
              COALESCE(SUM(quiz_done), 0) AS completed,
              COALESCE(SUM(reached_offer_at IS NOT NULL), 0) AS reached_offer,
              COALESCE(SUM(clicked_cta_at IS NOT NULL), 0) AS clicked_cta,
              COALESCE(SUM(gift_or_question_at IS NOT NULL), 0) AS gift_or_question,
              COALESCE(SUM(converted), 0) AS converted
            FROM users
        """)
        overall = dict(await cur.fetchone())
        cur2 = await db.execute(
            "SELECT age, COUNT(*) AS n FROM users WHERE age IS NOT NULL "
            "GROUP BY age ORDER BY age"
        )
        by_age = {r["age"]: r["n"] for r in await cur2.fetchall()}
        return {"overall": overall, "by_age": by_age}
