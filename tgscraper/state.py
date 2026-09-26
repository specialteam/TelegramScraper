"""Remember the last scraped message per channel so later runs only fetch new posts."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, Optional, Union

DEFAULT_STATE_FILE = Path(os.environ.get("TGSCRAPER_STATE", Path.home() / ".tgscraper" / "state.json"))


class State:
    def __init__(self, path: Union[str, Path, None] = None) -> None:
        self.path = Path(path) if path else DEFAULT_STATE_FILE
        self._data: Dict[str, int] = {}
        if self.path.exists():
            try:
                self._data = {k: int(v) for k, v in json.loads(self.path.read_text()).items()}
            except (ValueError, OSError):
                self._data = {}

    def last_id(self, channel: str) -> Optional[int]:
        return self._data.get(channel.lower())

    def update(self, channel: str, message_id: int) -> None:
        key = channel.lower()
        if message_id > self._data.get(key, 0):
            self._data[key] = message_id

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._data, indent=2, sort_keys=True))

    def reset(self, channel: Optional[str] = None) -> None:
        if channel:
            self._data.pop(channel.lower(), None)
        else:
            self._data.clear()
