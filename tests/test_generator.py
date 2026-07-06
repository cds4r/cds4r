import random

from lolz_reply_bot.generator import (
    TemplateReplyGenerator,
    _is_question,
    _keywords,
)


def test_keywords_filters_stopwords_russian():
    kws = _keywords("Как настроить прокси для бота", "ru")
    assert "настроить" in kws
    assert "прокси" in kws
    # stop-word "как"/"для" must be dropped
    assert "как" not in kws
    assert "для" not in kws


def test_is_question_detection():
    assert _is_question("Как поднять сервер?", "ru")
    assert _is_question("Что лучше выбрать", "ru")  # starts with question word
    assert not _is_question("Продаю аккаунт стим", "ru")
    assert _is_question("How do I fix this?", "en")


def test_template_reply_is_contextual_and_nonempty():
    gen = TemplateReplyGenerator(language="ru", rng=random.Random(1))
    title = "Как защититься от фишинга"
    reply = gen.generate(title)
    assert isinstance(reply, str)
    assert len(reply) > 20
    # The reply should reference a keyword from the title.
    assert "защититься" in reply.lower()


def test_template_reply_switches_language_for_english_title():
    gen = TemplateReplyGenerator(language="ru", rng=random.Random(2))
    reply = gen.generate("How to configure nginx reverse proxy?")
    # An English title must not produce a Cyrillic reply.
    assert not any("а" <= ch <= "я" for ch in reply.lower())
    assert "nginx" in reply.lower() or "configure" in reply.lower()


def test_template_reply_handles_empty_title():
    gen = TemplateReplyGenerator(language="ru", rng=random.Random(3))
    reply = gen.generate("")
    assert isinstance(reply, str)
    assert reply.strip()
