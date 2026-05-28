#!/usr/bin/env bash
# Wrapper — use Python to avoid CRLF/shell issues on WSL.
exec python3 "$(dirname "$0")/download_overnight.py" "$@"
