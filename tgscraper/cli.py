"""Command line interface: ``tgscraper durov -n 50 -o durov.csv``."""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import List, Optional, Sequence

from . import __version__
from .analytics import format_summary, summarize
from .client import ScraperError
from .exporters import FORMATS, export, load, to_json, to_markdown
from .media import download_media
from .models import Message

COMMANDS = {"scrape", "info", "search", "stats", "watch", "media", "mcp", "dashboard"}

EPILOG = """examples:
  tgscraper durov                          # latest 20 posts, pretty in the terminal
  tgscraper durov -n 500 -o durov.csv      # save as CSV (.json .jsonl .xlsx .db .md too)
  tgscraper durov telegram -n 100 -o all.db
  tgscraper durov --since 2026-01-01 --keyword ton --media-only
  tgscraper search durov "privacy" -n 30
  tgscraper info durov
  tgscraper stats durov -n 300              # or: tgscraper stats durov.json
  tgscraper media durov -n 50 -d ./media
  tgscraper watch durov --webhook https://example.com/hook
  tgscraper mcp                             # run the MCP server for AI assistants
  tgscraper durov --json | jq '.[0].text'  # machine-readable output
"""


def _add_scrape_options(p: argparse.ArgumentParser, many: bool = True) -> None:
    if many:
        p.add_argument("channels", nargs="+", help="channel usernames or links (durov, @durov, t.me/durov)")
    p.add_argument("-n", "--limit", type=int, default=20, help="max messages per channel, 0 = all (default 20)")
    p.add_argument("-o", "--output", help="save to file; format from extension: " + ", ".join(FORMATS))
    p.add_argument("-f", "--format", choices=FORMATS, help="force output format")
    p.add_argument("--json", action="store_true", help="print JSON to stdout (for scripts and AI agents)")
    p.add_argument("--since", help="only posts on/after this date (YYYY-MM-DD)")
    p.add_argument("--until", help="only posts on/before this date (YYYY-MM-DD)")
    p.add_argument("-k", "--keyword", action="append", default=[], help="keep posts containing a keyword (repeatable)")
    p.add_argument("--regex", help="keep posts matching a regular expression")
    p.add_argument("--hashtag", help="keep posts with this hashtag")
    p.add_argument("--media-only", action="store_true", help="only posts with media")
    p.add_argument("--media-type", action="append", default=[],
                   help="photo, video, voice, document, round_video, sticker, link_preview (repeatable)")
    p.add_argument("--min-views", type=int, help="only posts with at least N views")
    p.add_argument("-q", "--query", help="Telegram server-side search")
    p.add_argument("--incremental", action="store_true", help="only posts newer than the last --incremental run")
    p.add_argument("--download-media", metavar="DIR", help="also download photos/videos into DIR")
    _add_common(p)


def _add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument("-p", "--proxy", action="append", help="http/socks5 proxy URL (repeat to rotate)")
    p.add_argument("-v", "--verbose", action="store_true")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tgscraper",
        description="Scrape public Telegram channels — no API key, no login.",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"tgscraper {__version__}")
    sub = parser.add_subparsers(dest="command")

    _add_scrape_options(sub.add_parser("scrape", help="scrape messages (default command)"))

    p = sub.add_parser("search", help="search inside a channel")
    p.add_argument("channels", nargs=1, metavar="channel")
    p.add_argument("search_query", metavar="query")
    _add_scrape_options(p, many=False)

    p = sub.add_parser("info", help="channel title, description, subscribers")
    p.add_argument("channels", nargs="+")
    p.add_argument("--json", action="store_true")
    _add_common(p)

    p = sub.add_parser("stats", help="statistics for a channel or a saved .json/.jsonl/.db file")
    p.add_argument("source", nargs="+", help="channel(s) or file")
    p.add_argument("-n", "--limit", type=int, default=200)
    p.add_argument("--json", action="store_true")
    _add_common(p)

    p = sub.add_parser("media", help="download photos/videos of recent posts")
    p.add_argument("channels", nargs="+")
    p.add_argument("-n", "--limit", type=int, default=20)
    p.add_argument("-d", "--dir", default="media")
    p.add_argument("-t", "--type", action="append", default=[], help="photo, video, voice... (repeatable)")
    _add_common(p)

    p = sub.add_parser("watch", help="notify on new posts (Ctrl+C to stop)")
    p.add_argument("channels", nargs="+")
    p.add_argument("-i", "--interval", type=float, default=60, help="seconds between checks (default 60)")
    p.add_argument("-k", "--keyword", action="append", default=[], help="only notify on these keywords")
    p.add_argument("--webhook", help="POST each new post as JSON to this URL")
    p.add_argument("--bot-token", help="Telegram bot token for notifications")
    p.add_argument("--chat-id", help="chat id that receives bot notifications")
    p.add_argument("--save", help="append new posts to this .jsonl/.db file")
    p.add_argument("--backfill", type=int, default=0, help="emit N existing posts on start")
    _add_common(p)

    p = sub.add_parser("mcp", help="run the MCP server (stdio) so AI assistants can use tgscraper")
    p.add_argument("--transport", default="stdio", choices=["stdio", "sse", "streamable-http"])

    sub.add_parser("dashboard", help="open the web dashboard (needs telegram-channel-scraper[dashboard])")
    return parser


def _filters(args) -> dict:
    return {
        "since": args.since, "until": args.until, "keywords": args.keyword, "regex": args.regex,
        "media_only": args.media_only, "media_types": args.media_type, "min_views": args.min_views,
        "hashtag": args.hashtag,
    }


def _print_messages(messages: Sequence[Message]) -> None:
    for m in messages:
        meta = [m.date.strftime("%Y-%m-%d %H:%M") if m.date else "", f"👁 {m.views:,}" if m.views is not None else ""]
        if m.media:
            meta.append("📎 " + ",".join(m.media_types))
        if m.forwarded_from:
            meta.append(f"↪ {m.forwarded_from}")
        print(f"\033[1m{m.url}\033[0m  " + "  ".join(x for x in meta if x))
        print(m.text or "(no text)")
        print()


def _scrape(args) -> List[Message]:
    from . import scrape
    limit = None if args.limit == 0 else args.limit
    query = getattr(args, "search_query", None) or args.query
    out: List[Message] = []
    for ch in args.channels:
        out += scrape(ch, limit, proxy=args.proxy, incremental=args.incremental, query=query, **_filters(args))
    return out


def _emit(messages: List[Message], args) -> None:
    if args.output:
        path = export(messages, args.output, args.format)
        print(f"✅ Saved {len(messages)} messages to {path}", file=sys.stderr)
    elif args.json or args.format == "json":
        print(to_json(messages))
    elif args.format == "md":
        print(to_markdown(messages))
    elif args.format:
        print("Use -o FILE with --format " + args.format, file=sys.stderr)
    else:
        _print_messages(messages)
        print(f"— {len(messages)} messages", file=sys.stderr)
    if getattr(args, "download_media", None):
        files = download_media(messages, args.download_media, proxy=(args.proxy or [None])[0])
        print(f"🖼  Downloaded {len(files)} files to {args.download_media}", file=sys.stderr)


def main(argv: Optional[Sequence[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    # `tgscraper durov` == `tgscraper scrape durov`
    if argv and not argv[0].startswith("-") and argv[0] not in COMMANDS:
        argv.insert(0, "scrape")
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 0
    logging.basicConfig(level=logging.INFO if getattr(args, "verbose", False) else logging.WARNING,
                        format="%(levelname)s %(message)s")
    try:
        return _run(args)
    except ScraperError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


def _run(args) -> int:
    from . import channel_info, scrape

    if args.command in ("scrape", "search"):
        _emit(_scrape(args), args)
    elif args.command == "info":
        infos = [channel_info(ch, proxy=args.proxy) for ch in args.channels]
        if args.json:
            print(json.dumps([i.to_dict() for i in infos], ensure_ascii=False, indent=2))
        for i in infos if not args.json else []:
            print(f"\033[1m{i.title}\033[0m  ({i.url}){'  ✔' if i.verified else ''}")
            print(f"👥 {i.subscribers:,} subscribers" if i.subscribers is not None else "👥 ?")
            if i.counters:
                print("   " + " · ".join(f"{k}: {v:,}" for k, v in i.counters.items()))
            if i.description:
                print(i.description)
            print()
    elif args.command == "stats":
        messages: List[Message] = []
        for src in args.source:
            if Path(src).is_file():
                messages += load(src)
            else:
                messages += scrape(src, args.limit or None, proxy=args.proxy)
        stats = summarize(messages)
        print(json.dumps(stats, ensure_ascii=False, indent=2, default=str) if args.json else format_summary(stats))
    elif args.command == "media":
        total = 0
        for ch in args.channels:
            msgs = scrape(ch, args.limit, proxy=args.proxy, media_only=True)
            total += len(download_media(msgs, args.dir, types=args.type or None, proxy=(args.proxy or [None])[0]))
        print(f"🖼  {total} files in {args.dir}")
    elif args.command == "watch":
        _watch(args)
    elif args.command == "mcp":
        from .mcp_server import main as mcp_main
        mcp_main(args.transport)
    elif args.command == "dashboard":
        _dashboard()
    return 0


def _watch(args) -> None:
    from .client import Scraper
    from .monitor import telegram_notifier, watch, webhook_notifier

    def printer(m: Message) -> None:
        _print_messages([m])
        sys.stdout.flush()

    handlers = [printer]
    if args.webhook:
        handlers.append(webhook_notifier(args.webhook))
    if args.bot_token and args.chat_id:
        handlers.append(telegram_notifier(args.bot_token, args.chat_id))
    if args.save:
        def saver(m: Message) -> None:
            if args.save.endswith((".db", ".sqlite", ".sqlite3")):
                export([m], args.save)  # sqlite export is an upsert
            else:
                with open(args.save, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(m.to_dict(), ensure_ascii=False) + "\n")
        handlers.append(saver)
    print(f"👀 Watching {', '.join(args.channels)} every {args.interval:g}s — Ctrl+C to stop", file=sys.stderr)
    with Scraper(proxies=args.proxy) as s:
        watch(args.channels, handlers, interval=args.interval, keywords=args.keyword or None,
              scraper=s, backfill=args.backfill)


def _dashboard() -> None:
    import subprocess
    try:
        import streamlit  # noqa: F401
    except ImportError:
        print("Dashboard needs streamlit: pip install 'telegram-channel-scraper[dashboard]'", file=sys.stderr)
        raise SystemExit(1)
    app = Path(__file__).with_name("dashboard.py")
    raise SystemExit(subprocess.call([sys.executable, "-m", "streamlit", "run", str(app)]))


if __name__ == "__main__":
    sys.exit(main())
