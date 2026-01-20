import feedparser
import hashlib
import sqlite3
import os
import re
from urllib.parse import urlparse

from langdetect import detect
from deep_translator import GoogleTranslator
from telegram import Bot

# ======================
# CONFIG
# ======================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL = "@globalanimaladoptions"  # username del CANALE

# Filtri opzionali (lasciali vuoti per pubblicare tutto)
ALLOWED_SPECIES = set()     # es: {"dog", "cat"}
ALLOWED_COUNTRIES = set()   # es: {"IT", "ES"}

MAX_POSTS_PER_RUN = 10      # anti-spam

# ======================
# BOT
# ======================
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN non trovato")

bot = Bot(BOT_TOKEN)

# ======================
# DATABASE
# ======================
conn = sqlite3.connect("ads.db")
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS ads (
    id TEXT PRIMARY KEY,
    url TEXT
)
""")
conn.commit()

# ======================
# FEEDS
# ======================
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

# ======================
# UTILS
# ======================
def already_sent(ad_id):
    cur.execute("SELECT 1 FROM ads WHERE id=?", (ad_id,))
    return cur.fetchone() is not None

def save_ad(ad_id, url):
    cur.execute("INSERT INTO ads VALUES (?,?)", (ad_id, url))
    conn.commit()

def translate_all(text):
    try:
        lang = detect(text)
    except:
        lang = "en"

    en = GoogleTranslator(source=lang, target="en").translate(text)
    it = GoogleTranslator(source="en", target="it").translate(en)
    es = GoogleTranslator(source="en", target="es").translate(en)
    return en, it, es, lang

# ======================
# IMAGE EXTRACTION
# ======================
IMG_RE = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.I)

def pick_image(entry):
    if hasattr(entry, "media_content"):
        for m in entry.media_content:
            if m.get("url"):
                return m["url"]

    if hasattr(entry, "media_thumbnail"):
        for m in entry.media_thumbnail:
            if m.get("url"):
                return m["url"]

    if hasattr(entry, "links"):
        for l in entry.links:
            if l.get("rel") == "enclosure" and l.get("href"):
                return l["href"]

    html = getattr(entry, "summary", "")
    m = IMG_RE.search(html)
    if m:
        return m.group(1)

    return None

# ======================
# SPECIES DETECTION
# ======================
SPECIES_KEYWORDS = {
    "dog": ["dog", "puppy", "cane", "cucciolo", "perro"],
    "cat": ["cat", "kitten", "gatto", "gattino", "gato"],
    "rabbit": ["rabbit", "coniglio", "conejo"],
    "bird": ["bird", "uccello", "ave"],
    "horse": ["horse", "cavallo", "caballo"]
}

def detect_species(title, text):
    hay = f"{title} {text}".lower()
    for sp, kws in SPECIES_KEYWORDS.items():
        for kw in kws:
            if kw in hay:
                return sp
    return "other"

# ======================
# COUNTRY DETECTION
# ======================
DOMAIN_MAP = {
    "enpa.org": "IT",
    "oipa.org": "IT",
    "legadelcane.it": "IT",
    "protectoras.org": "ES",
    "adoptame.com": "ES",
    "la-spa.fr": "FR",
    "secondechance.org": "FR",
    "rspca.org.uk": "UK",
    "petrescue.com.au": "AU",
    "petlove.com.br": "BR",
    "adoptapet.mx": "MX",
    "tiervermittlung.de": "DE",
    "petfinder.com": "US",
    "adoptapet.com": "US"
}

def detect_country(url):
    netloc = urlparse(url).netloc.lower()
    for d, c in DOMAIN_MAP.items():
        if d in netloc:
            return c
    return "UNK"

# ======================
# HASHTAGS
# ======================
def build_hashtags(species, country, lang):
    tags = [f"#{species}", f"#{country.lower()}", f"#{lang}", "#adoption", "#rescue"]
    return " ".join(dict.fromkeys(tags))

# ======================
# POST
# ======================
def post(ad):
    msg = f"""🐾 {ad['title']}
🏷 {ad['species'].upper()} • 🌍 {ad['country']}

🇬🇧
{ad['en']}

🇮🇹
{ad['it']}

🇪🇸
{ad['es']}

🔗 {ad['url']}

{ad['hashtags']}
"""
    try:
        if ad["image"]:
            bot.send_photo(CHANNEL, ad["image"], caption=msg)
        else:
            bot.send_message(CHANNEL, msg)
    except:
        bot.send_message(CHANNEL, msg)

# ======================
# MAIN
# ======================
def main():
    posted = 0

    for feed_url in FEEDS:
        if posted >= MAX_POSTS_PER_RUN:
            break

        feed = feedparser.parse(feed_url)
        for e in feed.entries:
            if posted >= MAX_POSTS_PER_RUN:
                break

            if not hasattr(e, "link") or not hasattr(e, "title"):
                continue

            ad_id = hashlib.sha256(e.link.encode()).hexdigest()
            if already_sent(ad_id):
                continue

            raw = getattr(e, "summary", e.title)
            species = detect_species(e.title, raw)
            country = detect_country(e.link)

            if ALLOWED_SPECIES and species not in ALLOWED_SPECIES:
                continue
            if ALLOWED_COUNTRIES and country not in ALLOWED_COUNTRIES:
                continue

            en, it, es, lang = translate_all(raw)

            ad = {
                "title": e.title,
                "url": e.link,
                "species": species,
                "country": country,
                "en": en,
                "it": it,
                "es": es,
                "hashtags": build_hashtags(species, country, lang),
                "image": pick_image(e)
            }

            post(ad)
            save_ad(ad_id, e.link)
            posted += 1

if __name__ == "__main__":
    try:
        main()
    finally:
        conn.close()
