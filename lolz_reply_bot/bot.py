"""Core orchestration for the reply bot."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import List, Optional

from .api import ForumApiError, LolzForumClient
from .config import BotConfig
from .generator import ReplyGenerator, build_generator
from .state import StateStore

logger = logging.getLogger(__name__)


@dataclass
class ReplyResult:
    """Outcome of a single thread reply attempt."""

    forum_id: int
    thread_id: int
    thread_title: str
    reply_body: str
    posted: bool
    post_id: Optional[int] = None
    skipped_reason: Optional[str] = None
    error: Optional[str] = None


class ReplyBot:
    """Scans forum sections and leaves context-aware replies in their threads."""

    def __init__(
        self,
        config: BotConfig,
        client: Optional[LolzForumClient] = None,
        generator: Optional[ReplyGenerator] = None,
        state: Optional[StateStore] = None,
    ):
        config.validate()
        self.config = config
        self.client = client or LolzForumClient(
            token=config.token,
            base_url=config.base_url,
            request_delay=config.request_delay,
            timeout=config.timeout,
            proxy=config.proxy,
        )
        self.generator = generator or build_generator(config)
        self.state = state or StateStore(config.state_file)
        self._me_id: Optional[int] = None

    # -- helpers -----------------------------------------------------------
    def _current_user_id(self) -> Optional[int]:
        if self._me_id is not None or not self.config.token:
            return self._me_id
        try:
            me = self.client.get_me()
            self._me_id = me.get("user_id")
            logger.info("Authenticated as %s (id=%s)",
                        me.get("username", "?"), self._me_id)
        except ForumApiError as exc:
            logger.warning("Could not fetch current user: %s", exc)
        return self._me_id

    def _iter_threads(self, forum_id: int) -> List[dict]:
        threads: List[dict] = []
        for page in range(1, self.config.pages + 1):
            batch = self.client.list_threads(
                forum_id,
                page=page,
                limit=self.config.threads_per_forum,
                order=self.config.order,
            )
            if not batch:
                break
            threads.extend(batch)
            if len(threads) >= self.config.threads_per_forum * self.config.pages:
                break
        return threads

    def _should_skip(self, forum_id: int, thread: dict) -> Optional[str]:
        thread_id = thread.get("thread_id")
        if thread_id is None:
            return "missing thread_id"
        if self.config.max_thread_age_hours is not None:
            created = thread.get("thread_create_date")
            if created is not None:
                age_hours = (time.time() - float(created)) / 3600.0
                if age_hours > self.config.max_thread_age_hours:
                    return "older than window"
        if self.config.reply_once_per_thread and self.state.has_replied(forum_id, thread_id):
            return "already replied"
        if self.config.skip_own_threads:
            me = self._current_user_id()
            if me is not None and thread.get("creator_user_id") == me:
                return "own thread"
        if thread.get("thread_is_deleted") or thread.get("thread_is_closed"):
            return "closed/deleted thread"
        return None

    # -- main entry points -------------------------------------------------
    def run_once(self) -> List[ReplyResult]:
        results: List[ReplyResult] = []
        posted = 0
        for forum_id in self.config.forum_ids:
            logger.info("Scanning forum/section %s", forum_id)
            try:
                threads = self._iter_threads(forum_id)
            except ForumApiError as exc:
                logger.error("Failed to list threads in forum %s: %s", forum_id, exc)
                continue
            logger.info("Found %s thread(s) in forum %s", len(threads), forum_id)

            for thread in threads:
                if self.config.max_replies is not None and posted >= self.config.max_replies:
                    logger.info("Reached max_replies=%s, stopping", self.config.max_replies)
                    self.state.save()
                    return results

                result = self._handle_thread(forum_id, thread)
                results.append(result)
                if result.posted:
                    posted += 1

        self.state.save()
        return results

    def _handle_thread(self, forum_id: int, thread: dict) -> ReplyResult:
        thread_id = thread.get("thread_id")
        title = thread.get("thread_title", "")

        skip_reason = self._should_skip(forum_id, thread)
        reply_body = ""
        if skip_reason is None:
            reply_body = self.generator.generate(
                title, thread_body=thread.get("first_post", {}).get("post_body_plain_text"),
            )

        if skip_reason is not None:
            logger.info("Skipping thread %s (%s): %s", thread_id, title, skip_reason)
            return ReplyResult(forum_id, thread_id, title, reply_body, posted=False,
                               skipped_reason=skip_reason)

        if self.config.dry_run:
            logger.info("[dry-run] Would reply to #%s '%s':\n  -> %s",
                        thread_id, title, reply_body)
            return ReplyResult(forum_id, thread_id, title, reply_body, posted=False,
                               skipped_reason="dry-run")

        try:
            post = self.client.create_post(thread_id, reply_body)
            post_id = post.get("post_id")
            self.state.mark_replied(forum_id, thread_id, post_id=post_id)
            logger.info("Replied to thread #%s '%s' (post_id=%s)", thread_id, title, post_id)
            return ReplyResult(forum_id, thread_id, title, reply_body, posted=True,
                               post_id=post_id)
        except ForumApiError as exc:
            logger.error("Failed to reply to thread #%s: %s", thread_id, exc)
            return ReplyResult(forum_id, thread_id, title, reply_body, posted=False,
                               error=str(exc))

    def delete_posts(self, post_ids: List[int], reason: Optional[str] = None) -> int:
        """Delete the given post ids. Returns the number of posts deleted."""
        deleted = 0
        for post_id in post_ids:
            try:
                self.client.delete_post(post_id, reason=reason)
                self.state.forget_post(post_id)
                deleted += 1
                logger.info("Deleted post #%s", post_id)
            except ForumApiError as exc:
                logger.error("Failed to delete post #%s: %s", post_id, exc)
        self.state.save()
        return deleted

    def undo(self, reason: Optional[str] = None) -> int:
        """Delete every post recorded in the state file for the configured forums."""
        post_ids: List[int] = []
        for forum_id in self.config.forum_ids:
            post_ids.extend(
                p["post_id"] for p in self.state.created_posts(forum_id)
                if p.get("post_id") is not None
            )
        if not post_ids:
            logger.info("No recorded posts to delete for forums %s",
                        self.config.forum_ids)
            return 0
        logger.info("Deleting %s previously created post(s)", len(post_ids))
        return self.delete_posts(post_ids, reason=reason)

    def run(self) -> List[ReplyResult]:
        """Run once, or loop forever when ``config.loop`` is set."""
        if not self.config.loop:
            return self.run_once()

        all_results: List[ReplyResult] = []
        while True:
            all_results = self.run_once()
            logger.info("Cycle complete; sleeping %ss", self.config.loop_interval)
            try:
                time.sleep(self.config.loop_interval)
            except KeyboardInterrupt:
                logger.info("Interrupted, stopping loop")
                break
        return all_results
