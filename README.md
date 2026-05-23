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
      - PUID=${PUID:-1000}
      - PGID=${PGID:-1000}
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
| `PUID` | No | User ID to run as (default `1000`) — set to match your host user |
| `PGID` | No | Group ID to run as (default `1000`) — set to match your host group |

### 3. Start the bot

```bash
docker compose up -d
```

On first launch, the entrypoint copies a default `settings.json` into the config volume. Prompt templates are baked into the image and updated automatically when you pull a new image — they are not written to the config volume.

---

## Customization

All customization lives in `settings.json` in your config volume. The prompt templates are developer-owned and updated automatically with each image pull — you do not edit them directly.

### Categories and note types

Set the categories and types Gemini will use when classifying notes:

```json
{
  "categories": ["DnD", "HomeLab", "General"],
  "types": ["Session Notes", "Idea", "Reference"]
}
```

### Additional instructions

Inject extra rules into the prompt without touching the template:

```json
{
  "additional_instructions": "prefer DnD category for anything fantasy or tabletop related"
}
```

### Gemini model

```json
{
  "model": "gemini-2.5-flash"
}
```

### Smart note linking

When enabled (the default), the bot scans your vault before each note, passes all existing note titles to Gemini as context, and writes related-note links to the frontmatter. Disable it to skip the vault scan and omit related links — useful for large vaults or if you prefer not to send your note titles to the API.

```json
{
  "smart_linking": false
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

### Full `settings.json` reference

```json
{
  "model": "gemini-2.5-flash",
  "smart_linking": true,
  "categories": ["General"],
  "types": ["Idea"],
  "additional_instructions": "",
  "list_dirs": {
    "watchlist": "Watchlist",
    "playlist": "Playlist",
    "readinglist": "Readinglist"
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
