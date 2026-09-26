---
name: telegram-scraper
description: Read, search, export and analyze PUBLIC Telegram channels (t.me/<channel>) without an API key or login, using the tgscraper CLI / Python library. Use when the user mentions a Telegram channel, a t.me link, wants the latest posts, news or announcements from Telegram, wants to monitor a channel, export posts to CSV/JSON/Excel/SQLite, download channel photos/videos, or get channel statistics (views, top posts, posting times, hashtags, sentiment).
---

# Telegram Scraper

`tgscraper` reads the public web preview of Telegram channels (`https://t.me/s/<channel>`).
No API key, phone number or login. Only **public channels with web preview** work — not private
groups, chats or bots.

## 0. Setup (once)

```bash
tgscraper --version || pip install "telegram-channel-scraper[all]"
```

If the `telegram-scraper` MCP tools (`get_messages`, `search_messages`, `get_channel_info`,
`analyze_channel`, ...) are available, prefer them over the shell — same features.

Channel arguments accept `durov`, `@durov`, `t.me/durov` or `https://t.me/s/durov`.
For a post link `https://t.me/durov/123` the channel is `durov` and the message id is `123`.

## 1. Pick the right command

| User wants | Command |
|---|---|
| Latest posts | `tgscraper durov -n 20 --json` |
| Posts in a date range | `tgscraper durov -n 0 --since 2026-01-01 --until 2026-01-31 --json` |
| Posts about a topic (whole history) | `tgscraper search durov "privacy" -n 30 --json` |
| Filter recent posts by words | `tgscraper durov -n 200 -k bitcoin -k btc --json` |
| Only posts with photos/videos | `tgscraper durov --media-only --media-type photo --json` |
| Popular posts | `tgscraper durov -n 300 --min-views 100000 --json` |
| Channel info (subscribers, description) | `tgscraper info durov --json` |
| Statistics / analysis | `tgscraper stats durov -n 300 --json` |
| Save to a file | `tgscraper durov -n 500 -o durov.csv` (`.json .jsonl .xlsx .db .md`) |
| Several channels | `tgscraper chan1 chan2 chan3 -n 50 -o all.db` |
| Only new posts since last run | `tgscraper durov --incremental -o archive.db` |
| Download photos/videos | `tgscraper media durov -n 30 -d ./media` |
| Monitor for new posts | `tgscraper watch durov -i 120 --webhook URL` (long-running; run in background) |

`-n 0` means "no limit" (whole history — can be slow for big channels; combine with `--since`).

## 2. Output (`--json`)

A JSON array, newest first. Each message:

```json
{"id": 123, "channel": "durov", "url": "https://t.me/durov/123", "date": "2026-01-10T09:30:00+00:00",
 "text": "...", "views": 1250000, "author": null, "edited": false, "forwarded_from": null, "reply_to": null,
 "media": [{"type": "photo", "url": "https://cdn.../x.jpg"}], "reactions": {"👍": 15000},
 "hashtags": ["news"], "mentions": ["telegram"], "links": ["https://..."], "html": "..."}
```

Pipe large results through `jq` instead of reading everything, e.g.
`tgscraper durov -n 200 --json | jq '[.[] | {url, views, text: .text[:120]}]'`.

## 3. Python (for custom processing)

```python
import tgscraper as tg
posts = tg.scrape("durov", limit=100, since="2026-01-01", keywords=["ton"])
tg.export(posts, "out.xlsx")
stats = tg.summarize(posts)            # dict: top_posts, posts_by_hour, top_hashtags, sentiment...
results = tg.scrape_many(["a", "b"])   # concurrent, {channel: [Message] | Exception}
```

## 4. Answering well

- Always cite posts with their `url` and date.
- Report views as numbers (`1.2M`), and say how many posts you analyzed.
- `sentiment` is a rough lexicon score (-1..1), mention that it is approximate.
- Errors: `ChannelNotFound` → the channel is private, misspelled, or has web preview disabled.
  Network / HTTP 429 errors → wait and retry, or pass a proxy with `-p socks5://host:port`.
- Respect privacy and Telegram's terms: only public data, reasonable request volume.
