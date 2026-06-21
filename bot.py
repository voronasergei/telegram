# -*- coding: utf-8 -*-
import asyncio
import time
import logging
from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

import config
import db
import texts as t
from scheduler import start_scheduler

logging.basicConfig(level=logging.INFO)
router = Router()


def kb(rows):
    return InlineKeyboardMarkup(inline_keyboard=rows)


def b_cb(text, data):
    return InlineKeyboardButton(text=text, callback_data=data)


def b_url(text, url):
    return InlineKeyboardButton(text=text, url=url)


def age_kb():
    return kb([[b_cb(a, f"age:{i}")] for i, a in enumerate(t.AGES)])


def pain_kb(age):
    return kb([[b_cb(p["label"], f"pain:{i}")] for i, p in enumerate(t.PAINS[age])])


def tried_kb():
    return kb([[b_cb(o, f"tried:{i}")] for i, o in enumerate(t.V4_OPTS)])


def time_kb():
    return kb([[b_cb(o, f"time:{i}")] for i, o in enumerate(t.TIMES)])


def goal_kb():
    return kb([[b_cb(g[0], f"goal:{i}")] for i, g in enumerate(t.GOALS)])


def offer_kb():
    return kb([
        [b_cb("Вступить в Клуб →", "cta")],
        [b_url("Что входит →", config.site_link())],
        [b_cb("🎁 Чек-лист", "gift"), b_cb("Задать вопрос", "question")],
    ])


@router.message(CommandStart())
async def start(m: Message):
    await db.ensure(m.from_user.id)
    await db.set_fields(m.from_user.id, quiz_started_at=time.time(), quiz_done=0,
                        stage="age", a_idx=0, b_idx=0, c_idx=0, d_idx=0,
                        clicked_cta_at=None, gift_or_question_at=None, converted=0)
    for line in t.V1:
        await m.answer(line)
    await m.answer(t.V2, reply_markup=age_kb())


@router.callback_query(F.data.startswith("age:"))
async def on_age(cq: CallbackQuery):
    i = int(cq.data.split(":")[1])
    age = t.AGES[i]
    await db.set_fields(cq.from_user.id, age=age, stage="pain")
    await cq.message.answer(t.V3_ACK.format(age=age))
    await cq.message.answer(t.V3_Q, reply_markup=pain_kb(age))
    await cq.answer()


@router.callback_query(F.data.startswith("pain:"))
async def on_pain(cq: CallbackQuery):
    u = await db.get(cq.from_user.id)
    i = int(cq.data.split(":")[1])
    p = t.PAINS[u["age"]][i]
    await db.set_fields(cq.from_user.id, pain=p["label"], plan_efir=p["efir"],
                        plan_block=p["block"], stage="tried")
    await cq.message.answer(t.V4, reply_markup=tried_kb())
    await cq.answer()


@router.callback_query(F.data.startswith("tried:"))
async def on_tried(cq: CallbackQuery):
    await db.set_fields(cq.from_user.id, stage="time")
    for line in t.V5:
        await cq.message.answer(line)
    await cq.message.answer(t.V6, reply_markup=time_kb())
    await cq.answer()


@router.callback_query(F.data.startswith("time:"))
async def on_time(cq: CallbackQuery):
    i = int(cq.data.split(":")[1])
    await db.set_fields(cq.from_user.id, time_opt=t.TIMES[i], stage="goal")
    await cq.message.answer(t.V7, reply_markup=goal_kb())
    await cq.answer()


@router.callback_query(F.data.startswith("goal:"))
async def on_goal(cq: CallbackQuery):
    i = int(cq.data.split(":")[1])
    await db.set_fields(cq.from_user.id, goal_phrase=t.GOALS[i][1], stage="card")
    await cq.answer()
    await cq.message.answer(t.V8)
    await asyncio.sleep(1.5)
    u = await db.get(cq.from_user.id)
    card = t.V9.format(age=u["age"], pain=u["pain"], efir=u["plan_efir"],
                       block=u["plan_block"], time=u["time_opt"], goal=u["goal_phrase"])
    await cq.message.answer(card)
    await cq.message.answer(t.V10)
    await db.set_fields(cq.from_user.id, quiz_done=1, reached_offer_at=time.time(), stage="offer")
    for line in t.V11:
        await cq.message.answer(line)
    await cq.message.answer("👇", reply_markup=offer_kb())


@router.callback_query(F.data == "cta")
async def on_cta(cq: CallbackQuery):
    await db.set_fields(cq.from_user.id, clicked_cta_at=time.time())
    await cq.message.answer(t.CTA_LINK_MSG,
                            reply_markup=kb([[b_url("Открыть сайт →", config.site_link())]]))
    await cq.answer()


@router.callback_query(F.data == "gift")
async def on_gift(cq: CallbackQuery):
    await db.set_fields(cq.from_user.id, gift_or_question_at=time.time())
    msg = t.GIFT_MSG
    rows = [[b_url("Скачать чек-лист →", config.GIFT_URL)]] if config.GIFT_URL else None
    await cq.message.answer(msg, reply_markup=kb(rows) if rows else None)
    await cq.answer()


@router.callback_query(F.data == "question")
async def on_question(cq: CallbackQuery):
    await db.set_fields(cq.from_user.id, gift_or_question_at=time.time())
    await cq.message.answer(t.V13)
    await cq.answer()


@router.callback_query(F.data == "conv")
async def on_conv(cq: CallbackQuery):
    await db.set_fields(cq.from_user.id, converted=1)
    await cq.message.answer(t.OPTOUT_REPLY)
    await cq.answer()


async def send_stage(message: Message, u: dict):
    """Показать вопрос текущего шага квиза по сохранённому stage."""
    stage = (u or {}).get("stage") or "age"
    age = (u or {}).get("age")
    if stage == "pain" and age:
        await message.answer(t.V3_Q, reply_markup=pain_kb(age))
    elif stage == "tried":
        await message.answer(t.V4, reply_markup=tried_kb())
    elif stage == "time":
        await message.answer(t.V6, reply_markup=time_kb())
    elif stage == "goal":
        await message.answer(t.V7, reply_markup=goal_kb())
    else:
        # stage == "age" или возраст ещё не выбран — начинаем с вопроса о возрасте
        await db.set_fields(message.chat.id, stage="age")
        await message.answer(t.V2, reply_markup=age_kb())


@router.callback_query(F.data == "resume")
async def on_resume(cq: CallbackQuery):
    # Возобновляем квиз с того шага, на котором пользователь остановился.
    u = await db.get(cq.from_user.id)
    await cq.answer()
    await send_stage(cq.message, u)


@router.message(Command("myid"))
async def cmd_myid(m: Message):
    await m.answer(f"Ваш Telegram ID: {m.from_user.id}")


@router.message(Command("stats"))
async def cmd_stats(m: Message):
    if m.from_user.id not in config.ADMIN_IDS:
        return  # не админ — молча игнорируем
    s = await db.stats()
    o = s["overall"]
    total = o["total"] or 0

    def pct(x):
        return f" ({round(100 * x / total)}%)" if total else ""

    by_age = s["by_age"]
    age_lines = "\n".join(f"• {a}: {by_age.get(a, 0)}" for a in t.AGES)
    text = (
        "📊 Статистика воронки\n\n"
        f"👥 Всего пользователей: {total}\n"
        f"🧩 Прошли квиз: {o['completed']}{pct(o['completed'])}\n"
        f"🎯 Дошли до оффера: {o['reached_offer']}{pct(o['reached_offer'])}\n"
        f"🔗 Нажали «Вступить»: {o['clicked_cta']}{pct(o['clicked_cta'])}\n"
        f"🎁 Чек-лист / вопрос: {o['gift_or_question']}{pct(o['gift_or_question'])}\n"
        f"💚 Отметили «Я уже вступил»: {o['converted']}{pct(o['converted'])}\n\n"
        "По возрасту:\n"
        f"{age_lines}"
    )
    await m.answer(text)


@router.message(F.text)
async def on_text(m: Message):
    await m.answer("Спасибо, передаю куратору 💚 А пока можете заглянуть на сайт.",
                   reply_markup=kb([[b_url("Открыть сайт →", config.site_link())]]))


async def main():
    if not config.BOT_TOKEN:
        raise SystemExit("Укажите BOT_TOKEN в .env")
    await db.init()
    bot = Bot(token=config.BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)
    start_scheduler(bot)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
