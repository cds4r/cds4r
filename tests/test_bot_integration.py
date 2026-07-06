from lolz_reply_bot.bot import ReplyBot
from lolz_reply_bot.config import BotConfig

from .mock_server import MockLolzServer, make_threads


def _config(base_url, forum_ids, tmp_path, **overrides):
    cfg = BotConfig(
        token="valid-token",
        forum_ids=forum_ids,
        base_url=base_url,
        request_delay=0,  # no throttling in tests
        state_file=str(tmp_path / "state.json"),
        skip_own_threads=False,
        reply_language="ru",
    )
    for key, value in overrides.items():
        setattr(cfg, key, value)
    return cfg


def test_bot_posts_replies_end_to_end(tmp_path):
    titles = ["Как настроить прокси?", "Продаю аккаунт", "How to secure my server?"]
    threads = {50: make_threads(50, titles)}
    with MockLolzServer(threads) as server:
        cfg = _config(server.base_url, [50], tmp_path)
        bot = ReplyBot(cfg)
        results = bot.run_once()

        assert len(results) == 3
        assert all(r.posted for r in results)
        assert len(server.created_posts) == 3
        # every created post has a non-empty body
        for post in server.created_posts:
            assert post["post_body"].strip()


def test_bot_respects_state_and_no_double_reply(tmp_path):
    threads = {50: make_threads(50, ["Вопрос про безопасность?"])}
    with MockLolzServer(threads) as server:
        cfg = _config(server.base_url, [50], tmp_path)
        ReplyBot(cfg).run_once()
        assert len(server.created_posts) == 1

        # Second run with a fresh bot (loads persisted state) posts nothing new.
        ReplyBot(_config(server.base_url, [50], tmp_path)).run_once()
        assert len(server.created_posts) == 1


def test_bot_max_replies(tmp_path):
    threads = {50: make_threads(50, [f"Тема номер {i}" for i in range(5)])}
    with MockLolzServer(threads) as server:
        cfg = _config(server.base_url, [50], tmp_path, max_replies=2)
        results = ReplyBot(cfg).run_once()
        assert sum(1 for r in results if r.posted) == 2
        assert len(server.created_posts) == 2


def test_bot_dry_run_posts_nothing(tmp_path):
    threads = {50: make_threads(50, ["Тестовая тема?"])}
    with MockLolzServer(threads) as server:
        cfg = _config(server.base_url, [50], tmp_path, dry_run=True)
        results = ReplyBot(cfg).run_once()
        assert len(server.created_posts) == 0
        assert results[0].skipped_reason == "dry-run"
        assert results[0].reply_body  # a reply was still generated


def test_bot_max_age_hours_filter(tmp_path):
    # thread 1 created 30 min ago (within window), thread 2 created 5h ago (old)
    threads = {
        50: make_threads(
            50,
            ["Свежая тема?", "Старая тема"],
            ages_seconds=[30 * 60, 5 * 3600],
        )
    }
    with MockLolzServer(threads) as server:
        cfg = _config(server.base_url, [50], tmp_path, max_thread_age_hours=2)
        results = ReplyBot(cfg).run_once()
        posted = [r for r in results if r.posted]
        skipped = [r for r in results if r.skipped_reason == "older than window"]
        assert len(posted) == 1
        assert len(skipped) == 1
        assert len(server.created_posts) == 1


def test_bot_skips_own_threads(tmp_path):
    # me_id == creator_user_id -> thread should be skipped
    threads = {50: make_threads(50, ["Моя тема?"], creator_user_id=1)}
    with MockLolzServer(threads, me_id=1) as server:
        cfg = _config(server.base_url, [50], tmp_path, skip_own_threads=True)
        results = ReplyBot(cfg).run_once()
        assert results[0].skipped_reason == "own thread"
        assert len(server.created_posts) == 0
