"""Persistent state so the bot does not reply to the same thread twice."""

from __future__ import annotations

import json
import logging
import os
from typing import Dict, Set

logger = logging.getLogger(__name__)


class StateStore:
    """Tracks which threads have already been answered, keyed by forum id."""

    def __init__(self, path: str):
        self.path = path
        self._replied: Dict[str, Set[int]] = {}
        self._load()

    def _load(self) -> None:
        if not self.path or not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                raw = json.load(handle)
            self._replied = {
                str(forum): set(int(t) for t in threads)
                for forum, threads in raw.get("replied", {}).items()
            }
        except (OSError, ValueError) as exc:
            logger.warning("Could not read state file %s: %s", self.path, exc)

    def has_replied(self, forum_id: int, thread_id: int) -> bool:
        return thread_id in self._replied.get(str(forum_id), set())

    def mark_replied(self, forum_id: int, thread_id: int) -> None:
        self._replied.setdefault(str(forum_id), set()).add(thread_id)

    def save(self) -> None:
        if not self.path:
            return
        data = {
            "replied": {
                forum: sorted(threads) for forum, threads in self._replied.items()
            }
        }
        tmp = f"{self.path}.tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as handle:
                json.dump(data, handle, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)
        except OSError as exc:
            logger.warning("Could not write state file %s: %s", self.path, exc)
