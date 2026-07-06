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

# Words that hint at the "category" of a thread so replies stay a bit relevant.
_RU_GREETING_HINTS = {
    "утро", "утречко", "утречка", "утра", "привет", "приветик", "здаров",
    "здарова", "хай", "ночи", "ночь", "добри", "доброе", "здравствуйте",
    "здравствуй", "вечер", "день", "дратути", "всем",
}
_RU_RATING_HINTS = {"оцените", "оценка", "оценить", "оцен", "прокачку", "прокачка"}
_RU_BYE_HINTS = {"прощаюсь", "пока", "ухожу", "спокойной", "споки", "устал", "устала"}


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
        category = self._category(title, language)

        if language == "ru":
            reply = self._rng.choice(_RU_REPLIES[category])
        else:
            reply = self._rng.choice(_EN_REPLIES[category])

        # Occasionally add a trailing emoji for extra flavour (but not always,
        # so replies stay human and varied).
        if self._rng.random() < 0.4:
            reply = f"{reply} {self._rng.choice(_EXTRA_EMOJI)}"
        return reply

    def _category(self, title: str, language: str) -> str:
        """Bucket the title into greeting / bye / rating / question / generic."""
        words = set(re.findall(r"[\w']+", title.lower(), re.UNICODE))
        if language == "ru":
            if words & _RU_GREETING_HINTS:
                return "greeting"
            if words & _RU_BYE_HINTS:
                return "bye"
            if words & _RU_RATING_HINTS:
                return "rating"
        else:
            lower = title.lower()
            if any(w in lower for w in ("hi", "hello", "morning", "good night", "gm")):
                return "greeting"
            if any(w in lower for w in ("bye", "cya", "leaving", "gn")):
                return "bye"
            if "rate" in lower or "rating" in lower:
                return "rating"
        if _is_question(title, language):
            return "question"
        return "generic"


# Short, casual, human-sounding replies with a bit of slang and emoji, tuned
# for an off-topic ("флудилка") section. Kept intentionally tiny.
_RU_REPLIES = {
    "greeting": [
        "доброе утро ☀️", "здарова 🤝", "привет-привет 👋", "хай 😎",
        "утречка ☕", "дратути 🖐️", "и тебе привет 😄", "здаров, чо как",
    ],
    "bye": [
        "покеда 👋", "давай, не пропадай", "споки 😴", "бывай 🫡",
        "ну удачи там 🙌", "пиши как что",
    ],
    "rating": [
        "норм 👍", "10 из 10 🔥", "ну пойдёт 😄", "топчик 🔥", "мне зашло 👌",
        "ну такое, но лайк 😅", "красава 💪", "имба",
    ],
    "question": [
        "чоо? 🤨", "не пон 🤔", "а что случилось-то", "хз даже 🤷",
        "поясни за это", "чо по чем 😅", "интересно, го дальше", "а сам как думаешь?",
        "хмм, надо глянуть 👀",
    ],
    "generic": [
        "пон 👌", "жиза 😂", "ахахах 😆", "лол 🤣", "база 💯", "мда уж 🙃",
        "четко 🔥", "согласен полностью", "красава", "плюсую ➕",
        "вот это поворот 😮", "ну ты дал 😄", "кек", "реально так", "топ 🔝",
    ],
}

_EN_REPLIES = {
    "greeting": ["morning ☀️", "hey hey 👋", "yo 😎", "hi there 🙌", "sup"],
    "bye": ["cya 👋", "take care 🫡", "gn 😴", "later!"],
    "rating": ["solid 👍", "10/10 🔥", "not bad 😄", "i dig it 👌", "clean"],
    "question": ["huh? 🤔", "no idea tbh 🤷", "wait what", "explain pls",
                 "hmm good one 👀"],
    "generic": ["lol 😂", "based 💯", "true 🔥", "fr fr", "nice one 👌",
                "haha 😆", "wild 😮", "agreed", "big +"],
}

_EXTRA_EMOJI = ["😁", "😂", "🔥", "💀", "👀", "🙌", "😅", "🤝", "✌️", "😎"]


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
            "Ты — обычный живой участник форума-флудилки. По заголовку темы "
            "напиши ОЧЕНЬ короткий (1 короткая фраза, максимум предложение) "
            "человеческий и рофельный ответ — так, как реально пишут в чате: "
            "разговорно, с сленгом (типа «чоо», «пон», «жиза», «база», «доброе "
            "утро») и с уместными эмодзи. Пиши на "
            f"{lang} языке (если заголовок на другом языке — отвечай на языке "
            "заголовка). Без markdown, без ссылок, без рекламы, без занудства. "
            "Ответ должен быть в тему заголовка, но лёгкий и короткий."
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
