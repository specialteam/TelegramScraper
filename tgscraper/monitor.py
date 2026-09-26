"""Watch channels and push new posts to a callback, a webhook or a Telegram bot."""
from __future__ import annotations

import logging
import time
from typing import Callable, List, Optional, Sequence

import httpx

from .client import Scraper, ScraperError
from .models import Message
from .parser import normalize_channel

log = logging.getLogger("tgscraper")

Handler = Callable[[Message], None]


def webhook_notifier(url: str, timeout: float = 15) -> Handler:
    """POST every new message as JSON to ``url`` (Slack/Discord/n8n/Zapier/your API...)."""
    def send(msg: Message) -> None:
        payload = msg.to_dict()
        # Slack & Discord read "text"/"content"; everyone else gets the full message.
        payload.update({"content": f"{msg.url}\n{msg.text}"[:1900]})
        try:
            httpx.post(url, json=payload, timeout=timeout).raise_for_status()
        except httpx.HTTPError as exc:
            log.warning("Webhook failed: %s", exc)
    return send


def telegram_notifier(bot_token: str, chat_id: str, timeout: float = 15) -> Handler:
    """Forward new posts to a chat through a Telegram bot (create one with @BotFather)."""
    api = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    def send(msg: Message) -> None:
        text = f"📢 {msg.channel}\n\n{msg.text}\n\n{msg.url}"
        try:
            httpx.post(api, json={"chat_id": chat_id, "text": text[:4096]}, timeout=timeout).raise_for_status()
        except httpx.HTTPError as exc:
            log.warning("Telegram bot notification failed: %s", exc)
    return send


def watch(
    channels: Sequence[str],
    handlers: Sequence[Handler],
    interval: float = 60,
    keywords: Optional[Sequence[str]] = None,
    scraper: Optional[Scraper] = None,
    backfill: int = 0,
    iterations: Optional[int] = None,
) -> None:
    """Poll ``channels`` every ``interval`` seconds and call every handler for each new message.

    ``backfill`` = how many existing posts to emit on start (0 = only brand-new posts).
    ``keywords`` = only notify when a post contains one of them.
    ``iterations`` = stop after N polls (``None`` = forever, Ctrl+C to quit).
    """
    own = scraper is None
    scraper = scraper or Scraper()
    names: List[str] = [normalize_channel(c) for c in channels]
    last: dict = {}
    try:
        for ch in names:
            recent = scraper.get_messages(ch, limit=max(backfill, 1))
            last[ch] = max((m.id for m in recent), default=0)
            for msg in reversed(recent[:backfill]):
                _dispatch(msg, handlers, keywords)
            log.info("Watching %s (last id %s)", ch, last[ch])
        polls = 0
        while iterations is None or polls < iterations:
            time.sleep(interval)
            polls += 1
            for ch in names:
                try:
                    new = scraper.get_messages(ch, limit=None, min_id=last[ch], max_pages=5)
                except ScraperError as exc:
                    log.warning("Polling %s failed: %s", ch, exc)
                    continue
                for msg in reversed(new):  # oldest first
                    _dispatch(msg, handlers, keywords)
                    last[ch] = max(last[ch], msg.id)
    finally:
        if own:
            scraper.close()


def _dispatch(msg: Message, handlers: Sequence[Handler], keywords: Optional[Sequence[str]]) -> None:
    if keywords and not any(k.lower() in msg.text.lower() for k in keywords):
        return
    for handler in handlers:
        handler(msg)
