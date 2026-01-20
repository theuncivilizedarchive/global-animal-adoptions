import feedparser
import hashlib
import sqlite3
import os
from langdetect import detect
from deep_translator import GoogleTranslator
from telegram import Bot

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL = "@animaladoptionsbot"  # il tuo canale

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

def already_sent(ad_id: str) -> bool:
    cur.execute("SELECT 1 FROM ads WHERE id=?", (ad_id,))
    return cur.fetchone() is not None

def save_ad(ad_id: str, url: str) -> None:
    cur.execute("INSERT INTO ads VALUES (?,?)", (ad_id, url))
    conn.commit()

def translate(text: str):
    try:
        lang = detect(text)
    except:
        lang = "en"

    en = GoogleTranslator(source=lang, target="en").translate(text)
    it = GoogleTranslator(source="en", target="it").translate(en)
    es = GoogleTranslator(source="en", target="es").translate(en)
    return en, it, es

def pick_image_url(entry) -> str | None:
    """
    Prova a trovare una foto dal feed RSS/Atom in diversi campi comuni.
    Non tutti i feed forniscono immagini.
    """
    # media_content / media_thumbnail (molto comuni)
    if hasattr(entry, "media_content") and entry.media_content:
        url = entry.media_content[0].get("url")
        if url:
            return url

    if hasattr(entry, "media_thumbnail") and entry.media_thumbnail:
        url = entry.media_thumbnail[0].get("url")
        if url:
            return url

    # enclosure links (alcuni feed)
    if hasattr(entry, "links"):
        for l in entry.links:
            if l.get("rel") == "enclosure":
                href = l.get("href")
                if href:
                    return href

    # image in "summary_detail" o "summary" (a volte c'è HTML con <img ...>)
    # Evito parsing HTML pesante: feedparser spesso già estrae media_*
    return None

def build_message(ad) -> str:
    return f"""🐾 {ad['title']}

🇬🇧
{ad['en']}

🇮🇹
{ad['it']}

🇪🇸
{ad['es']}

🔗 {ad['url']}
"""

def post(ad) -> None:
    msg = build_message(ad)
    try:
        if ad.get("image_url"):
            # Se la foto non è accettata da Telegram o URL non valido, andiamo in fallback
            bot.send_photo(chat_id=CHANNEL, photo=ad["image_url"], caption=msg)
        else:
            bot.send_message(chat_id=CHANNEL, text=msg)

        print(f"Pubblicato: {ad['title']}")
    except Exception as e:
        # fallback: prova a inviare solo testo se la foto fallisce
        print(f"Errore invio (foto/testo): {e}")
        try:
            bot.send_message(chat_id=CHANNEL, text=msg)
            print(f"Fallback testo OK: {ad['title']}")
        except Exception as e2:
            print(f"Errore anche col fallback testo: {e2}")

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

def main():
    for feed_url in FEEDS:
        feed = feedparser.parse(feed_url)

        # se feed rotto / down
        if getattr(feed, "bozo", 0):
            print(f"Feed problematico: {feed_url} | bozo_exception: {getattr(feed, 'bozo_exception', '')}")
            continue

        for e in feed.entries:
            link = getattr(e, "link", None)
            title = getattr(e, "title", None)

            if not link or not title:
                continue

            ad_id = hashlib.sha256(link.encode()).hexdigest()
            if already_sent(ad_id):
                continue

            text = e.summary if hasattr(e, "summary") and e.summary else title
            en, it, es = translate(text)

            image_url = pick_image_url(e)

            ad = {
                "title": title,
                "url": link,
                "en": en,
                "it": it,
                "es": es,
                "image_url": image_url
            }

            post(ad)
            save_ad(ad_id, link)

if __name__ == "__main__":
    try:
        main()
    finally:
        conn.close()
