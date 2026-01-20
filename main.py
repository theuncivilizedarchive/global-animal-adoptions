import feedparser
import hashlib
import sqlite3
import os
from langdetect import detect
from deep_translator import GoogleTranslator
from telegram import Bot

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL = "@animaladoptionsbot"

bot = Bot(BOT_TOKEN)

conn = sqlite3.connect("ads.db")
cur = conn.cursor()

def already_sent(ad_id):
    cur.execute("SELECT 1 FROM ads WHERE id=?", (ad_id,))
    return cur.fetchone() is not None

def save_ad(ad_id, url):
    cur.execute("INSERT INTO ads VALUES (?,?)", (ad_id, url))
    conn.commit()

def translate(text):
    try:
        lang = detect(text)
    except:
        lang = "en"

    en = GoogleTranslator(source=lang, target="en").translate(text)
    it = GoogleTranslator(source="en", target="it").translate(en)
    es = GoogleTranslator(source="en", target="es").translate(en)
    return en, it, es

def post(ad):
    msg = f"""🐾 {ad['title']}

🇬🇧
{ad['en']}

🇮🇹
{ad['it']}

🇪🇸
{ad['es']}

🔗 {ad['url']}
"""
    bot.send_message(CHANNEL, msg)

FEEDS = [
    "https://www.petfinder.com/rss/search/",
    "https://www.adoptapet.com/adoptable-pets/rss",
    "https://rescuegroups.org/feed/",
    "https://www.petrescue.com.au/rss/adoptable",
    "https://www.secondechance.org/feed",
    "https://www.rspca.org.uk/adopt-pets/feed",
    "https://www.adoptame.com/feed",
    "https://protectoras.org/feed",
    "https://www.fundacion-affinity.org/feed",
    "https://www.enpa.org/feed/",
    "https://www.oipa.org/feed/",
    "https://www.legadelcane.it/feed/",
    "https://www.gattileitaliano.it/feed/",
    "https://www.la-spa.fr/rss/",
    "https://www.cats.org.uk/rss/adoptable",
    "https://www.dogstrust.org.uk/feed",
    "https://www.petlove.com.br/feed",
    "https://adoptapet.mx/feed",
    "https://www.tiervermittlung.de/feed"
]


for feed_url in FEEDS:
    feed = feedparser.parse(feed_url)

    for e in feed.entries:
        ad_id = hashlib.sha256(e.link.encode()).hexdigest()

        if already_sent(ad_id):
            continue

        text = e.summary if hasattr(e, "summary") else e.title
        en, it, es = translate(text)

        ad = {
            "title": e.title,
            "url": e.link,
            "en": en,
            "it": it,
            "es": es
        }

        post(ad)
        save_ad(ad_id, e.link)

conn.close()
