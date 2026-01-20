import os
import re
import time
import hashlib
import sqlite3
from io import BytesIO
from urllib.parse import urlparse

import feedparser
import requests
from bs4 import BeautifulSoup

from langdetect import detect
from deep_translator import GoogleTranslator
from telegram import Bot

# ======================
# CONFIG
# ======================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL = "@globalanimaladoptions"  # <-- username del canale (non del bot)

# Filtri opzionali (lascia vuoti per pubblicare tutto)
ALLOWED_SPECIES = set()     # es: {"dog", "cat"}
ALLOWED_COUNTRIES = set()   # es: {"IT", "ES"}

# Anti-spam / rate control
MAX_POSTS_PER_RUN = 8       # quanti post max per run (con cron ogni 5 min, 3-8 è ok)
SLEEP_BETWEEN_POSTS_SEC = 1 # piccola pausa

# RSS feeds
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
    "https://www.tiervermittlung.de/feed",
]

# Pagine da scrappare (senza RSS)
SCRAPE_SOURCES = [
    ("https://www.rifugioapachioggia.it/centro-adozioni", "dog", "IT"),
    ("https://www.rifugioapachioggia.it/adotta-un-micio", "cat", "IT"),
]

UA_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
    "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
}

# ======================
# BOT + DB
# ======================
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN non trovato. Imposta il secret BOT_TOKEN su GitHub Actions.")

bot = Bot(BOT_TOKEN)

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

# ======================
# TEXT CLEANING
# ======================
IMG_RE = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.I)

def clean_html(html: str) -> str:
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def remove_wp_footer(text: str) -> str:
    """Taglia le code WordPress tipo 'Continue reading' / 'appeared first on' ecc."""
    if not text:
        return ""
    cut_markers = [
        "Continue reading",
        "Continua a leggere",
        "Continuar leyendo",
        "appeared first on",
        "è apparso per la prima volta su",
        "apareció por primera vez en",
    ]
    lowered = text.lower()
    for m in cut_markers:
        idx = lowered.find(m.lower())
        if idx != -1:
            return text[:idx].strip()
    return text

# ======================
# TRANSLATION
# ======================
def translate_all(text: str):
    text = (text or "").strip()
    if not text:
        return "", "", "", "en"
    try:
        lang = detect(text)
    except:
        lang = "en"

    en = GoogleTranslator(source=lang, target="en").translate(text)
    it = GoogleTranslator(source="en", target="it").translate(en)
    es = GoogleTranslator(source="en", target="es").translate(en)
    return en, it, es, lang

# ======================
# SPECIES + COUNTRY DETECTION
# ======================
SPECIES_KEYWORDS = {
    "dog": ["dog", "puppy", "cane", "cucciolo", "perro", "cachorro", "chien", "chiot", "hund", "welpe"],
    "cat": ["cat", "kitten", "gatto", "gattino", "gato", "chat", "chaton", "katze", "kätzchen"],
    "rabbit": ["rabbit", "coniglio", "conejo", "lapin", "kaninchen"],
    "bird": ["bird", "uccello", "ave", "pájaro", "oiseau", "vogel"],
    "horse": ["horse", "cavallo", "caballo", "cheval", "pferd"],
}

DOMAIN_HINTS = [
    ("enpa.org", "IT"),
    ("oipa.org", "IT"),
    ("legadelcane.it", "IT"),
    ("gattileitaliano.it", "IT"),
    ("rifugioapachioggia.it", "IT"),
    ("protectoras.org", "ES"),
    ("fundacion-affinity.org", "ES"),
    ("adoptame.com", "ES"),
    ("la-spa.fr", "FR"),
    ("secondechance.org", "FR"),
    ("rspca.org.uk", "UK"),
    ("cats.org.uk", "UK"),
    ("dogstrust.org.uk", "UK"),
    ("petrescue.com.au", "AU"),
    ("petlove.com.br", "BR"),
    ("adoptapet.mx", "MX"),
    ("tiervermittlung.de", "DE"),
    ("petfinder.com", "US"),
    ("adoptapet.com", "US"),
    ("rescuegroups.org", "US"),
]

TLD_TO_COUNTRY = {
    "it": "IT",
    "es": "ES",
    "fr": "FR",
    "uk": "UK",
    "de": "DE",
    "mx": "MX",
    "au": "AU",
    "br": "BR",
}

def detect_species(title: str, text: str, default: str = "other") -> str:
    hay = f"{title} {text}".lower()
    for sp, kws in SPECIES_KEYWORDS.items():
        for kw in kws:
            if kw in hay:
                return sp
    return default

def detect_country(url: str) -> str:
    try:
        netloc = urlparse(url).netloc.lower()
    except:
        return "UNK"
    for d, cc in DOMAIN_HINTS:
        if d in netloc:
            return cc
    parts = netloc.split(".")
    if len(parts) >= 2:
        tld = parts[-1]
        return TLD_TO_COUNTRY.get(tld, "UNK")
    return "UNK"

# ======================
# HASHTAGS
# ======================
def build_hashtags(species: str, country: str, lang: str) -> str:
    tags = []
    if species and species != "other":
        tags.append(f"#{species}")
    if country and country != "UNK":
        tags.append(f"#{country.lower()}")
    if lang:
        tags.append(f"#{lang.lower()}")
    tags += ["#adoption", "#rescue"]
    # de-dup
    seen = set()
    out = []
    for t in tags:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return " ".join(out)

# ======================
# IMAGE HANDLING
# ======================
def pick_image_from_feed(entry):
    """Prende immagine se il feed la fornisce (media/enclosure o <img> in summary)."""
    if hasattr(entry, "media_content") and entry.media_content:
        for m in entry.media_content:
            u = m.get("url")
            if u:
                return u

    if hasattr(entry, "media_thumbnail") and entry.media_thumbnail:
        for m in entry.media_thumbnail:
            u = m.get("url")
            if u:
                return u

    if hasattr(entry, "links"):
        for l in entry.links:
            if l.get("rel") == "enclosure" and l.get("href"):
                return l["href"]

    html = getattr(entry, "summary", "") or getattr(entry, "description", "")
    if html:
        m = IMG_RE.search(html)
        if m:
            return m.group(1)

    return None

def download_image(url: str, referer: str):
    """Scarica immagine come bytes (evita 403 se Telegram non può hotlinkare)."""
    r = requests.get(url, headers={**UA_HEADERS, "Referer": referer}, timeout=30)
    r.raise_for_status()
    return r.content

# ======================
# SCRAPING: Rifugio APA Chioggia
# ======================
def fetch_html(url: str) -> str:
    r = requests.get(url, headers={**UA_HEADERS, "Referer": url}, timeout=30)
    r.raise_for_status()
    return r.text

def scrape_rifugio_page(url: str, default_species: str):
    """
    Estrae animali da pagine tipo:
    - /centro-adozioni
    - /adotta-un-micio
    Strategia: usa <article> e considera H2/H3 come "nome animale",
    poi raccoglie paragrafi e immagini fino al prossimo nome.
    """
    html = fetch_html(url)
    soup = BeautifulSoup(html, "html.parser")

    article = soup.find("article") or soup
    animals = []
    current = None

    for el in article.find_all(["h2", "h3", "h4", "p", "img"], recursive=True):
        if el.name in ["h2", "h3", "h4"]:
            title = el.get_text(" ", strip=True)
            title = re.sub(r"\s+", " ", title).strip()
            if not title:
                continue

            # evita titoli generici
            if title.lower() in {"centro adozioni", "adotta un micio", "cani cercafamiglia"}:
                continue

            # salva precedente
            if current and current["name"] and (current["desc"] or current["images"]):
                animals.append(current)

            current = {"name": title, "desc": "", "images": [], "species": default_species, "page": url}
            continue

        if not current:
            continue

        if el.name == "p":
            txt = el.get_text(" ", strip=True)
            txt = re.sub(r"\s+", " ", txt).strip()
            if not txt:
                continue
            # elimina footer/contatti ripetuti se presenti
            if "rifugio" in txt.lower() and "chioggia" in txt.lower() and len(txt) < 40:
                continue
            current["desc"] = (current["desc"] + "\n" + txt).strip()

        if el.name == "img":
            src = el.get("src") or ""
            if src.startswith("http"):
                current["images"].append(src)

    if current and current["name"] and (current["desc"] or current["images"]):
        animals.append(current)

    # dedup immagini
    for a in animals:
        seen = set()
        uniq = []
        for im in a["images"]:
            if im not in seen:
                seen.add(im)
                uniq.append(im)
        a["images"] = uniq[:6]

    return animals

# ======================
# POSTING
# ======================
def build_message(title: str, species: str, country: str, en: str, it: str, es: str, url: str, hashtags: str) -> str:
    return f"""🐾 {title}
🏷 {species.upper()} • 🌍 {country}

🇬🇧
{en}

🇮🇹
{it}

🇪🇸
{es}

🔗 {url}

{hashtags}
"""

def send_post(title: str, message: str, image_url: str | None, image_referer: str | None):
    """
    Se c'è immagine:
    - prova a inviare come URL
    - se fallisce, scarica bytes e invia
    - se fallisce, manda testo
    """
    try:
        if image_url:
            try:
                bot.send_photo(chat_id=CHANNEL, photo=image_url, caption=message)
                print(f"[OK] Foto via URL: {title}")
                return
            except Exception as e_url:
                print(f"[WARN] Foto URL fallita: {title} | {e_url}")

            if image_referer:
                try:
                    b = download_image(image_url, referer=image_referer)
                    bot.send_photo(chat_id=CHANNEL, photo=BytesIO(b), caption=message)
                    print(f"[OK] Foto via bytes: {title}")
                    return
                except Exception as e_bytes:
                    print(f"[WARN] Foto bytes fallita: {title} | {e_bytes}")

        bot.send_message(chat_id=CHANNEL, text=message)
        print(f"[OK] Testo: {title}")
    except Exception as e:
        print(f"[ERR] Invio fallito: {title} | {e}")

# ======================
# MAIN
# ======================
def main():
    posted = 0

    # --- 1) Scraping pagine senza feed (APA Chioggia)
    for page_url, default_species, fixed_country in SCRAPE_SOURCES:
        if posted >= MAX_POSTS_PER_RUN:
            break

        try:
            items = scrape_rifugio_page(page_url, default_species=default_species)
        except Exception as e:
            print(f"[ERR] Scrape fallito {page_url}: {e}")
            continue

        for item in items:
            if posted >= MAX_POSTS_PER_RUN:
                break

            # ID stabile: pagina + nome
            ad_id = hashlib.sha256((item["page"] + "|" + item["name"]).encode()).hexdigest()
            if already_sent(ad_id):
                continue

            raw = item["desc"] or item["name"]
            raw = clean_html(raw)
            raw = remove_wp_footer(raw)

            species = item["species"] or "other"
            country = fixed_country or "UNK"

            if ALLOWED_SPECIES and species not in ALLOWED_SPECIES:
                continue
            if ALLOWED_COUNTRIES and country not in ALLOWED_COUNTRIES:
                continue

            en, it, es, lang = translate_all(raw)
            hashtags = build_hashtags(species, country, lang)

            msg = build_message(
                title=item["name"],
                species=species,
                country=country,
                en=en,
                it=it,
                es=es,
                url=item["page"],
                hashtags=hashtags
            )

            img = item["images"][0] if item["images"] else None
            send_post(item["name"], msg, img, image_referer=item["page"])
            save_ad(ad_id, item["page"] + "#" + item["name"])
            posted += 1
            time.sleep(SLEEP_BETWEEN_POSTS_SEC)

    # --- 2) RSS feeds
    for feed_url in FEEDS:
        if posted >= MAX_POSTS_PER_RUN:
            break

        feed = feedparser.parse(feed_url)
        if getattr(feed, "bozo", 0):
            print(f"[WARN] Feed problematico: {feed_url} | {getattr(feed, 'bozo_exception', '')}")
            continue

        for e in feed.entries:
            if posted >= MAX_POSTS_PER_RUN:
                break

            link = getattr(e, "link", None)
            title = getattr(e, "title", None)
            if not link or not title:
                continue

            ad_id = hashlib.sha256(link.encode()).hexdigest()
            if already_sent(ad_id):
                continue

            raw_html = getattr(e, "summary", "") or getattr(e, "description", "") or title
            raw = clean_html(raw_html)
            raw = remove_wp_footer(raw)

            species = detect_species(title, raw, default="other")
            country = detect_country(link)

            if ALLOWED_SPECIES and species not in ALLOWED_SPECIES:
                continue
            if ALLOWED_COUNTRIES and country not in ALLOWED_COUNTRIES:
                continue

            en, it, es, lang = translate_all(raw)
            hashtags = build_hashtags(species, country, lang)

            msg = build_message(
                title=title.strip(),
                species=species,
                country=country,
                en=en,
                it=it,
                es=es,
                url=link,
                hashtags=hashtags
            )

            image_url = pick_image_from_feed(e)
            send_post(title, msg, image_url, image_referer=link)

            save_ad(ad_id, link)
            posted += 1
            time.sleep(SLEEP_BETWEEN_POSTS_SEC)

if __name__ == "__main__":
    try:
        main()
    finally:
        conn.close()
