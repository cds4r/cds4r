"""Command line interface for lolz_reply_bot."""

from __future__ import annotations

import argparse
import logging
import sys
from typing import List, Optional

from .bot import ReplyBot
from .config import BotConfig, _parse_forum_ids

try:  # optional dependency, only used to load a local .env file
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - dotenv is optional
    load_dotenv = None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lolz_reply_bot",
        description=(
            "Bot for lolz.live: leaves context-aware replies in the threads of a "
            "given forum section, based on each thread title."
        ),
    )
    parser.add_argument(
        "-f", "--forum-id", dest="forum_id",
        help="Forum/section id to work in. Accepts several ids (comma separated).",
    )
    parser.add_argument("--token", help="lolz.live API token (overrides LOLZ_TOKEN).")
    parser.add_argument("--base-url", help="API base URL.")
    parser.add_argument("--request-delay", type=float,
                        help="Seconds between API requests (default 3).")
    parser.add_argument("--threads-per-forum", type=int, default=20,
                        help="How many threads to scan per forum (default 20).")
    parser.add_argument("--pages", type=int, default=1,
                        help="Number of thread pages to scan (default 1).")
    parser.add_argument("--order", default="thread_create_date_reverse",
                        help="Thread ordering (default newest first).")
    parser.add_argument("--max-replies", type=int,
                        help="Maximum number of replies to post in this run.")
    parser.add_argument("--max-age-hours", type=float,
                        help="Only reply to threads created within the last N hours.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Generate and print replies without posting them.")
    parser.add_argument("--reply-to-own", action="store_true",
                        help="Also reply to threads created by the bot account.")
    parser.add_argument("--allow-duplicates", action="store_true",
                        help="Do not skip threads already answered in a past run.")
    parser.add_argument("--state-file", default=".lolz_reply_bot_state.json",
                        help="Path to the state file tracking answered threads.")
    parser.add_argument("--reply-language", help="Reply language: 'ru' or 'en'.")
    parser.add_argument("--loop", action="store_true",
                        help="Keep running, re-scanning periodically.")
    parser.add_argument("--loop-interval", type=float, default=300.0,
                        help="Seconds to wait between cycles in --loop mode.")
    parser.add_argument("--undo", action="store_true",
                        help="Delete all posts this bot created (from the state file) "
                             "in the given forum(s), then exit.")
    parser.add_argument("--delete-posts",
                        help="Delete the given post id(s) (comma separated), then exit.")
    parser.add_argument("--delete-reason",
                        help="Optional reason to send when deleting posts.")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Enable debug logging.")
    return parser


def build_config(args: argparse.Namespace) -> BotConfig:
    if load_dotenv is not None:
        load_dotenv()
    config = BotConfig.from_env()

    if args.forum_id:
        config.forum_ids = _parse_forum_ids(args.forum_id)
    if args.token:
        config.token = args.token
    if args.base_url:
        config.base_url = args.base_url
    if args.request_delay is not None:
        config.request_delay = args.request_delay
    if args.reply_language:
        config.reply_language = args.reply_language

    config.threads_per_forum = args.threads_per_forum
    config.pages = args.pages
    config.order = args.order
    config.max_replies = args.max_replies
    if args.max_age_hours is not None:
        config.max_thread_age_hours = args.max_age_hours
    config.dry_run = args.dry_run
    config.skip_own_threads = not args.reply_to_own
    config.reply_once_per_thread = not args.allow_duplicates
    config.state_file = args.state_file
    config.loop = args.loop
    config.loop_interval = args.loop_interval
    return config


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    try:
        config = build_config(args)
        bot = ReplyBot(config)
    except ValueError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    # Deletion modes short-circuit the normal reply flow.
    if args.delete_posts:
        ids = [int(x) for x in _parse_forum_ids(args.delete_posts)]
        deleted = bot.delete_posts(ids, reason=args.delete_reason)
        print(f"\nDeleted {deleted}/{len(ids)} post(s).")
        return 0
    if args.undo:
        deleted = bot.undo(reason=args.delete_reason)
        print(f"\nDeleted {deleted} previously created post(s).")
        return 0

    mode = "DRY-RUN" if config.dry_run else "LIVE"
    llm = "LLM" if config.use_llm else "template"
    logging.getLogger(__name__).info(
        "Starting lolz_reply_bot [%s, %s replies] forums=%s",
        mode, llm, config.forum_ids,
    )

    results = bot.run()

    posted = sum(1 for r in results if r.posted)
    previewed = sum(1 for r in results if r.skipped_reason == "dry-run")
    skipped = sum(1 for r in results if r.skipped_reason and r.skipped_reason != "dry-run")
    errors = sum(1 for r in results if r.error)
    print(
        f"\nDone. processed={len(results)} posted={posted} "
        f"previewed={previewed} skipped={skipped} errors={errors}"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
