# QuickNotes

A Telegram bot that turns freeform messages into structured Obsidian markdown notes, powered by Google Gemini.

Send a message → Gemini classifies and titles it → a `.md` file with YAML frontmatter lands in your vault.

---

## Prerequisites

- A [Telegram bot token](https://core.telegram.org/bots#botfather) (create one via BotFather)
- A [Google Gemini API key](https://aistudio.google.com/apikey)
- Docker (and optionally Portainer for UI-based deployment)
- An Obsidian vault directory accessible to the host machine

---

## Docker Setup

The recommended way to run QuickNotes is via Docker Compose using the pre-built image from GitHub Container Registry.

### 1. Create a compose file

```yaml
services:
  quicknotes:
    container_name: quicknotes
    image: ghcr.io/dubyafm/quicknotes:latest
    restart: unless-stopped
    environment:
      - TELEGRAM_TOKEN=${TELEGRAM_TOKEN}
      - GEMINI_API_KEY=${GEMINI_API_KEY}
      - ALLOWED_CHAT_IDS=${ALLOWED_CHAT_IDS}
      - NOTES_DIR=/notes
      - CONFIG_DIR=/config
    volumes:
      - ${NOTES_HOST_PATH}:/notes
      - ${CONFIG_HOST_PATH:-/opt/quicknotes/config}:/config
```

### 2. Set environment variables

Create a `.env` file alongside the compose file:

```env
TELEGRAM_TOKEN=your_telegram_bot_token
GEMINI_API_KEY=your_gemini_api_key
ALLOWED_CHAT_IDS=123456789,987654321
NOTES_HOST_PATH=/path/to/your/obsidian/vault
CONFIG_HOST_PATH=/opt/quicknotes/config
```

| Variable | Required | Description |
|---|---|---|
| `TELEGRAM_TOKEN` | Yes | Bot token from BotFather |
| `GEMINI_API_KEY` | Yes | API key from Google AI Studio |
| `ALLOWED_CHAT_IDS` | No | Comma-separated Telegram chat IDs; if unset, all users are accepted |
| `NOTES_HOST_PATH` | Yes | Host path to your Obsidian vault |
| `CONFIG_HOST_PATH` | No | Host path for config files (defaults to `/opt/quicknotes/config`) |

### 3. Start the bot

```bash
docker compose up -d
```

On first launch, the entrypoint script copies default config files (`prompt.txt`, `list_lookup_prompt.txt`, `settings.json`) into the config volume so you can edit them without rebuilding the image.

---

## Customization

### Categories and note types

Edit `prompt.txt` in your config directory to define your own categories and note types. The prompt uses two placeholders — `{notes_context}` and `{message_text}` — which are the only parts with special syntax. Everything else is plain text you can rewrite freely.

### Gemini model

Edit `settings.json` to change the model:

```json
{
  "model": "gemini-2.5-flash"
}
```

### List folder names

The watchlist, playlist, and readinglist folders default to `Watchlist/`, `Playlist/`, and `Readinglist/` inside your vault. Override them in `settings.json`:

```json
{
  "list_dirs": {
    "watchlist": "My Watch List",
    "playlist": "Music",
    "readinglist": "Books"
  }
}
```

---

## Features

### Notes

Send any freeform text and the bot will:

- Classify it into a category and type
- Generate a title, filename, and tags
- Link it to related existing notes
- Write a `.md` file with YAML frontmatter to `Inbox/` in your vault

Frontmatter fields: `title`, `date`, `category`, `type`, `tags`, `related`, `status`.

### Media lists

Prefix or phrase your message so Gemini identifies it as a list item (e.g. "add Inception to my watchlist", "queue up Hollow Knight", "want to read Project Hail Mary"). The bot will:

- Look up metadata via Google Search (creator, year, genre, streaming platform)
- Write the item to the appropriate list folder (`Watchlist/`, `Playlist/`, or `Readinglist/`)
- Auto-create an Obsidian Base index file (e.g. `Watchlist/Watchlist.md`) on the first entry, which renders as a live table of all items in that folder

Frontmatter fields: `title`, `date`, `list`, `media_type`, `creator`, `genre`, `platform`, `year`, `status`, `tags`, `related`.

### `/status` command

Send `/status` to the bot to get a summary of uptime, total note count, and Gemini API connectivity.
