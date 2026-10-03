#!/usr/bin/env bash
# Daily fetch of news AND events: ./fetch.sh            (looks 7 days back)
#                                  ./fetch.sh --days 30  (longer look-back)
set -euo pipefail
cd "$(dirname "$0")"
exec .venv/bin/python fetch.py "$@"
