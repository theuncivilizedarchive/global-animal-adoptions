# 🌍 Global Animal Adoptions Bot

An automated bot that collects **animal adoption listings from around the world** and publishes them to a Telegram channel in **multiple languages**.

The goal of this project is to help animals find a home by increasing the visibility of adoption posts from shelters, rescues, and organizations internationally.

👉 **Telegram Channel:** https://t.me/globalanimaladoptions

---

## ✨ Features

- 🐾 Collects animal adoption posts from:
  - RSS feeds (international adoption websites)
  - Websites without RSS using HTML scraping
- 🌍 International coverage
- 🌐 Automatic translation into:
  - English 🇬🇧
  - Italian 🇮🇹
  - Spanish 🇪🇸
- 🖼️ Smart image handling:
  - Uses feed images when available
  - Scrapes images from websites
  - Falls back to text-only posts if needed
- 🧹 Cleans HTML content (no `<p>`, `<a>`, blog junk, etc.)
- 🚫 Filters out blog posts, news, and technical updates
- 🏷️ Automatic hashtags:
  - Species (#dog, #cat, …)
  - Country (#it, #es, #us, …)
  - Language (#en, #it, #es)
- 🔁 Prevents duplicate posts using SQLite
- ⏱️ Runs automatically with GitHub Actions (every few minutes)
- 💸 100% free hosting (no server required)

---

## 📢 Telegram Channel

All collected adoption posts are published here:

➡️ **https://t.me/globalanimaladoptions**

Feel free to follow, share, and help animals find a loving home ❤️

---

## ⚙️ How It Works

1. GitHub Actions runs the bot on a schedule
2. The bot:
   - Fetches RSS feeds
   - Scrapes selected adoption websites
   - Cleans and translates the content
   - Detects species and country
   - Filters non-adoption content
3. New adoption posts are sent to Telegram
4. Previously posted items are skipped using a persistent SQLite database

---

## 🛠️ Technologies Used

- Python 3.10
- GitHub Actions (automation & scheduling)
- Telegram Bot API
- SQLite (anti-duplicate storage)
- Libraries:
  - `feedparser`
  - `requests`
  - `beautifulsoup4`
  - `langdetect`
  - `deep-translator`
  - `python-telegram-bot`

---

## 🚀 Running Automatically

The bot is designed to run automatically using **GitHub Actions** with a cron schedule.

No VPS, no paid services, no manual intervention required.

---

## ❤️ Contributing

Contributions are welcome!

You can help by:
- Adding new adoption sources
- Improving scraping logic
- Improving language detection or translations
- Reporting bugs or false positives

---

## ⚠️ Disclaimer

This project is intended **only to promote animal adoptions**.  
All content belongs to the original shelters and organizations.

If you manage a shelter and want your content removed or improved, please get in touch.

---

## 🐶🐱 Let’s help animals find a home

If this project helps even one animal get adopted, it’s worth it.
