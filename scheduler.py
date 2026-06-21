# -*- coding: utf-8 -*-
"""Добивочные серии: APScheduler раз в 10 минут шлёт дозревшие касания.
Максимум 1 сообщение в день; стоп при converted=1. Приоритет: C > B > D > A."""
import time
import logging
from datetime import date
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

import config
import db
import texts as t

log = logging.getLogger("scheduler")

# Задержки в минутах от соответствующего таймстемпа
A_OFF = [30, 1440]
B_OFF = [120, 1440, 2880, 4320, 5760, 8640]
C_OFF = [180, 1440]
D_OFF = [1440, 4320, 7200]


def _kb(rows):
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _site():
    return InlineKeyboardButton(text="Открыть сайт →", url=config.site_link())


def _conv():
    return InlineKeyboardButton(text="Я уже вступил 💚", callback_data="conv")


def _question():
    return InlineKeyboardButton(text="Есть вопрос", callback_data="question")


def build(series, idx):
    if series == "A":
        return t.A[idx], _kb([[InlineKeyboardButton(text="Продолжить →", callback_data="resume")]])
    if series == "B":
        rows = [[_site()]]
        if idx >= 2:
            rows.append([_conv()])
        return t.B[idx], _kb(rows)
    if series == "C":
        if idx == 0:
            return t.C[0], _kb([[_conv()], [_question()], [_site()]])
        return t.C[1], _kb([[_site()], [_question()]])
    if series == "D":
        return t.D[idx], _kb([[_site()]])
    return None, None


def _due(ts, offsets, idx, now):
    return bool(ts) and idx < len(offsets) and (now - ts) >= offsets[idx] * 60


async def tick(bot):
    today = date.today().isoformat()
    now = time.time()
    for u in await db.all_active():
        if u.get("last_sent_date") == today:
            continue
        uid = u["user_id"]
        series = idx = field = None
        # Приоритет: C > B > D > A
        if _due(u.get("clicked_cta_at"), C_OFF, u["c_idx"], now):
            series, idx, field = "C", u["c_idx"], "c_idx"
        elif u["quiz_done"] and not u.get("clicked_cta_at") and _due(u.get("reached_offer_at"), B_OFF, u["b_idx"], now):
            series, idx, field = "B", u["b_idx"], "b_idx"
        elif _due(u.get("gift_or_question_at"), D_OFF, u["d_idx"], now):
            series, idx, field = "D", u["d_idx"], "d_idx"
        elif not u["quiz_done"] and _due(u.get("quiz_started_at"), A_OFF, u["a_idx"], now):
            series, idx, field = "A", u["a_idx"], "a_idx"
        if not series:
            continue
        text, markup = build(series, idx)
        try:
            await bot.send_message(uid, text, reply_markup=markup)
            await db.set_fields(uid, last_sent_date=today, **{field: idx + 1})
        except Exception as e:  # пользователь заблокировал бота и т.п.
            log.warning("send to %s failed: %s", uid, e)


def start_scheduler(bot):
    sched = AsyncIOScheduler()
    sched.add_job(tick, "interval", minutes=10, args=[bot])
    sched.start()
    return sched
