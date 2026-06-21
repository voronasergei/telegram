# -*- coding: utf-8 -*-
import os
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
SITE_URL = os.getenv("SITE_URL", "https://edpower.ru/club")
UTM = os.getenv("UTM", "utm_source=tgbot&utm_medium=funnel")
GIFT_URL = os.getenv("GIFT_URL", "")  # ссылка на файл чек-листа
# Путь к файлу базы. На хостинге укажите путь внутрь постоянного диска,
# напр. DB_PATH=/data/club_bot.db — иначе база обнуляется при передеплое.
DB_PATH = os.getenv("DB_PATH", "club_bot.db")

def site_link() -> str:
    sep = "&" if "?" in SITE_URL else "?"
    return f"{SITE_URL}{sep}{UTM}" if UTM else SITE_URL
