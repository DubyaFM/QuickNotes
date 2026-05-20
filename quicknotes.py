#!/usr/bin/env python3

import os
import time
import json
import requests
import re
import concurrent.futures
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Bootstrap config dir from real OS environment before any dotenv loading
CONFIG_DIR = Path(os.environ.get('CONFIG_DIR', Path(__file__).parent / 'config'))

# Load secrets — config dir takes priority, project root is local dev fallback
load_dotenv(CONFIG_DIR / '.env')
load_dotenv(Path(__file__).parent / '.env')

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
NOTES_DIR = Path(os.getenv('NOTES_DIR', '/notes'))
ALLOWED_CHAT_IDS = set(
    int(x.strip()) for x in os.getenv('ALLOWED_CHAT_IDS', '').split(',') if x.strip()
)

# Load settings.json
_settings_path = CONFIG_DIR / 'settings.json'
_settings = json.loads(_settings_path.read_text()) if _settings_path.exists() else {}

GEMINI_MODEL = _settings.get('model', 'gemini-2.5-flash')
INBOX_DIR = NOTES_DIR / 'Inbox'
LIST_DIRS = {
    k: NOTES_DIR / v
    for k, v in _settings.get('list_dirs', {
        'watchlist': 'Watchlist',
        'playlist': 'Playlist',
        'readinglist': 'Readinglist',
    }).items()
}
POLL_INTERVAL = 5
GEMINI_TIMEOUT = 90

# Initialize Gemini
gemini = genai.Client(api_key=GEMINI_API_KEY)

TELEGRAM_API = f'https://api.telegram.org/bot{TELEGRAM_TOKEN}'
PROMPT_TEMPLATE = (CONFIG_DIR / 'prompt.txt').read_text()
LIST_LOOKUP_TEMPLATE = (CONFIG_DIR / 'list_lookup_prompt.txt').read_text()


def get_existing_notes():
    """Scan vault for processed note filenames and titles."""
    notes = []
    for f in NOTES_DIR.rglob('*.md'):
        if f.is_relative_to(INBOX_DIR):
            continue
        title = f.stem.replace('-', ' ').replace('_', ' ').title()
        try:
            content = f.read_text()
            match = re.search(r'^title:\s*(.+)$', content, re.MULTILINE)
            if match:
                title = match.group(1).strip().strip('"')
        except Exception:
            pass
        notes.append(f'{f.name}: {title}')
    return notes


def _parse_json_response(raw):
    if not raw:
        raise ValueError('Gemini returned an empty response (possibly blocked by safety filters)')
    raw = raw.strip()
    raw = re.sub(r'^```(?:json)?\n?', '', raw)
    raw = re.sub(r'\n?```$', '', raw)
    return json.loads(raw)


def _gemini_call(fn):
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(fn).result(timeout=GEMINI_TIMEOUT)


def process_with_gemini(message_text, existing_notes):
    """Send message to Gemini for processing."""
    notes_context = '\n'.join(existing_notes) if existing_notes else 'No existing notes yet.'
    prompt = PROMPT_TEMPLATE.replace('{notes_context}', notes_context).replace('{message_text}', message_text)
    processed = _parse_json_response(_gemini_call(
        lambda: gemini.models.generate_content(model=GEMINI_MODEL, contents=prompt)
    ).text)

    if processed.get('note_type') == 'list':
        lookup_prompt = (LIST_LOOKUP_TEMPLATE
                         .replace('{title}', processed.get('title', ''))
                         .replace('{media_type}', processed.get('media_type', '')))
        search_tool = types.Tool(google_search=types.GoogleSearch())
        try:
            lookup_response = _gemini_call(lambda: gemini.models.generate_content(
                model=GEMINI_MODEL,
                contents=lookup_prompt,
                config=types.GenerateContentConfig(tools=[search_tool]),
            ))
            metadata = _parse_json_response(lookup_response.text)
            processed.update({k: v for k, v in metadata.items() if v is not None})
        except Exception as e:
            print(f'Metadata lookup failed (continuing without it): {e}')

    return processed


def write_list_item(processed, raw_message):
    """Write a list item (watchlist/playlist/readinglist) to its folder."""
    list_type = processed.get('list', 'watchlist')
    folder = LIST_DIRS.get(list_type, NOTES_DIR / 'Watchlist')
    folder.mkdir(parents=True, exist_ok=True)

    date_str = datetime.now().strftime('%Y-%m-%d')
    filename = f"{processed['filename']}.md"
    filepath = folder / filename

    counter = 1
    while filepath.exists():
        filepath = folder / f"{processed['filename']}-{counter}.md"
        counter += 1

    safe_title = processed['title'].replace('"', '\\"')
    lines = [
        '---',
        f'title: "{safe_title}"',
        f'date: {date_str}',
        f'list: {list_type}',
        f'media_type: {processed.get("media_type", "")}',
    ]
    for field in ('creator', 'genre', 'platform'):
        val = processed.get(field)
        if val is not None:
            lines.append(f'{field}: "{str(val).replace(chr(34), chr(92)+chr(34))}"')
    if processed.get('year') is not None:
        lines.append(f'year: {processed["year"]}')
    lines.append(f'status: {processed.get("status", "want-to-watch")}')

    tags_yaml = ', '.join(f'"{t}"' for t in processed.get('tags', []))
    lines.append(f'tags: [{tags_yaml}]')
    related_yaml = '\n'.join(f'  - "{r}"' for r in processed.get('related', []))
    lines.append(f'related:\n{related_yaml}' if related_yaml else 'related: []')
    lines.append('---\n')

    content = '\n'.join(lines) + '\n' + processed.get('content', raw_message)
    filepath.write_text(content)
    return filepath, list_type


def write_note(processed, raw_message):
    """Write the processed note to the vault."""
    if processed.get('note_type') == 'list':
        return write_list_item(processed, raw_message)

    category = processed.get('category', 'General')

    INBOX_DIR.mkdir(parents=True, exist_ok=True)

    date_str = datetime.now().strftime('%Y-%m-%d')
    filename = f"{processed['filename']}.md"
    filepath = INBOX_DIR / filename

    # Handle duplicate filenames
    counter = 1
    while filepath.exists():
        filepath = INBOX_DIR / f"{processed['filename']}-{counter}.md"
        counter += 1

    tags_yaml = ', '.join(f'"{t}"' for t in processed.get('tags', []))
    related_yaml = '\n'.join(f'  - "{r}"' for r in processed.get('related', []))
    related_block = f'related:\n{related_yaml}' if related_yaml else 'related: []'

    safe_title = processed['title'].replace('"', '\\"')
    note_type = processed.get('type', 'Idea')
    frontmatter = f"""---
title: "{safe_title}"
date: {date_str}
category: {category}
type: {note_type}
tags: [{tags_yaml}]
{related_block}
status: inbox
---

"""

    content = frontmatter + processed.get('content', raw_message)
    filepath.write_text(content)
    return filepath, category


def telegram_get_updates(offset=None):
    params = {'timeout': 30, 'allowed_updates': ['message']}
    if offset:
        params['offset'] = offset
    try:
        r = requests.get(f'{TELEGRAM_API}/getUpdates', params=params, timeout=35)
        return r.json()
    except Exception as e:
        print(f'Error getting updates: {e}')
        return None


def telegram_send_message(chat_id, text):
    try:
        r = requests.post(f'{TELEGRAM_API}/sendMessage', json={
            'chat_id': chat_id,
            'text': text,
        })
        data = r.json()
        if not data.get('ok'):
            print(f'Telegram API error: {data}')
    except Exception as e:
        print(f'Error sending message: {e}')


def handle_status_command(chat_id, start_time):
    uptime = datetime.now() - start_time
    total_seconds = int(uptime.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes = remainder // 60
    uptime_str = f'{hours}h {minutes}m' if hours else f'{minutes}m'

    note_count = sum(1 for _ in NOTES_DIR.rglob('*.md'))

    try:
        gemini.models.get(model=GEMINI_MODEL)
        gemini_status = f'✅ connected ({GEMINI_MODEL})'
    except Exception as e:
        gemini_status = f'❌ {str(e)[:60]}'

    reply = (
        f'✅ Bot is running\n'
        f'⏱ Uptime: {uptime_str}\n'
        f'📝 Notes in vault: {note_count}\n'
        f'🤖 Gemini: {gemini_status}\n'
        f'📁 Vault: {NOTES_DIR}'
    )
    telegram_send_message(chat_id, reply)


def main():
    print('QuickNotes bot starting...')
    if not ALLOWED_CHAT_IDS:
        print('WARNING: ALLOWED_CHAT_IDS not set — bot will respond to any user')
    offset = None
    start_time = datetime.now()

    while True:
        updates = telegram_get_updates(offset)
        if not updates or not updates.get('ok'):
            time.sleep(POLL_INTERVAL)
            continue

        for update in updates.get('result', []):
            offset = update['update_id'] + 1
            message = update.get('message', {})
            text = message.get('text', '').strip()
            chat_id = message.get('chat', {}).get('id')

            if not text or not chat_id:
                continue

            if ALLOWED_CHAT_IDS and chat_id not in ALLOWED_CHAT_IDS:
                continue

            if text == '/status':
                handle_status_command(chat_id, start_time)
                continue

            if text.startswith('/'):
                continue

            print(f'Processing: {text[:50]}...')
            telegram_send_message(chat_id, '⏳ Processing your note...')

            try:
                existing_notes = get_existing_notes()
                processed = process_with_gemini(text, existing_notes)
                filepath, _ = write_note(processed, text)

                if processed.get('note_type') == 'list':
                    list_type = processed.get('list', 'watchlist')
                    list_emoji = {'watchlist': '👁', 'playlist': '🎮', 'readinglist': '📚'}.get(list_type, '📋')
                    meta_parts = [p for p in [
                        processed.get('creator'),
                        str(processed['year']) if processed.get('year') else None,
                        processed.get('genre'),
                        processed.get('platform'),
                    ] if p]
                    reply = (
                        f"✅ {processed['title']}\n"
                        f"{list_emoji} {list_type.title()} · {processed.get('status', '')}"
                    )
                    if meta_parts:
                        reply += f"\n🎬 {' · '.join(meta_parts)}"
                    reply += f"\n🏷 {', '.join(processed.get('tags', []))}"
                else:
                    reply = (
                        f"✅ {processed['title']}\n"
                        f"📁 {processed.get('category', 'General')} · {processed.get('type', 'Idea')}\n"
                        f"🏷 {', '.join(processed.get('tags', []))}"
                    )
                    if processed.get('related'):
                        reply += f"\n🔗 Related: {', '.join(processed['related'])}"

                telegram_send_message(chat_id, reply)
                print(f'Note written: {filepath}')

            except Exception as e:
                print(f'Error processing note: {e}')
                telegram_send_message(chat_id, f'❌ Error processing note: {str(e)}')


if __name__ == '__main__':
    main()