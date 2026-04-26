#!/usr/bin/env bash
# Thin wrapper: activate venv and run refresh_gmail_token.py
# Usage: ./scripts/refresh_gmail_token.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENGINE_DIR="$(dirname "$SCRIPT_DIR")"

cd "$ENGINE_DIR"

if [[ ! -d ".venv" ]]; then
  echo "❌ .venv not found in $ENGINE_DIR" >&2
  exit 1
fi

# shellcheck disable=SC1091
source .venv/bin/activate

if ! command -v railway >/dev/null 2>&1; then
  echo "❌ Railway CLI not found. Install with: brew install railway" >&2
  exit 1
fi

python scripts/refresh_gmail_token.py
