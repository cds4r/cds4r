# AGENTS.md

## Project overview

This repository contains `lolz_reply_bot`, a Python CLI bot that leaves
context-aware replies in the threads of a chosen **forum section** on
[lolz.live](https://lolz.live) (Zelenka), based on each thread's **title**.

- `lolz_reply_bot/api.py` – minimal Forum API client (`GET /threads`,
  `POST /posts`, `GET /users/me`) with rate limiting + retries.
- `lolz_reply_bot/generator.py` – reply generators: a dependency-free template
  generator (always available) and an optional OpenAI-compatible LLM generator.
- `lolz_reply_bot/bot.py` – orchestration (scan → generate → post, with state).
- `lolz_reply_bot/cli.py` – `python -m lolz_reply_bot` entry point.
- Usage docs: `lolz_reply_bot/README.md`.

## Cursor Cloud specific instructions

- Python project. Set up with a venv: `python3 -m venv .venv && . .venv/bin/activate`
  then `pip install -r requirements-dev.txt`. `python3-venv` is required for the
  venv (installed at the system level; not part of the update script).
- Run tests: `python -m pytest` (from repo root). Tests are network-free — they
  spin up an in-process mock of the lolz.live API (`tests/mock_server.py`), so
  no token or internet is needed to exercise the full fetch→generate→post flow.
- Lint/build: there is no configured linter; `python -m py_compile lolz_reply_bot/*.py`
  is a quick syntax check. There is no build step (pure Python).
- Running the app **live** requires a real lolz.live API token in `LOLZ_TOKEN`
  (scopes `read` + `post`) and a section id. Without a token, use `--dry-run`,
  which generates and prints replies but posts nothing (great for local testing).
- The API is rate limited (~20 req/min); the client defaults to a 3s delay
  between requests. Use `--request-delay 0` only against the local mock server.
- The bot records answered threads in a state file (default
  `.lolz_reply_bot_state.json`, git-ignored) to avoid double-replying; delete it
  or pass `--allow-duplicates` to reply again.
- `README.md` at the repo root is the owner's GitHub **profile** README — leave
  it untouched; the bot's docs live in `lolz_reply_bot/README.md`.
