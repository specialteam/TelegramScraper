"""Save / load messages as JSON, JSON Lines, CSV, Excel, SQLite or Markdown."""
from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Union

from .models import Message

FORMATS = ("json", "jsonl", "csv", "xlsx", "sqlite", "md")
_EXT = {
    ".json": "json", ".jsonl": "jsonl", ".ndjson": "jsonl", ".csv": "csv", ".xlsx": "xlsx",
    ".db": "sqlite", ".sqlite": "sqlite", ".sqlite3": "sqlite", ".md": "md",
}
FLAT_COLUMNS = [
    "channel", "id", "url", "date", "text", "views", "author", "edited", "forwarded_from", "reply_to",
    "media_types", "media_urls", "reactions", "reactions_total", "hashtags", "mentions", "links",
]
_SQL_COLUMNS = {
    "channel": "TEXT", "id": "INTEGER", "url": "TEXT", "date": "TEXT", "text": "TEXT", "html": "TEXT",
    "views": "INTEGER", "author": "TEXT", "edited": "INTEGER", "forwarded_from": "TEXT", "reply_to": "INTEGER",
    "media": "TEXT", "reactions": "TEXT", "hashtags": "TEXT", "mentions": "TEXT", "links": "TEXT",
}


def detect_format(path: Union[str, Path], fmt: Optional[str] = None) -> str:
    if fmt:
        fmt = fmt.lower()
        if fmt not in FORMATS:
            raise ValueError(f"Unknown format {fmt!r}. Choose one of: {', '.join(FORMATS)}")
        return fmt
    ext = Path(path).suffix.lower()
    if ext not in _EXT:
        raise ValueError(f"Cannot guess format from {str(path)!r}; use one of {', '.join(_EXT)} or pass format=")
    return _EXT[ext]


def flatten(msg: Message) -> Dict[str, Any]:
    """One flat row per message, friendly for CSV / Excel / pandas."""
    return {
        "channel": msg.channel,
        "id": msg.id,
        "url": msg.url,
        "date": msg.date.isoformat() if msg.date else "",
        "text": msg.text,
        "views": msg.views,
        "author": msg.author or "",
        "edited": msg.edited,
        "forwarded_from": msg.forwarded_from or "",
        "reply_to": msg.reply_to,
        "media_types": ",".join(msg.media_types),
        "media_urls": " ".join(m.url for m in msg.media if m.url),
        "reactions": json.dumps(msg.reactions, ensure_ascii=False) if msg.reactions else "",
        "reactions_total": sum(msg.reactions.values()),
        "hashtags": " ".join("#" + h for h in msg.hashtags),
        "mentions": " ".join("@" + m for m in msg.mentions),
        "links": " ".join(msg.links),
    }


def to_json(messages: Iterable[Message], indent: Optional[int] = 2) -> str:
    return json.dumps([m.to_dict() for m in messages], ensure_ascii=False, indent=indent)


def to_markdown(messages: Iterable[Message]) -> str:
    parts = []
    for m in messages:
        head = f"### [{m.channel}/{m.id}]({m.url})"
        meta = " · ".join(x for x in [
            m.date.strftime("%Y-%m-%d %H:%M") if m.date else "",
            f"👁 {m.views:,}" if m.views is not None else "",
            ("📎 " + ", ".join(m.media_types)) if m.media else "",
        ] if x)
        parts.append(f"{head}\n_{meta}_\n\n{m.text or '(no text)'}\n")
    return "\n---\n\n".join(parts)


def export(messages: Iterable[Message], path: Union[str, Path], format: Optional[str] = None) -> Path:
    """Write messages to ``path``; the format is guessed from the extension.

    SQLite exports are *upserts*, so running the same export repeatedly builds a growing archive.
    """
    path = Path(path)
    fmt = detect_format(path, format)
    messages = list(messages)
    if path.parent and not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)

    if fmt == "json":
        path.write_text(to_json(messages), encoding="utf-8")
    elif fmt == "jsonl":
        with path.open("w", encoding="utf-8") as fh:
            for m in messages:
                fh.write(json.dumps(m.to_dict(), ensure_ascii=False) + "\n")
    elif fmt == "csv":
        # utf-8-sig so Excel opens Persian/Arabic/emoji text correctly
        with path.open("w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=FLAT_COLUMNS)
            writer.writeheader()
            writer.writerows(flatten(m) for m in messages)
    elif fmt == "xlsx":
        try:
            from openpyxl import Workbook
        except ImportError as exc:  # pragma: no cover
            raise ImportError("Excel export needs openpyxl: pip install 'tgscraper[excel]'") from exc
        wb = Workbook()
        ws = wb.active
        ws.title = "messages"
        ws.append(FLAT_COLUMNS)
        for m in messages:
            ws.append([flatten(m)[c] for c in FLAT_COLUMNS])
        wb.save(path)
    elif fmt == "sqlite":
        _to_sqlite(messages, path)
    elif fmt == "md":
        path.write_text(to_markdown(messages), encoding="utf-8")
    return path


def _to_sqlite(messages: List[Message], path: Path) -> None:
    cols = list(_SQL_COLUMNS)
    with sqlite3.connect(path) as db:
        db.execute(
            "CREATE TABLE IF NOT EXISTS messages ("
            + ", ".join(f"{c} {t}" for c, t in _SQL_COLUMNS.items())
            + ", PRIMARY KEY (channel, id))"
        )
        db.execute("CREATE INDEX IF NOT EXISTS idx_messages_date ON messages(date)")
        rows = []
        for m in messages:
            d = m.to_dict()
            for key in ("media", "reactions", "hashtags", "mentions", "links"):
                d[key] = json.dumps(d[key], ensure_ascii=False)
            d["edited"] = int(m.edited)
            rows.append([d[c] for c in cols])
        db.executemany(
            f"INSERT OR REPLACE INTO messages ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})", rows
        )


def load(path: Union[str, Path], format: Optional[str] = None) -> List[Message]:
    """Load messages previously saved as json / jsonl / sqlite."""
    path = Path(path)
    fmt = detect_format(path, format)
    if fmt == "json":
        return [Message.from_dict(d) for d in json.loads(path.read_text(encoding="utf-8"))]
    if fmt == "jsonl":
        with path.open(encoding="utf-8") as fh:
            return [Message.from_dict(json.loads(line)) for line in fh if line.strip()]
    if fmt == "sqlite":
        with sqlite3.connect(path) as db:
            db.row_factory = sqlite3.Row
            out = []
            for row in db.execute("SELECT * FROM messages ORDER BY date DESC, id DESC"):
                d = dict(row)
                for key in ("media", "reactions", "hashtags", "mentions", "links"):
                    d[key] = json.loads(d[key]) if d[key] else ([] if key != "reactions" else {})
                d["edited"] = bool(d["edited"])
                out.append(Message.from_dict(d))
            return out
    raise ValueError(f"Loading {fmt} is not supported; use json, jsonl or sqlite")
