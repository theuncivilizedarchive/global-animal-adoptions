import feedparser
import hashlib
import sqlite3
import os
from langdetect import detect
from deep_translator import GoogleTranslator
from telegram import Bot

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL = "@globalanimaladoptions"  # username del CANALE

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN non trovato. Imposta il secret BOT_TOKEN su GitHub Actions.")

# ✅ QUI viene creato il bot
bot = Bot(BOT_TOKEN)

# 🔴 TEST TEMPORANEO (DEVE STARE QUI, SUBITO DOPO)
bot.send_message(
    chat_id=CHANNEL,
    text="✅ Test: il bot riesce a scrivere nel canale"
)

# ----- da qui in poi il resto del codice -----

conn = sqlite3.connect("ads.db")
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS ads (
    id TEXT PRIMARY KEY,
    url TEXT
)
""")
conn.commit()

def already_sent(ad_id: str) -> bool:
    cur.execute("SELECT 1 FROM ads WHERE id=?", (ad_id,))
    return cur.fetchone() is not None

def save_ad(ad_id: str, url: str) -> None:
    cur.execute("INSERT INTO ads VALUES (?,?)", (ad_id, url))
    conn.commit()
