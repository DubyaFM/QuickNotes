# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

QuickNotes is a single-file Telegram bot (`quicknotes.py`) that captures freeform text messages and turns them into structured Obsidian-style markdown notes. It uses Google Gemini to classify, title, tag, and clean up the note, then writes it to a local vault directory with YAML frontmatter.

## Running the bot

```bash
python quicknotes.py
```

Requires a `.env` file in the project root with:
- `TELEGRAM_TOKEN` — Telegram bot token
- `GEMINI_API_KEY` — Google Gemini API key
- `NOTES_DIR` — path to the notes vault (defaults to `/notes`)
- `ALLOWED_CHAT_IDS` — comma-separated Telegram chat IDs allowed to use the bot; if unset, all users are accepted

Install dependencies:
```bash
pip install -r requirements.txt
```

## Deployment

Built for Docker. The `docker-compose.yml` uses `build: .` so no image registry is needed — Portainer can deploy directly from the GitHub repository. The notes directory is bind-mounted into the container at `/notes`.

Environment variables are set in the Portainer stack UI (not via `.env` in production).

## Architecture

All logic lives in `quicknotes.py`. The flow is:

1. **Poll Telegram** (`telegram_get_updates`) — long-polls the Telegram Bot API for new messages, ignoring `/commands` and unauthorized chat IDs
2. **Scan vault** (`get_existing_notes`) — reads all `.md` files under `NOTES_DIR` (excluding `Inbox/`) to give Gemini context for linking related notes
3. **Process with Gemini** (`process_with_gemini`) — sends the raw message + existing note list to Gemini; expects a JSON response with `category`, `type`, `filename`, `title`, `tags`, `related`, and `content`
4. **Write note** (`write_note`) — writes a `.md` file with YAML frontmatter to `NOTES_DIR/Inbox/`; appends a numeric suffix if the filename already exists
5. **Reply** — sends a plain-text Telegram confirmation with title, category, type, and tags

## Customizing categories and types

Edit `prompt.txt` to set your own categories and types. The prompt uses simple string replacement (`{notes_context}` and `{message_text}`) — curly braces in those two placeholders are the only special syntax.

## Note format

```yaml
---
title: "Human Readable Title"
date: YYYY-MM-DD
category: <from prompt.txt>
type: <from prompt.txt>
tags: ["tag1", "tag2"]
related: []
status: inbox
---
```

All notes land in `NOTES_DIR/Inbox/` regardless of category. Category and type are metadata only.

## Key constants

- `POLL_INTERVAL = 5` — seconds to wait between Telegram polls on error
- `INBOX_DIR` — `NOTES_DIR/Inbox/`, the write destination for all new notes
- Gemini model: `gemini-2.5-flash` (line 27)
