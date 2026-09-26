"""MCP (Model Context Protocol) server so AI assistants (Claude, Cursor, ChatGPT...) can read Telegram channels.

Run:  ``tgscraper-mcp``  (or ``tgscraper mcp``, or ``python -m tgscraper.mcp_server``)
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

try:  # mcp >= 2
    from mcp.server.mcpserver import MCPServer as FastMCP
except ImportError:
    try:  # mcp 1.x
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:  # pragma: no cover
        raise ImportError("The MCP server needs the 'mcp' package: pip install 'telegram-channel-scraper[mcp]'") from exc

from .analytics import summarize
from .client import AsyncScraper, ScraperError
from .exporters import export
from .models import Message

PROXY = os.environ.get("TGSCRAPER_PROXY") or None
MAX_LIMIT = int(os.environ.get("TGSCRAPER_MCP_MAX_LIMIT", "500"))
MAX_TEXT = 4000

mcp = FastMCP(
    "telegram-scraper",
    instructions=(
        "Read public Telegram channels (t.me/s/<channel>) without any API key. "
        "Channel arguments accept 'durov', '@durov' or 'https://t.me/durov'. "
        "Messages are returned newest first. Start with get_channel_info or get_messages; "
        "use search_messages for topics and analyze_channel for statistics. "
        "Only public channels with web preview enabled can be read."
    ),
)


def _scraper() -> AsyncScraper:
    return AsyncScraper(proxies=PROXY, delay=0.3)


def _compact(m: Message) -> Dict[str, Any]:
    d = m.to_dict()
    d.pop("html", None)
    if len(d["text"]) > MAX_TEXT:
        d["text"] = d["text"][:MAX_TEXT] + "… [truncated]"
    d["media"] = [{k: v for k, v in x.items() if v} for x in d["media"]]
    return {k: v for k, v in d.items() if v not in (None, [], {}, "", False) or k in ("id", "text")}


def _limit(n: Optional[int]) -> int:
    return max(1, min(int(n or 20), MAX_LIMIT))


def _error(exc: Exception) -> Dict[str, Any]:
    return {"error": str(exc)}


@mcp.tool()
async def get_channel_info(channel: str) -> Dict[str, Any]:
    """Get a public Telegram channel's title, description, subscriber count, photo and media counters."""
    try:
        async with _scraper() as s:
            return (await s.channel_info(channel)).to_dict()
    except ScraperError as exc:
        return _error(exc)


@mcp.tool()
async def get_messages(
    channel: str,
    limit: int = 20,
    since: Optional[str] = None,
    until: Optional[str] = None,
    keywords: Optional[List[str]] = None,
    hashtag: Optional[str] = None,
    media_only: bool = False,
    min_views: Optional[int] = None,
    before_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Get recent posts of a public Telegram channel, newest first.

    Args:
        channel: username or link, e.g. "durov" or "https://t.me/durov".
        limit: number of posts to return (1-500, default 20).
        since / until: ISO dates like "2026-01-31" to restrict the time range.
        keywords: keep only posts containing any of these words (case-insensitive).
        hashtag: keep only posts with this hashtag.
        media_only: keep only posts with photos/videos/files.
        min_views: keep only posts with at least this many views.
        before_id: return posts older than this message id (for paging backwards).
    """
    try:
        async with _scraper() as s:
            kwargs: Dict[str, Any] = dict(since=since, until=until, keywords=keywords or [], hashtag=hashtag,
                                          media_only=media_only, min_views=min_views)
            msgs = await s.get_messages(channel, _limit(limit), before=before_id, max_pages=100, **kwargs)
        return {"channel": channel, "count": len(msgs), "messages": [_compact(m) for m in msgs]}
    except (ScraperError, ValueError) as exc:
        return _error(exc)


@mcp.tool()
async def search_messages(channel: str, query: str, limit: int = 20) -> Dict[str, Any]:
    """Search the whole history of a public Telegram channel using Telegram's own search."""
    try:
        async with _scraper() as s:
            msgs = await s.get_messages(channel, _limit(limit), query=query, max_pages=50)
        return {"channel": channel, "query": query, "count": len(msgs), "messages": [_compact(m) for m in msgs]}
    except (ScraperError, ValueError) as exc:
        return _error(exc)


@mcp.tool()
async def get_message(channel: str, message_id: int) -> Dict[str, Any]:
    """Get one specific post, e.g. for a link like https://t.me/durov/123 use channel="durov", message_id=123."""
    try:
        async with _scraper() as s:
            msg = await s.get_message(channel, message_id)
        return _compact(msg) if msg else {"error": f"Message {message_id} not found in {channel}"}
    except (ScraperError, ValueError) as exc:
        return _error(exc)


@mcp.tool()
async def get_new_messages(channel: str, after_id: int, limit: int = 100) -> Dict[str, Any]:
    """Get only posts newer than ``after_id`` — use the highest id you saw before to follow a channel."""
    try:
        async with _scraper() as s:
            msgs = await s.get_messages(channel, _limit(limit), min_id=after_id, max_pages=20)
        return {"channel": channel, "count": len(msgs), "latest_id": max([m.id for m in msgs] or [after_id]),
                "messages": [_compact(m) for m in msgs]}
    except (ScraperError, ValueError) as exc:
        return _error(exc)


@mcp.tool()
async def analyze_channel(channel: str, limit: int = 200) -> Dict[str, Any]:
    """Statistics for a channel's recent posts: views, top posts, posting frequency and hours, hashtags,
    frequent words, media mix, reactions and a rough sentiment score. Also includes channel info."""
    try:
        async with _scraper() as s:
            info = await s.channel_info(channel)
            msgs = await s.get_messages(channel, _limit(limit))
        stats = summarize(msgs)
        stats.pop("posts_by_day", None)
        return {"channel": info.to_dict(), "stats": stats}
    except (ScraperError, ValueError) as exc:
        return _error(exc)


@mcp.tool()
async def compare_channels(channels: List[str], limit: int = 100) -> Dict[str, Any]:
    """Compare several public channels side by side (subscribers, activity, average views, sentiment)."""
    out: Dict[str, Any] = {}
    async with _scraper() as s:
        results = await s.scrape_many(channels[:10], _limit(limit))
        for ch, res in results.items():
            if isinstance(res, Exception):
                out[ch] = {"error": str(res)}
                continue
            try:
                info = await s.channel_info(ch)
            except ScraperError as exc:
                out[ch] = {"error": str(exc)}
                continue
            st = summarize(res)
            out[ch] = {
                "title": info.title, "subscribers": info.subscribers, "posts_analyzed": st["count"],
                "posts_per_day": st.get("posts_per_day"), "avg_views": st.get("avg_views"),
                "engagement_rate": round(st["avg_views"] / info.subscribers, 3)
                if st.get("avg_views") and info.subscribers else None,
                "with_media": st.get("with_media"), "sentiment": st.get("sentiment", {}).get("average"),
                "top_hashtags": st.get("top_hashtags", [])[:5],
            }
    return out


@mcp.tool()
async def export_messages(channel: str, path: str, limit: int = 100) -> Dict[str, Any]:
    """Save a channel's posts to a local file. Format from the extension: .json .jsonl .csv .xlsx .db .md"""
    try:
        async with _scraper() as s:
            msgs = await s.get_messages(channel, _limit(limit))
        saved = export(msgs, os.path.expanduser(path))
        return {"saved": str(saved.resolve()), "count": len(msgs)}
    except (ScraperError, ValueError, ImportError, OSError) as exc:
        return _error(exc)


@mcp.resource("telegram://channel/{channel}")
async def channel_resource(channel: str) -> str:
    """The 20 latest posts of a channel as Markdown."""
    from .exporters import to_markdown
    async with _scraper() as s:
        return to_markdown(await s.get_messages(channel, 20))


@mcp.prompt()
def summarize_channel(channel: str, days: int = 7) -> str:
    """Summarize what a Telegram channel posted recently."""
    return (f"Use get_channel_info and get_messages (since = {days} days ago) for the Telegram channel "
            f"'{channel}'. Summarize the main topics, the most viewed posts (with links), notable announcements, "
            f"and the overall tone. Answer in the user's language.")


@mcp.prompt()
def track_topic(channels: str, topic: str) -> str:
    """Find what several channels say about a topic."""
    return (f"For each of these Telegram channels: {channels} — call search_messages with query '{topic}'. "
            f"Compare what each channel says about '{topic}', cite post links, and note dates.")


def main(transport: str = "stdio") -> None:
    mcp.run(transport=transport)


if __name__ == "__main__":
    main()
