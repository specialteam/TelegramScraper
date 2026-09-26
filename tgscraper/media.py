"""Download photos / videos / voice notes attached to messages."""
from __future__ import annotations

import logging
import mimetypes
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Union
from urllib.parse import urlparse

import httpx

from .client import DEFAULT_HEADERS
from .models import Message

log = logging.getLogger("tgscraper")

DOWNLOADABLE = ("photo", "video", "round_video", "voice", "sticker")


def download_media(
    messages: Iterable[Message],
    folder: Union[str, Path] = "media",
    types: Optional[Sequence[str]] = None,
    proxy: Optional[str] = None,
    overwrite: bool = False,
) -> List[Path]:
    """Download media files to ``folder`` as ``<channel>_<id>_<n>.<ext>``. Returns the saved paths.

    Documents are not downloadable from the public preview (they link back to the Telegram app).
    """
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    wanted = set(types or DOWNLOADABLE) & set(DOWNLOADABLE)
    saved: List[Path] = []
    with httpx.Client(proxy=proxy, headers=DEFAULT_HEADERS, timeout=60, follow_redirects=True) as client:
        for msg in messages:
            for n, media in enumerate(msg.media, 1):
                if media.type not in wanted or not media.url or not media.url.startswith("http"):
                    continue
                ext = Path(urlparse(media.url).path).suffix
                stem = folder / f"{msg.channel}_{msg.id}_{n}"
                existing = list(folder.glob(stem.name + ".*"))
                if existing and not overwrite:
                    saved.append(existing[0])
                    continue
                try:
                    response = client.get(media.url)
                    response.raise_for_status()
                except httpx.HTTPError as exc:
                    log.warning("Could not download %s: %s", media.url, exc)
                    continue
                if not ext:
                    content_type = response.headers.get("content-type", "").split(";")[0]
                    ext = mimetypes.guess_extension(content_type) or ".bin"
                target = stem.with_suffix(ext)
                target.write_bytes(response.content)
                saved.append(target)
    return saved
