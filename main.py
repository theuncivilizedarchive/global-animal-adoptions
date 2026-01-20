import feedparser
import hashlib
import sqlite3
import os
from langdetect import detect
from deep_translator import GoogleTranslator
from telegram import Bot

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL = "@globalanimaladoptions"  # il tuo canale

conn = sqlite3.connect("ads.db")
cur = conn.cursor()

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN non trovato. Imposta il secret BOT_TOKEN su GitHub Actions.")

bot = Bot(BOT_TOKEN)

conn = sqlite3.connect("ads.db")
cur = conn.cursor()

# Tabella anti-duplicati
cur.execute("""
CREATE TABLE IF NOT EXISTS ads (
    id TEXT PRIMARY KEY,
    url TEXT
)
""")
conn.commit()

