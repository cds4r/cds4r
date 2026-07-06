import os

import pytest

from lolz_reply_bot.config import BotConfig, _parse_forum_ids
from lolz_reply_bot.state import StateStore


def test_parse_forum_ids_variants():
    assert _parse_forum_ids("123") == [123]
    assert _parse_forum_ids("1,2, 3") == [1, 2, 3]
    assert _parse_forum_ids("10 20") == [10, 20]
    assert _parse_forum_ids("") == []
    assert _parse_forum_ids(None) == []


def test_config_from_env():
    env = {
        "LOLZ_TOKEN": "abc",
        "LOLZ_FORUM_ID": "42, 43",
        "LOLZ_REQUEST_DELAY": "0",
        "REPLY_LANGUAGE": "en",
    }
    cfg = BotConfig.from_env(env)
    assert cfg.token == "abc"
    assert cfg.forum_ids == [42, 43]
    assert cfg.request_delay == 0
    assert cfg.reply_language == "en"
    assert cfg.use_llm is False


def test_config_validate_requires_forum():
    cfg = BotConfig(token="x", forum_ids=[])
    with pytest.raises(ValueError):
        cfg.validate()


def test_config_validate_requires_token_when_not_dry_run():
    cfg = BotConfig(token=None, forum_ids=[1], dry_run=False)
    with pytest.raises(ValueError):
        cfg.validate()
    # dry-run does not require a token
    BotConfig(token=None, forum_ids=[1], dry_run=True).validate()


def test_state_store_roundtrip(tmp_path):
    path = os.path.join(tmp_path, "state.json")
    store = StateStore(path)
    assert not store.has_replied(1, 100)
    store.mark_replied(1, 100)
    store.save()

    reloaded = StateStore(path)
    assert reloaded.has_replied(1, 100)
    assert not reloaded.has_replied(1, 200)
    assert not reloaded.has_replied(2, 100)
