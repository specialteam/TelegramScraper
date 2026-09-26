"""Sync and async HTTP clients that page through ``https://t.me/s/<channel>``."""
from __future__ import annotations

import asyncio
import itertools
import logging
import random
import time
from dataclasses import dataclass, field
from typing import AsyncIterator, Dict, Iterator, List, Optional, Sequence, Set, Tuple, Union

import httpx

from .filters import MessageFilter
from .models import Channel, Message
from .parser import normalize_channel, parse_page

log = logging.getLogger("tgscraper")

BASE_URL = "https://t.me/s/"
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}
RETRY_STATUSES = {429, 500, 502, 503, 504}


class ScraperError(Exception):
    """Base error of this package."""


class ChannelNotFound(ScraperError):
    """The channel does not exist, is private, or has no public web preview."""


Page = Tuple[List[Message], Channel, Optional[int]]


@dataclass
class _Walk:
    """Pagination state shared by the sync and async clients."""

    limit: Optional[int]
    flt: MessageFilter
    min_id: Optional[int] = None
    yielded: int = 0
    seen: Set[int] = field(default_factory=set)
    done: bool = False

    def feed(self, messages: List[Message], before: Optional[int]) -> List[Message]:
        """Take one page (oldest->newest); return matches newest-first and update ``done``."""
        out = []
        new = [m for m in reversed(messages) if m.id not in self.seen]
        if not new:
            self.done = True
            return out
        for msg in new:
            self.seen.add(msg.id)
            if self.min_id is not None and msg.id <= self.min_id:
                self.done = True
                break
            if self.flt.since and msg.date and msg.date < self.flt.since:
                self.done = True
                break
            if self.flt.matches(msg):
                out.append(msg)
                self.yielded += 1
                if self.limit is not None and self.yielded >= self.limit:
                    self.done = True
                    break
        if before is None:
            self.done = True
        return out


def _build_filter(flt: Optional[MessageFilter], kwargs: Dict) -> MessageFilter:
    if flt is not None and kwargs:
        raise TypeError("Pass either filter=MessageFilter(...) or filter keyword arguments, not both")
    return flt or MessageFilter(**kwargs)


def _page_params(before: Optional[int], query: Optional[str]) -> Dict[str, Union[str, int]]:
    params: Dict[str, Union[str, int]] = {}
    if before:
        params["before"] = before
    if query:
        params["q"] = query
    return params


class _Base:
    def __init__(
        self,
        proxies: Union[None, str, Sequence[str]] = None,
        timeout: float = 20.0,
        retries: int = 3,
        delay: float = 0.5,
        headers: Optional[Dict[str, str]] = None,
    ) -> None:
        if isinstance(proxies, str):
            proxies = [proxies]
        self.proxies: List[Optional[str]] = list(proxies) if proxies else [None]
        self.timeout = timeout
        self.retries = retries
        self.delay = delay
        self.headers = {**DEFAULT_HEADERS, **(headers or {})}

    def _wait_time(self, attempt: int, response: Optional[httpx.Response]) -> float:
        if response is not None and response.headers.get("Retry-After", "").isdigit():
            return float(response.headers["Retry-After"])
        return min(30.0, (2 ** attempt) * max(self.delay, 0.5)) + random.uniform(0, 0.3)

    @staticmethod
    def _check(response: httpx.Response, channel: str) -> None:
        if response.status_code == 404 or response.is_redirect:
            raise ChannelNotFound(
                f"Channel '{channel}' not found or has no public preview (https://t.me/s/{channel})"
            )


class Scraper(_Base):
    """Synchronous scraper.

    >>> with Scraper() as s:
    ...     for msg in s.iter_messages("durov", limit=10):
    ...         print(msg.date, msg.text)
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._clients = [
            httpx.Client(proxy=p, timeout=self.timeout, headers=self.headers, follow_redirects=False)
            for p in self.proxies
        ]
        self._cycle = itertools.cycle(self._clients)
        self._last_request = 0.0

    # --- plumbing -------------------------------------------------------
    def _get(self, channel: str, params: Dict) -> str:
        url = BASE_URL + channel
        response = None
        for attempt in range(self.retries + 1):
            wait = self.delay - (time.monotonic() - self._last_request)
            if wait > 0:
                time.sleep(wait)
            self._last_request = time.monotonic()
            try:
                response = next(self._cycle).get(url, params=params)
            except httpx.TransportError as exc:
                if attempt >= self.retries:
                    raise ScraperError(f"Network error for {url}: {exc}") from exc
                log.warning("Network error (%s), retrying...", exc)
                time.sleep(self._wait_time(attempt, None))
                continue
            self._check(response, channel)
            if response.status_code in RETRY_STATUSES and attempt < self.retries:
                log.warning("HTTP %s for %s, retrying...", response.status_code, url)
                time.sleep(self._wait_time(attempt, response))
                continue
            if response.status_code != 200:
                raise ScraperError(f"HTTP {response.status_code} for {url}")
            return response.text
        raise ScraperError(f"Giving up on {url}")

    def get_page(self, channel: str, before: Optional[int] = None, query: Optional[str] = None) -> Page:
        channel = normalize_channel(channel)
        return parse_page(self._get(channel, _page_params(before, query)), channel)

    # --- public API -----------------------------------------------------
    def channel_info(self, channel: str) -> Channel:
        """Title, description, subscriber count, photo... of a channel."""
        return self.get_page(channel)[1]

    def iter_messages(
        self,
        channel: str,
        limit: Optional[int] = 100,
        *,
        query: Optional[str] = None,
        min_id: Optional[int] = None,
        before: Optional[int] = None,
        max_pages: Optional[int] = None,
        filter: Optional[MessageFilter] = None,
        **filter_kwargs,
    ) -> Iterator[Message]:
        """Yield messages newest-first.

        ``query`` is a server-side search. Filters (``since``, ``until``, ``keywords``, ``regex``,
        ``media_only``, ``media_types``, ``min_views``, ``hashtag``) are applied client-side.
        ``min_id`` stops at messages older than or equal to that id (used for incremental scraping).
        ``before`` starts from messages older than that id. ``limit=None`` scrapes the whole history.
        """
        channel = normalize_channel(channel)
        walk = _Walk(limit=limit, flt=_build_filter(filter, filter_kwargs), min_id=min_id)
        for page_no in itertools.count(1):
            messages, _, before = self.get_page(channel, before, query)
            yield from walk.feed(messages, before)
            if walk.done or (max_pages and page_no >= max_pages):
                return

    def get_messages(self, channel: str, limit: Optional[int] = 100, **kwargs) -> List[Message]:
        """Same as :meth:`iter_messages` but returns a list."""
        return list(self.iter_messages(channel, limit, **kwargs))

    def get_message(self, channel: str, message_id: int) -> Optional[Message]:
        """Fetch a single message by id (``None`` if deleted)."""
        messages, _, _ = self.get_page(channel, before=message_id + 1)
        return next((m for m in messages if m.id == message_id), None)

    def close(self) -> None:
        for client in self._clients:
            client.close()

    def __enter__(self) -> "Scraper":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


class AsyncScraper(_Base):
    """Asynchronous scraper, ideal for many channels at once.

    >>> async with AsyncScraper() as s:
    ...     results = await s.scrape_many(["durov", "telegram"], limit=50)
    """

    def __init__(self, *args, concurrency: int = 5, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._clients = [
            httpx.AsyncClient(proxy=p, timeout=self.timeout, headers=self.headers, follow_redirects=False)
            for p in self.proxies
        ]
        self._cycle = itertools.cycle(self._clients)
        self._semaphore = asyncio.Semaphore(concurrency)

    async def _get(self, channel: str, params: Dict) -> str:
        url = BASE_URL + channel
        for attempt in range(self.retries + 1):
            async with self._semaphore:
                if self.delay:
                    await asyncio.sleep(self.delay)
                try:
                    response = await next(self._cycle).get(url, params=params)
                except httpx.TransportError as exc:
                    if attempt >= self.retries:
                        raise ScraperError(f"Network error for {url}: {exc}") from exc
                    await asyncio.sleep(self._wait_time(attempt, None))
                    continue
            self._check(response, channel)
            if response.status_code in RETRY_STATUSES and attempt < self.retries:
                await asyncio.sleep(self._wait_time(attempt, response))
                continue
            if response.status_code != 200:
                raise ScraperError(f"HTTP {response.status_code} for {url}")
            return response.text
        raise ScraperError(f"Giving up on {url}")

    async def get_page(self, channel: str, before: Optional[int] = None, query: Optional[str] = None) -> Page:
        channel = normalize_channel(channel)
        return parse_page(await self._get(channel, _page_params(before, query)), channel)

    async def channel_info(self, channel: str) -> Channel:
        return (await self.get_page(channel))[1]

    async def iter_messages(
        self,
        channel: str,
        limit: Optional[int] = 100,
        *,
        query: Optional[str] = None,
        min_id: Optional[int] = None,
        before: Optional[int] = None,
        max_pages: Optional[int] = None,
        filter: Optional[MessageFilter] = None,
        **filter_kwargs,
    ) -> AsyncIterator[Message]:
        channel = normalize_channel(channel)
        walk = _Walk(limit=limit, flt=_build_filter(filter, filter_kwargs), min_id=min_id)
        for page_no in itertools.count(1):
            messages, _, before = await self.get_page(channel, before, query)
            for msg in walk.feed(messages, before):
                yield msg
            if walk.done or (max_pages and page_no >= max_pages):
                return

    async def get_messages(self, channel: str, limit: Optional[int] = 100, **kwargs) -> List[Message]:
        return [m async for m in self.iter_messages(channel, limit, **kwargs)]

    async def get_message(self, channel: str, message_id: int) -> Optional[Message]:
        messages, _, _ = await self.get_page(channel, before=message_id + 1)
        return next((m for m in messages if m.id == message_id), None)

    async def scrape_many(
        self, channels: Sequence[str], limit: Optional[int] = 100, **kwargs
    ) -> Dict[str, Union[List[Message], Exception]]:
        """Scrape several channels concurrently. Failed channels map to their exception."""
        async def one(ch: str):
            try:
                return await self.get_messages(ch, limit, **kwargs)
            except Exception as exc:  # noqa: BLE001 - reported per channel
                return exc

        results = await asyncio.gather(*(one(c) for c in channels))
        return {normalize_channel(c): r for c, r in zip(channels, results)}

    async def aclose(self) -> None:
        for client in self._clients:
            await client.aclose()

    async def __aenter__(self) -> "AsyncScraper":
        return self

    async def __aexit__(self, *exc) -> None:
        await self.aclose()
