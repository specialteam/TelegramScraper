"""Tour of the tgscraper API. Run: python example.py"""
import tgscraper as tg


def main():
    # 1) Channel info
    info = tg.channel_info("durov")
    print(f"{info.title}: {info.subscribers:,} subscribers")

    # 2) Latest posts (newest first) — each one is a rich Message object
    posts = tg.scrape("durov", limit=30)
    for p in posts[:5]:
        print(p.date, p.views, p.url, p.text[:80])

    # 3) Filters: date range, keywords, media, views...
    recent_media = tg.scrape("durov", limit=10, since="2026-01-01", media_only=True)
    print(len(recent_media), "recent posts with media")

    # 4) Telegram's own search
    hits = tg.search("durov", "privacy", limit=5)
    print([h.url for h in hits])

    # 5) Save anywhere: .json .jsonl .csv .xlsx .db .md
    tg.export(posts, "durov.csv")

    # 6) Statistics
    print(tg.format_summary(tg.summarize(posts)))


if __name__ == "__main__":
    main()
