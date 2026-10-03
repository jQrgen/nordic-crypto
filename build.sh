#!/usr/bin/env bash
# Builds site/ and runs the privacy gate. Pushes nothing.
#   ./build.sh            public build: only editor-approved (and, where required, jQrgen-approved) content
#   ./build.sh --preview  local review build: also pending items, clearly marked; never publish this one
set -euo pipefail
cd "$(dirname "$0")"
.venv/bin/python build.py "$@"
.venv/bin/python tools/privacy_gate.py site
.venv/bin/python tools/text_gate.py
