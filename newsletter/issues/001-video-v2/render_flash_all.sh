#!/bin/bash
# Sensational cut. Sequential, same memory guard as the newsreel.
set -euo pipefail
cd "$(dirname "$0")"
export TIMELINE=build/timeline_flash.json
export SEGDIR=build/flash/
export RENDER=render_flash.py
exec bash render_all.sh "$@"
