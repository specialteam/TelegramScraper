"""Client-side message filters."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timezone
from typing import Iterable, List, Optional, Pattern, Sequence, Union

from .models import Message

DateLike = Union[str, date, datetime, None]


def to_datetime(value: DateLike, end_of_day: bool = False) -> Optional[datetime]:
    """Parse ``"2026-01-31"``, ``"2026-01-31T10:00"``, ``date`` or ``datetime`` into an aware UTC datetime."""
    if value is None or value == "":
        return None
    if isinstance(value, str):
        value = value.strip()
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if len(value) == 10 and end_of_day:
            parsed = datetime.combine(parsed.date(), time.max)
        value = parsed
    elif not isinstance(value, datetime):
        value = datetime.combine(value, time.max if end_of_day else time.min)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value


@dataclass
class MessageFilter:
    """Filters applied to every scraped message. All conditions must match."""

    since: DateLike = None
    until: DateLike = None
    keywords: Sequence[str] = field(default_factory=list)  # any of them, case-insensitive
    regex: Optional[Union[str, Pattern]] = None
    media_only: bool = False
    media_types: Sequence[str] = field(default_factory=list)  # photo, video, document, voice, ...
    min_views: Optional[int] = None
    hashtag: Optional[str] = None

    def __post_init__(self) -> None:
        self.since = to_datetime(self.since)
        self.until = to_datetime(self.until, end_of_day=True)
        if isinstance(self.keywords, str):
            self.keywords = [self.keywords]
        self.keywords = [k.lower() for k in self.keywords if k]
        if isinstance(self.media_types, str):
            self.media_types = [self.media_types]
        if isinstance(self.regex, str) and self.regex:
            self.regex = re.compile(self.regex, re.IGNORECASE)
        if self.hashtag:
            self.hashtag = self.hashtag.lstrip("#").lower()

    def matches(self, msg: Message) -> bool:
        date_ = msg.date
        if date_ is not None and date_.tzinfo is None:
            date_ = date_.replace(tzinfo=timezone.utc)
        if self.since and date_ and date_ < self.since:
            return False
        if self.until and date_ and date_ > self.until:
            return False
        if self.keywords and not any(k in msg.text.lower() for k in self.keywords):
            return False
        if self.regex and not self.regex.search(msg.text):
            return False
        if self.media_only and not msg.media:
            return False
        if self.media_types and not set(self.media_types) & set(msg.media_types):
            return False
        if self.min_views is not None and (msg.views or 0) < self.min_views:
            return False
        if self.hashtag and self.hashtag not in (h.lower() for h in msg.hashtags):
            return False
        return True

    def apply(self, messages: Iterable[Message]) -> List[Message]:
        return [m for m in messages if self.matches(m)]
