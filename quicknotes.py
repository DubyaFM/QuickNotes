#!/usr/bin/env python3

import os
import time
import json
import requests
import re
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
import google.generativeai as genai

# Load environment
load_dotenv(Path(__file__).parent / '.env')

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
NOTES_DIR = Path(os.getenv('NOTES_DIR', '/notes'))
ALLOWED_CHAT_IDS = set(
    int(x.strip()) for x in os.getenv('ALLOWED_CHAT_IDS', '').split(',') if x.strip()
)
INBOX_DIR = NOTES_DIR / 'Inbox'
POLL_INTERVAL = 5  # seconds

# Initialize Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')

TELEGRAM_API = f'https://api.telegram.org/bot{TELEGRAM_TOKEN}'
PROMPT_TEMPLATE = (Path(__file__).parent / 'prompt.txt').read_text()


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


def process_with_gemini(message_text, existing_notes):
    """Send message to Gemini for processing."""
    notes_context = '\n'.join(existing_notes) if existing_notes else 'No existing notes yet.'
    prompt = PROMPT_TEMPLATE.replace('{notes_context}', notes_context).replace('{message_text}', message_text)
    response = model.generate_content(prompt)
    raw = response.text
    if not raw:
        raise ValueError('Gemini returned an empty response (possibly blocked by safety filters)')
    raw = raw.strip()

    # Strip markdown code fences if present
    raw = re.sub(r'^```(?:json)?\n?', '', raw)
    raw = re.sub(r'\n?```$', '', raw)

    return json.loads(raw)


def write_note(processed, raw_message):
    """Write the processed note to the vault."""
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


def main():
    print('QuickNotes bot starting...')
    if not ALLOWED_CHAT_IDS:
        print('WARNING: ALLOWED_CHAT_IDS not set — bot will respond to any user')
    offset = None

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

            # Skip commands for now
            if text.startswith('/'):
                continue

            print(f'Processing: {text[:50]}...')
            telegram_send_message(chat_id, '⏳ Processing your note...')

            try:
                existing_notes = get_existing_notes()
                processed = process_with_gemini(text, existing_notes)
                filepath, category = write_note(processed, text)

                response = (
                    f"✅ {processed['title']}\n"
                    f"📁 {category} · {processed.get('type', 'Idea')}\n"
                    f"🏷 {', '.join(processed.get('tags', []))}"
                )
                if processed.get('related'):
                    response += f"\n🔗 Related: {', '.join(processed['related'])}"

                telegram_send_message(chat_id, response)
                print(f'Note written: {filepath}')

            except Exception as e:
                print(f'Error processing note: {e}')
                telegram_send_message(chat_id, f'❌ Error processing note: {str(e)}')


if __name__ == '__main__':
    main()