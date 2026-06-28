#!/usr/bin/env bash
# Run the full test suite with coverage.
# Usage: ./scripts/test.sh [pytest args...]
set -euo pipefail

cd "$(dirname "$0")/.."

if ! command -v pytest &>/dev/null; then
    echo "pytest not found — run: pip install -r requirements-dev.txt"
    exit 1
fi

pytest tests/ -q "$@"
