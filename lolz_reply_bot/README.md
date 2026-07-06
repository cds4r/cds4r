# lolz_reply_bot

A bot for [lolz.live](https://lolz.live) (Zelenka) that leaves **context‑aware
replies** in the threads of a chosen forum **section**, based on each thread's
**title**. You tell it which section id to work in and it does the rest.

## What it does

1. Reads the threads of the section(s) you specify (`--forum-id`).
2. For every thread it builds a meaningful reply from the thread title.
3. Posts the reply back to the thread via the Forum API (`POST /posts`).
4. Remembers which threads it already answered so it never double‑replies.

Replies are generated either by a built‑in **template generator** (works out of
the box, no external service, picks up keywords/question form/language from the
title) or, if you provide an LLM key, by any **OpenAI‑compatible** chat model
for genuinely smart answers.

## Install

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Configure

Copy `.env.example` to `.env` and set at least:

- `LOLZ_TOKEN` – your lolz.live API token (needs the `read` + `post` scopes).
- `LOLZ_FORUM_ID` – the section id to work in (or pass `--forum-id`).

Optional, for smart LLM replies: `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`.

## Run

Preview replies without posting (no token required):

```bash
python -m lolz_reply_bot --forum-id 123 --dry-run
```

Post replies for real:

```bash
python -m lolz_reply_bot --forum-id 123 --max-replies 5
```

Work in several sections and loop periodically:

```bash
python -m lolz_reply_bot --forum-id "123,456" --loop --loop-interval 600
```

### Useful flags

| Flag | Meaning |
| --- | --- |
| `--forum-id` | Section id(s) to work in (comma separated). |
| `--dry-run` | Generate + print replies, post nothing. |
| `--max-replies N` | Cap replies per run. |
| `--reply-to-own` | Also reply to the bot's own threads. |
| `--allow-duplicates` | Ignore the state file and re‑reply. |
| `--reply-language` | `ru` (default) or `en`. |
| `--loop` / `--loop-interval` | Keep scanning periodically. |
| `--request-delay` | Seconds between API calls (default 3, API limit ~20/min). |

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest
```

The test suite includes an in‑process mock of the lolz.live API, so the full
fetch → generate → post flow is exercised end‑to‑end without network access.
