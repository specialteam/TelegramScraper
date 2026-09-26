"""tgscraper — scrape public Telegram channels without an API key, login or phone number.

Quick start::

    import tgscraper as tg

    posts = tg.scrape("durov", limit=50)           # list[Message], newest first
    tg.export(posts, "durov.csv")                   # .json .jsonl .csv .xlsx .db .md
    print(tg.channel_info("durov").subscribers)
    print(tg.format_summary(tg.summarize(posts)))
"""
from __future__ import annotations

import asyncio
from typing import Dict, List, Optional, Sequence, Union

from .analytics import format_summary, sentiment, summarize, top_words
from .client import AsyncScraper, ChannelNotFound, Scraper, ScraperError
from .exporters import export, flatten, load, to_json, to_markdown
from .filters import MessageFilter
from .media import download_media
from .models import Channel, Media, Message
from .monitor import telegram_notifier, watch, webhook_notifier
from .parser import normalize_channel
from .state import State

__version__ = "2.0.0"

__all__ = [
    "scrape", "scrape_many", "search", "channel_info", "get_message",
    "Scraper", "AsyncScraper", "MessageFilter", "State",
    "Message", "Media", "Channel", "ScraperError", "ChannelNotFound",
    "export", "load", "flatten", "to_json", "to_markdown", "download_media",
    "summarize", "format_summary", "sentiment", "top_words",
    "watch", "webhook_notifier", "telegram_notifier", "normalize_channel",
]

Proxy = Union[None, str, Sequence[str]]


def scrape(
    channel: str,
    limit: Optional[int] = 100,
    *,
    proxy: Proxy = None,
    incremental: bool = False,
    state_file: Optional[str] = None,
    **options,
) -> List[Message]:
    """Scrape the latest ``limit`` messages (newest first) of a public channel.

    Filters: ``since``, ``until`` (``"2026-01-01"``), ``keywords=["btc"]``, ``regex``, ``media_only``,
    ``media_types=["photo"]``, ``min_views``, ``hashtag``. Server-side search: ``query="text"``.
    ``incremental=True`` only returns posts newer than the previous incremental run.
    """
    state = State(state_file) if incremental else None
    name = normalize_channel(channel)
    if state and state.last_id(name) and "min_id" not in options:
        options["min_id"] = state.last_id(name)
    with Scraper(proxies=proxy) as s:
        messages = s.get_messages(name, limit, **options)
    if state:
        for m in messages:
            state.update(name, m.id)
        state.save()
    return messages


def scrape_many(
    channels: Sequence[str], limit: Optional[int] = 100, *, proxy: Proxy = None, concurrency: int = 5, **options
) -> Dict[str, Union[List[Message], Exception]]:
    """Scrape several channels concurrently. Returns ``{channel: messages or exception}``."""
    async def run():
        async with AsyncScraper(proxies=proxy, concurrency=concurrency) as s:
            return await s.scrape_many(channels, limit, **options)
    return asyncio.run(run())


def search(channel: str, query: str, limit: Optional[int] = 50, *, proxy: Proxy = None, **options) -> List[Message]:
    """Search a channel's history using Telegram's own search."""
    return scrape(channel, limit, proxy=proxy, query=query, **options)


def channel_info(channel: str, *, proxy: Proxy = None) -> Channel:
    """Title, description, subscriber count and photo of a channel."""
    with Scraper(proxies=proxy) as s:
        return s.channel_info(channel)


def get_message(channel: str, message_id: int, *, proxy: Proxy = None) -> Optional[Message]:
    """One message by id, or ``None``."""
    with Scraper(proxies=proxy) as s:
        return s.get_message(channel, message_id)
