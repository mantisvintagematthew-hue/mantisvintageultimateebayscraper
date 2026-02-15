#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python -m pip install -e .[dev] >/dev/null 2>&1 || true
python -m uvicorn app.ui.server:app --host 127.0.0.1 --port 8080
