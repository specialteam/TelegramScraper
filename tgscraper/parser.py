"""HTML parsing for the public web preview of a channel (https://t.me/s/<channel>)."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from bs4 import BeautifulSoup, Tag

from .models import Channel, Media, Message

_CHANNEL_RE = re.compile(r"^(?:https?://)?(?:www\.)?(?:t\.me|telegram\.me)/(?:s/)?([A-Za-z0-9_]+)", re.I)
_BG_URL_RE = re.compile(r"url\(['\"]?([^'\")]+)['\"]?\)")
_HASHTAG_RE = re.compile(r"(?<!\w)#(\w+)", re.UNICODE)
_MENTION_RE = re.compile(r"(?<![\w@])@([A-Za-z0-9_]{4,32})")


def normalize_channel(channel: str) -> str:
    """Accept ``durov``, ``@durov``, ``t.me/durov``, ``https://t.me/s/durov`` ... and return ``durov``."""
    channel = channel.strip()
    match = _CHANNEL_RE.match(channel)
    if match:
        return match.group(1)
    channel = channel.lstrip("@").strip("/")
    if not re.fullmatch(r"[A-Za-z0-9_]+", channel):
        raise ValueError(f"Invalid channel name or URL: {channel!r}")
    return channel


def parse_count(value: Optional[str]) -> Optional[int]:
    """Convert Telegram counters like ``1.2K``, ``3,4M`` or ``12 345`` to ints."""
    if not value:
        return None
    value = value.strip().replace(" ", "").replace(" ", "")
    multiplier = 1
    if value[-1:].upper() in ("K", "M", "B"):
        multiplier = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}[value[-1].upper()]
        value = value[:-1].replace(",", ".")
    else:
        value = value.replace(",", "")
    try:
        return int(round(float(value) * multiplier))
    except ValueError:
        return None


def _bg_url(tag: Tag) -> Optional[str]:
    match = _BG_URL_RE.search(tag.get("style", "") or "")
    return match.group(1) if match else None


def _text_of(tag: Tag) -> str:
    for br in tag.find_all("br"):
        br.replace_with("\n")
    return tag.get_text().strip()


def _own(root: Tag, selector: str) -> List[Tag]:
    """Elements matching ``selector`` that are not inside a quoted reply / link preview."""
    out = []
    for el in root.select(selector):
        if el.find_parent(class_=["tgme_widget_message_reply", "link_preview_wrap"]) is not None:
            continue
        out.append(el)
    return out


def _parse_media(node: Tag) -> List[Media]:
    media: List[Media] = []
    for el in _own(node, "a.tgme_widget_message_photo_wrap"):
        media.append(Media("photo", url=_bg_url(el), thumbnail=_bg_url(el)))
    for el in _own(node, ".tgme_widget_message_video_player"):
        video = el.select_one("video")
        thumb = el.select_one(".tgme_widget_message_video_thumb")
        duration = el.select_one(".message_video_duration")
        kind = "round_video" if "tgme_widget_message_roundvideo_player" in (el.get("class") or []) else "video"
        media.append(Media(
            kind,
            url=video.get("src") if video else None,
            thumbnail=_bg_url(thumb) if thumb else None,
            duration=duration.get_text(strip=True) if duration else None,
        ))
    for el in _own(node, "audio.tgme_widget_message_voice"):
        duration = node.select_one(".tgme_widget_message_voice_duration")
        media.append(Media("voice", url=el.get("src"), duration=duration.get_text(strip=True) if duration else None))
    for el in _own(node, ".tgme_widget_message_document_wrap"):
        title = el.select_one(".tgme_widget_message_document_title")
        kind = "audio" if el.select_one(".audio") else "document"
        media.append(Media(kind, url=el.get("href"), title=title.get_text(strip=True) if title else None))
    for el in _own(node, ".tgme_widget_message_sticker_wrap"):
        img = el.select_one("img, video")
        media.append(Media("sticker", url=img.get("src") if img else _bg_url(el)))
    for el in node.select("a.tgme_widget_message_link_preview"):
        title = el.select_one(".link_preview_title") or el.select_one(".link_preview_site_name")
        image = el.select_one(".link_preview_image, .link_preview_right_image")
        media.append(Media("link_preview", url=el.get("href"),
                           thumbnail=_bg_url(image) if image else None,
                           title=title.get_text(strip=True) if title else None))
    return media


def _parse_reactions(node: Tag) -> Dict[str, int]:
    reactions: Dict[str, int] = {}
    for el in node.select(".tgme_reaction"):
        emoji_el = el.select_one("i.emoji b") or el.select_one("i.emoji") or el.select_one("tg-emoji")
        emoji = emoji_el.get_text(strip=True) if emoji_el else ""
        if emoji_el is not None:
            emoji_el.extract()
        count = parse_count(el.get_text(strip=True))
        if not emoji:
            emoji = el.get("data-emoji") or "custom"
        reactions[emoji] = reactions.get(emoji, 0) + (count or 0)
    return reactions


def parse_message(node: Tag, channel: str) -> Optional[Message]:
    post = node.get("data-post") or ""
    if "/" not in post:
        return None
    post_channel, _, post_id = post.rpartition("/")
    try:
        msg_id = int(post_id)
    except ValueError:
        return None

    text_nodes = _own(node, ".tgme_widget_message_text")
    text_el = text_nodes[0] if text_nodes else None
    html = text_el.decode_contents() if text_el else ""
    links: List[str] = []
    if text_el:
        for a in text_el.find_all("a", href=True):
            href = a["href"]
            if not href.startswith("?q=") and href not in links:
                links.append(href)
    text = _text_of(text_el) if text_el else ""

    date = None
    time_el = node.select_one(".tgme_widget_message_date time[datetime]") or node.select_one("time[datetime]")
    if time_el:
        try:
            date = datetime.fromisoformat(time_el["datetime"])
        except ValueError:
            date = None

    views_el = node.select_one(".tgme_widget_message_views")
    author_el = node.select_one(".tgme_widget_message_from_author")
    meta_el = node.select_one(".tgme_widget_message_meta")
    fwd_el = node.select_one(".tgme_widget_message_forwarded_from_name")
    reply_el = node.select_one("a.tgme_widget_message_reply")
    reply_to = None
    if reply_el and reply_el.get("href"):
        match = re.search(r"/(\d+)(?:\?|$)", reply_el["href"])
        reply_to = int(match.group(1)) if match else None

    return Message(
        id=msg_id,
        channel=post_channel or channel,
        url=f"https://t.me/{post_channel or channel}/{msg_id}",
        date=date,
        text=text,
        html=html,
        views=parse_count(views_el.get_text()) if views_el else None,
        author=author_el.get_text(strip=True) if author_el else None,
        edited=bool(meta_el and "edited" in meta_el.get_text().lower()),
        forwarded_from=fwd_el.get_text(strip=True) if fwd_el else None,
        reply_to=reply_to,
        media=_parse_media(node),
        reactions=_parse_reactions(node),
        hashtags=list(dict.fromkeys(_HASHTAG_RE.findall(text))),
        mentions=list(dict.fromkeys(_MENTION_RE.findall(text))),
        links=links,
    )


def parse_channel_info(soup: BeautifulSoup, channel: str) -> Channel:
    info = Channel(username=channel, url=f"https://t.me/{channel}")
    title = soup.select_one(".tgme_channel_info_header_title")
    if title:
        info.title = title.get_text(strip=True)
        info.verified = title.select_one(".verified-icon") is not None
    desc = soup.select_one(".tgme_channel_info_description")
    if desc:
        info.description = _text_of(desc)
    photo = soup.select_one(".tgme_channel_info_header .tgme_page_photo_image img")
    if photo:
        info.photo = photo.get("src")
    for counter in soup.select(".tgme_channel_info_counter"):
        value = counter.select_one(".counter_value")
        kind = counter.select_one(".counter_type")
        if value and kind:
            info.counters[kind.get_text(strip=True).lower()] = parse_count(value.get_text()) or 0
    for key in ("subscribers", "subscriber", "members", "member"):
        if key in info.counters:
            info.subscribers = info.counters[key]
            break
    return info


def parse_page(html: str, channel: str) -> Tuple[List[Message], Channel, Optional[int]]:
    """Parse one ``t.me/s/<channel>`` page.

    Returns ``(messages oldest->newest, channel info, before_id for the next older page or None)``.
    """
    soup = BeautifulSoup(html, "html.parser")
    messages = []
    for node in soup.select(".tgme_widget_message[data-post]"):
        msg = parse_message(node, channel)
        if msg:
            messages.append(msg)
    before = None
    more = soup.select_one("a.tme_messages_more[data-before]")
    if more:
        try:
            before = int(more["data-before"])
        except (KeyError, ValueError):
            before = None
    if before is None and more is not None and more.get("href"):
        match = re.search(r"before=(\d+)", more["href"])
        before = int(match.group(1)) if match else None
    return messages, parse_channel_info(soup, channel), before
