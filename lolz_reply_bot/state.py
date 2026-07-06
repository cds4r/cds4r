"""Persistent state so the bot does not reply to the same thread twice."""

from __future__ import annotations

import json
import logging
import os
from typing import Dict, List, Set

logger = logging.getLogger(__name__)


class StateStore:
    """Tracks answered threads and created post ids, keyed by forum id."""

    def __init__(self, path: str):
        self.path = path
        self._replied: Dict[str, Set[int]] = {}
        # forum_id -> list of {"thread_id", "post_id"} created by the bot.
        self._posts: Dict[str, List[dict]] = {}
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
            self._posts = {
                str(forum): list(posts)
                for forum, posts in raw.get("posts", {}).items()
            }
        except (OSError, ValueError) as exc:
            logger.warning("Could not read state file %s: %s", self.path, exc)

    def has_replied(self, forum_id: int, thread_id: int) -> bool:
        return thread_id in self._replied.get(str(forum_id), set())

    def mark_replied(self, forum_id: int, thread_id: int, post_id=None) -> None:
        self._replied.setdefault(str(forum_id), set()).add(thread_id)
        if post_id is not None:
            self._posts.setdefault(str(forum_id), []).append(
                {"thread_id": thread_id, "post_id": post_id}
            )

    def created_posts(self, forum_id=None) -> List[dict]:
        """Return recorded posts, optionally filtered to a single forum."""
        if forum_id is not None:
            return list(self._posts.get(str(forum_id), []))
        result: List[dict] = []
        for posts in self._posts.values():
            result.extend(posts)
        return result

    def forget_post(self, post_id: int) -> None:
        for posts in self._posts.values():
            posts[:] = [p for p in posts if p.get("post_id") != post_id]

    def save(self) -> None:
        if not self.path:
            return
        data = {
            "replied": {
                forum: sorted(threads) for forum, threads in self._replied.items()
            },
            "posts": {forum: posts for forum, posts in self._posts.items() if posts},
        }
        tmp = f"{self.path}.tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as handle:
                json.dump(data, handle, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)
        except OSError as exc:
            logger.warning("Could not write state file %s: %s", self.path, exc)
