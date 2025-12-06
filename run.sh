#!/usr/bin/env bash

# Start the app only when it's not already running.
if pgrep -f hack >/dev/null 2>&1; then
  exit 0
fi

echo "start hack app"
nohup ~/.local/bin/uv run hack.py >/tmp/hack_log &
