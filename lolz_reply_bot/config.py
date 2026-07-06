"""Configuration handling for lolz_reply_bot."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Optional

DEFAULT_BASE_URL = "https://prod-api.lolz.live"
DEFAULT_LLM_BASE_URL = "https://api.openai.com/v1"
DEFAULT_LLM_MODEL = "gpt-4o-mini"
DEFAULT_REQUEST_DELAY = 3.0
DEFAULT_REPLY_LANGUAGE = "ru"


def _parse_forum_ids(raw: Optional[str]) -> List[int]:
    """Parse a comma/space separated list of forum ids into a list of ints."""
    if not raw:
        return []
    ids: List[int] = []
    for chunk in raw.replace(",", " ").split():
        chunk = chunk.strip()
        if not chunk:
            continue
        ids.append(int(chunk))
    return ids


@dataclass
class BotConfig:
    """Runtime configuration for the reply bot.

    Values are usually assembled from environment variables and CLI arguments
    (see ``cli.build_config``). ``forum_ids`` selects the section(s) the bot
    will operate in.
    """

    token: Optional[str] = None
    forum_ids: List[int] = field(default_factory=list)
    base_url: str = DEFAULT_BASE_URL
    request_delay: float = DEFAULT_REQUEST_DELAY

    # How many threads to scan per forum and how many replies to post per run.
    threads_per_forum: int = 20
    pages: int = 1
    order: str = "thread_create_date_reverse"
    max_replies: Optional[int] = None

    # Only reply to threads created within this many hours (None = no limit).
    max_thread_age_hours: Optional[float] = None

    # Behaviour toggles.
    dry_run: bool = False
    skip_own_threads: bool = True
    reply_once_per_thread: bool = True
    state_file: str = ".lolz_reply_bot_state.json"

    # Loop mode.
    loop: bool = False
    loop_interval: float = 300.0

    # Reply generation.
    reply_language: str = DEFAULT_REPLY_LANGUAGE
    llm_api_key: Optional[str] = None
    llm_base_url: str = DEFAULT_LLM_BASE_URL
    llm_model: str = DEFAULT_LLM_MODEL
    llm_temperature: float = 0.8

    # Networking.
    proxy: Optional[str] = None
    timeout: float = 30.0

    def validate(self) -> None:
        """Raise ``ValueError`` if the configuration is not usable."""
        if not self.forum_ids:
            raise ValueError(
                "No forum/section id provided. Use --forum-id or set LOLZ_FORUM_ID."
            )
        if not self.dry_run and not self.token:
            raise ValueError(
                "A lolz.live API token is required to post. "
                "Set LOLZ_TOKEN (or use --dry-run to preview without posting)."
            )
        if self.request_delay < 0:
            raise ValueError("request_delay must be >= 0")

    @property
    def use_llm(self) -> bool:
        return bool(self.llm_api_key)

    @classmethod
    def from_env(cls, env: Optional[dict] = None) -> "BotConfig":
        """Build a config from environment variables (dotenv-friendly)."""
        env = os.environ if env is None else env

        def _get(name: str) -> Optional[str]:
            value = env.get(name)
            if value is None:
                return None
            value = value.strip()
            return value or None

        cfg = cls()
        cfg.token = _get("LOLZ_TOKEN")
        cfg.forum_ids = _parse_forum_ids(_get("LOLZ_FORUM_ID"))
        cfg.base_url = _get("LOLZ_BASE_URL") or DEFAULT_BASE_URL

        delay = _get("LOLZ_REQUEST_DELAY")
        if delay is not None:
            cfg.request_delay = float(delay)

        max_age = _get("LOLZ_MAX_THREAD_AGE_HOURS")
        if max_age is not None:
            cfg.max_thread_age_hours = float(max_age)

        cfg.reply_language = _get("REPLY_LANGUAGE") or DEFAULT_REPLY_LANGUAGE
        cfg.llm_api_key = _get("LLM_API_KEY")
        cfg.llm_base_url = _get("LLM_BASE_URL") or DEFAULT_LLM_BASE_URL
        cfg.llm_model = _get("LLM_MODEL") or DEFAULT_LLM_MODEL

        temperature = _get("LLM_TEMPERATURE")
        if temperature is not None:
            cfg.llm_temperature = float(temperature)

        cfg.proxy = _get("LOLZ_PROXY")
        return cfg
