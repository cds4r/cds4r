"""lolz_reply_bot - a bot that leaves context-aware replies in lolz.live threads.

The bot reads the threads of a given forum section (by its id), builds a
meaningful reply from each thread title and posts it back to the thread using
the lolz.live (Zelenka) Forum API.
"""

from .api import ForumApiError, LolzForumClient
from .bot import ReplyBot, ReplyResult
from .config import BotConfig
from .generator import (
    OpenAIReplyGenerator,
    ReplyGenerator,
    TemplateReplyGenerator,
    build_generator,
)

__all__ = [
    "BotConfig",
    "ForumApiError",
    "LolzForumClient",
    "OpenAIReplyGenerator",
    "ReplyBot",
    "ReplyResult",
    "ReplyGenerator",
    "TemplateReplyGenerator",
    "build_generator",
]

__version__ = "0.1.0"
