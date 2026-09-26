"""Data models returned by the scraper."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class Media:
    """A photo, video, document, voice note, etc. attached to a message."""

    type: str  # photo | video | round_video | document | voice | sticker | link_preview
    url: Optional[str] = None
    thumbnail: Optional[str] = None
    duration: Optional[str] = None
    title: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Message:
    """One post of a public Telegram channel."""

    id: int
    channel: str
    url: str
    date: Optional[datetime] = None
    text: str = ""
    html: str = ""
    views: Optional[int] = None
    author: Optional[str] = None
    edited: bool = False
    forwarded_from: Optional[str] = None
    reply_to: Optional[int] = None
    media: List[Media] = field(default_factory=list)
    reactions: Dict[str, int] = field(default_factory=dict)
    hashtags: List[str] = field(default_factory=list)
    mentions: List[str] = field(default_factory=list)
    links: List[str] = field(default_factory=list)

    @property
    def has_media(self) -> bool:
        return bool(self.media)

    @property
    def media_types(self) -> List[str]:
        return [m.type for m in self.media]

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["date"] = self.date.isoformat() if self.date else None
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        data = dict(data)
        if isinstance(data.get("date"), str) and data["date"]:
            data["date"] = datetime.fromisoformat(data["date"])
        data["media"] = [m if isinstance(m, Media) else Media(**m) for m in data.get("media") or []]
        known = cls.__dataclass_fields__.keys()
        return cls(**{k: v for k, v in data.items() if k in known})

    def __str__(self) -> str:
        return self.text


@dataclass
class Channel:
    """Public information about a channel."""

    username: str
    url: str
    title: Optional[str] = None
    description: Optional[str] = None
    photo: Optional[str] = None
    subscribers: Optional[int] = None
    counters: Dict[str, int] = field(default_factory=dict)  # subscribers, photos, videos, links, files...
    verified: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
