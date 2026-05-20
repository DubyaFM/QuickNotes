#!/bin/sh
set -e

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

exec python -u quicknotes.py
