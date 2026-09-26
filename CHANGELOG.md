# Changelog

## 2.0.0

First release on PyPI: **`pip install "telegram-channel-scraper[all]"`**

A complete rewrite of the old single-class script into the `tgscraper` package: a Python library, a CLI, an MCP server for AI assistants, and a web dashboard. It reads public Telegram channels through `t.me/s/<channel>`, with no API key, no login and no phone number.

### Highlights
- **Rich data per post:** id, date, text and HTML, views, reactions per emoji, author, edited flag, forwards, replies, media (photos, videos, voice notes, documents, stickers, link previews), hashtags, mentions and links. Also channel info: title, description, subscribers and counters.
- **One-line API and CLI:** `tg.scrape("durov")` in Python, `tgscraper durov` in the terminal. Every command supports `--json`.
- **Search and filters:** Telegram's server-side search, date ranges, keywords, regex, hashtag, media type, minimum views, and full-history scraping.
- **Export:** JSON, JSONL, CSV (Excel-friendly), XLSX, SQLite (upsert archive) and Markdown.
- **Robust networking:** sync and async clients, concurrent multi-channel scraping, retries with backoff, `Retry-After` handling, rate limiting, and rotating HTTP/SOCKS proxies.
- **Incremental scraping, monitoring and media:** fetch only new posts since the last run; watch channels and push new posts to a webhook or a Telegram bot; download photos, videos and voice notes.
- **Analytics:** top posts, activity by day, hour and weekday, hashtags, top words, reactions, and English/Persian sentiment.
- **For AI assistants:**
  - MCP server `tgscraper-mcp` with 8 tools, 2 prompts and 1 resource, for Claude, Cursor, VS Code, Windsurf and others;
  - a Claude Skill;
  - `llms.txt` and `AGENTS.md`.
- **Dashboard and Docker:** `tgscraper dashboard` opens a Streamlit UI; `docker compose up dashboard` runs it in a container.
- **Quality:**
  - offline test suite on Python 3.9–3.13;
  - a weekly live test against real `t.me`;
  - releases published to PyPI with Trusted Publishing.

### Compatibility
- `from telegram_scraper import TelegramScraper` still works.
- The PyPI package name is `telegram-channel-scraper`, because `tgscraper` was already taken. The import name and the commands are still `tgscraper`.
