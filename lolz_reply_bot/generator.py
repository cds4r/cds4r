"""Reply generators.

Two strategies are provided:

* :class:`TemplateReplyGenerator` - no external dependencies. It analyses the
  thread title (question vs. statement, keywords, language) and assembles a
  reply that is relevant to the title. Always available, used as a fallback.
* :class:`OpenAIReplyGenerator` - uses any OpenAI-compatible chat completions
  endpoint to write a genuinely context-aware reply. Falls back to the template
  generator when the request fails.
"""

from __future__ import annotations

import logging
import random
import re
from typing import List, Optional, Protocol

import requests

logger = logging.getLogger(__name__)

# Very small stop-word lists just to pick "meaningful" keywords from a title.
_RU_STOP = {
    "и", "в", "во", "не", "что", "он", "на", "я", "с", "со", "как", "а", "то",
    "все", "она", "так", "его", "но", "да", "ты", "к", "у", "же", "вы", "за",
    "бы", "по", "только", "ее", "мне", "было", "вот", "от", "меня", "еще",
    "нет", "о", "из", "ему", "теперь", "когда", "даже", "ну", "вдруг", "ли",
    "если", "уже", "или", "ни", "быть", "был", "него", "до", "вас", "нибудь",
    "для", "мой", "тем", "чтобы", "нее", "они", "тут", "где", "есть", "надо",
    "ней", "их", "чем", "была", "сам", "чтоб", "без", "будто", "чего", "раз",
    "тоже", "себе", "под", "будет", "ж", "тогда", "кто", "этот", "того", "это",
}
_EN_STOP = {
    "the", "a", "an", "and", "or", "but", "if", "of", "to", "in", "on", "for",
    "with", "is", "are", "was", "were", "be", "been", "how", "what", "why",
    "who", "which", "this", "that", "these", "those", "can", "do", "does",
    "my", "your", "it", "at", "by", "as", "from", "about",
}

_RU_QUESTION_WORDS = {
    "как", "что", "где", "почему", "зачем", "когда", "кто", "какой", "какая",
    "какие", "сколько", "можно", "куда", "чем", "чей",
}
_EN_QUESTION_WORDS = {"how", "what", "where", "why", "when", "who", "which", "can"}


class ReplyGenerator(Protocol):
    """Anything that turns a thread title into a reply body."""

    def generate(self, title: str, *, thread_body: Optional[str] = None) -> str:
        ...


def _has_cyrillic(text: str) -> bool:
    return bool(re.search(r"[а-яё]", text, re.IGNORECASE))


def _keywords(title: str, language: str) -> List[str]:
    stop = _RU_STOP if language == "ru" else _EN_STOP
    words = re.findall(r"[\w']+", title.lower(), re.UNICODE)
    keywords = [w for w in words if len(w) >= 4 and w not in stop]
    # De-duplicate while preserving order.
    seen: set = set()
    unique = []
    for word in keywords:
        if word not in seen:
            seen.add(word)
            unique.append(word)
    return unique[:6]


def _is_question(title: str, language: str) -> bool:
    if "?" in title:
        return True
    first = re.findall(r"[\w']+", title.lower())
    words = _RU_QUESTION_WORDS if language == "ru" else _EN_QUESTION_WORDS
    return bool(first) and first[0] in words


class TemplateReplyGenerator:
    """Builds a relevant reply from the title without any external service."""

    def __init__(self, language: str = "ru", rng: Optional[random.Random] = None):
        self.language = language if language in {"ru", "en"} else "ru"
        self._rng = rng or random.Random()

    def _lang_for_title(self, title: str) -> str:
        # Reply in the language of the title: a Cyrillic title never gets an
        # English reply and a Latin title never gets a Cyrillic one. The
        # configured language is only used for ambiguous titles (digits/symbols).
        if _has_cyrillic(title):
            return "ru"
        if re.search(r"[a-z]", title, re.IGNORECASE):
            return "en"
        return self.language

    def generate(self, title: str, *, thread_body: Optional[str] = None) -> str:
        title = (title or "").strip()
        language = self._lang_for_title(title)
        keywords = _keywords(title, language)
        topic = keywords[0] if keywords else None
        question = _is_question(title, language)

        if language == "ru":
            return self._generate_ru(title, topic, keywords, question)
        return self._generate_en(title, topic, keywords, question)

    # -- Russian ----------------------------------------------------------
    def _generate_ru(self, title, topic, keywords, question) -> str:
        topic_phrase = f"«{topic}»" if topic else "этой теме"
        keyword_phrase = ", ".join(keywords[:3]) if keywords else "этот вопрос"

        if question:
            openers = [
                f"Хороший вопрос по теме {topic_phrase}.",
                f"Тоже интересовался этим по поводу {topic_phrase}.",
                f"Отличная тема — {topic_phrase} действительно заслуживает внимания.",
            ]
            bodies = [
                f"Из своего опыта скажу: тут важно разобраться в деталях "
                f"({keyword_phrase}), а не искать быстрый ответ.",
                f"Советую сначала уточнить вводные, а потом уже двигаться по "
                f"пунктам — тогда с {topic_phrase} будет проще.",
                f"Если коротко — многое зависит от конкретной ситуации, "
                f"но по {topic_phrase} обычно помогает пошаговый подход.",
            ]
            closers = [
                "Если скинешь больше деталей, подскажу конкретнее.",
                "Готов помочь, если распишешь подробнее.",
                "Напиши, что именно уже пробовал — так будет понятнее.",
            ]
        else:
            openers = [
                f"Интересная тема про {topic_phrase}.",
                f"Спасибо, что подняли тему {topic_phrase}.",
                f"Полезно, {topic_phrase} сейчас реально актуально.",
            ]
            bodies = [
                f"Согласен по поводу {keyword_phrase} — сам сталкивался с похожим.",
                f"Тема {topic_phrase} у многих вызывает вопросы, так что материал в тему.",
                f"По {topic_phrase} есть что обсудить, тут важны нюансы ({keyword_phrase}).",
            ]
            closers = [
                "Было бы здорово услышать и другие мнения.",
                "Подписался, интересно следить за обсуждением.",
                "Если будут обновления по теме — пиши.",
            ]
        return self._compose(openers, bodies, closers)

    # -- English ----------------------------------------------------------
    def _generate_en(self, title, topic, keywords, question) -> str:
        topic_phrase = f"\"{topic}\"" if topic else "this topic"
        keyword_phrase = ", ".join(keywords[:3]) if keywords else "this"

        if question:
            openers = [
                f"Good question about {topic_phrase}.",
                f"I was wondering about {topic_phrase} too.",
                f"Solid topic — {topic_phrase} definitely deserves a look.",
            ]
            bodies = [
                f"From my experience it comes down to the details ({keyword_phrase}) "
                f"rather than a one-size-fits-all answer.",
                f"I'd nail down the requirements first, then work through it step "
                f"by step — {topic_phrase} gets much easier that way.",
                f"Short version: it depends on your setup, but a methodical approach "
                f"to {topic_phrase} usually works.",
            ]
            closers = [
                "Share a few more details and I can be more specific.",
                "Happy to help if you expand on it.",
                "Let me know what you've already tried.",
            ]
        else:
            openers = [
                f"Interesting write-up on {topic_phrase}.",
                f"Thanks for bringing up {topic_phrase}.",
                f"Useful — {topic_phrase} is pretty relevant right now.",
            ]
            bodies = [
                f"I agree on {keyword_phrase}, ran into something similar myself.",
                f"{topic_phrase} raises a lot of questions, so this is timely.",
                f"There's a lot to discuss around {topic_phrase} — the nuances matter "
                f"({keyword_phrase}).",
            ]
            closers = [
                "Would love to hear other opinions too.",
                "Following this thread, curious where it goes.",
                "Ping the thread if there are updates.",
            ]
        return self._compose(openers, bodies, closers)

    def _compose(self, openers, bodies, closers) -> str:
        return " ".join(
            [self._rng.choice(openers), self._rng.choice(bodies), self._rng.choice(closers)]
        )


class OpenAIReplyGenerator:
    """Generate replies with an OpenAI-compatible chat completions endpoint."""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o-mini",
        language: str = "ru",
        temperature: float = 0.8,
        timeout: float = 30.0,
        fallback: Optional[ReplyGenerator] = None,
        session: Optional[requests.Session] = None,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.language = language
        self.temperature = temperature
        self.timeout = timeout
        self.fallback = fallback or TemplateReplyGenerator(language=language)
        self._session = session or requests.Session()

    def _system_prompt(self) -> str:
        lang = "русском" if self.language == "ru" else "English"
        return (
            "Ты — вежливый и полезный участник форума. По заголовку темы напиши "
            "короткий (2-4 предложения) содержательный и релевантный ответ, "
            "как будто ты реально отвечаешь в обсуждении. Пиши на "
            f"{lang} языке (если заголовок на другом языке — отвечай на языке "
            "заголовка). Без приветствий-штампов, без markdown, без ссылок и "
            "рекламы. Ответ должен быть по существу заголовка."
        )

    def generate(self, title: str, *, thread_body: Optional[str] = None) -> str:
        user_content = f"Заголовок темы: {title}"
        if thread_body:
            snippet = thread_body.strip()[:600]
            if snippet:
                user_content += f"\n\nНачало темы: {snippet}"
        payload = {
            "model": self.model,
            "temperature": self.temperature,
            "messages": [
                {"role": "system", "content": self._system_prompt()},
                {"role": "user", "content": user_content},
            ],
        }
        try:
            response = self._session.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"].strip()
            if not content:
                raise ValueError("empty completion")
            return content
        except Exception as exc:  # noqa: BLE001 - degrade gracefully
            logger.warning("LLM generation failed (%s); using template fallback", exc)
            return self.fallback.generate(title, thread_body=thread_body)


def build_generator(config) -> ReplyGenerator:
    """Return the best available generator for the given ``BotConfig``."""
    template = TemplateReplyGenerator(language=config.reply_language)
    if config.use_llm:
        return OpenAIReplyGenerator(
            api_key=config.llm_api_key,
            base_url=config.llm_base_url,
            model=config.llm_model,
            language=config.reply_language,
            temperature=config.llm_temperature,
            fallback=template,
        )
    return template
