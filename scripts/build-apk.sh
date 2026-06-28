#!/usr/bin/env bash
# Build a debug APK via buildozer.
# Requires MAILSYNC_CLIENT_ID to be set.
# Usage: ./scripts/build-apk.sh
set -euo pipefail

cd "$(dirname "$0")/.."

: "${MAILSYNC_CLIENT_ID:?MAILSYNC_CLIENT_ID must be set}"

if ! command -v buildozer &>/dev/null; then
    echo "buildozer not found — see ANDROID_BUILD.md for setup instructions."
    exit 1
fi

buildozer android debug
echo ""
echo "APK: $(find bin/ -name '*.apk' | head -1)"
