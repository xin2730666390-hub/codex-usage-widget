#!/bin/zsh
set -e

cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
  osascript -e 'display dialog "Python 3 is required. Install Python from python.org, then open this launcher again." buttons {"OK"} default button "OK"'
  exit 1
fi

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

source .venv/bin/activate
python -m pip install --upgrade pip >/dev/null
python -m pip install --upgrade -r requirements.txt >/dev/null
python codex_usage_widget.py
