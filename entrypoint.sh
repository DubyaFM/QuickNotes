#!/bin/sh
set -e

PUID=${PUID:-1000}
PGID=${PGID:-1000}

DEFAULT_CONFIG="/app/config"
TARGET_CONFIG="${CONFIG_DIR:-/app/config}"

if [ "$TARGET_CONFIG" != "$DEFAULT_CONFIG" ]; then
    mkdir -p "$TARGET_CONFIG"
    for f in "$DEFAULT_CONFIG"/*; do
        filename=$(basename "$f")
        if [ ! -f "$TARGET_CONFIG/$filename" ]; then
            echo "Populating default config: $filename"
            cp "$f" "$TARGET_CONFIG/$filename"
        fi
    done
fi

# Create group/user matching host UID/GID if they don't already exist
if ! getent group "$PGID" > /dev/null 2>&1; then
    addgroup --gid "$PGID" appgroup
fi
if ! getent passwd "$PUID" > /dev/null 2>&1; then
    adduser --uid "$PUID" --gid "$PGID" --no-create-home --disabled-password --gecos "" appuser
fi

# Fix ownership of mounted volumes so the unprivileged user can write to them
chown -R "$PUID:$PGID" "${NOTES_DIR:-/notes}" "$TARGET_CONFIG"

exec gosu "$PUID" python -u quicknotes.py
