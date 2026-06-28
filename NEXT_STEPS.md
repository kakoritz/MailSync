# MailSync — Next Steps

**Last updated:** 2026-06-28
**Current version:** v0.6.0
**Branch:** `development` (PR #1 open → `main`, CI green)
**Test count:** 102 unit + 9 E2E (all passing in CI)

---

## Current State

v0.6.0 is complete and CI is fully green across all three jobs:

| Job | Status | What it tests |
|---|---|---|
| `test-logic` | ✓ green | 102 unit tests, no Kivy, no Docker |
| `test-e2e` | ✓ green | 9 E2E tests against Dovecot IMAP in Docker |
| `test-ui` | ✓ green | 7 Kivy smoke tests (headless, hard-gated) |

PR #1 (`development → main`) is open. Merge when ready to cut a release.

---

## What Was Built (DO NOT REBUILD)

Everything below is complete, tested, committed, and CI-verified.

- [x] Yahoo IMAP auth, MSAL Device Code Flow, encrypted token store
- [x] Sync engine: 3-tier dedup, dry-run, partial failure recovery
- [x] IMAP IDLE (RFC 2177) push monitor + keepalive + reconnect backoff
- [x] BOOT_COMPLETED BroadcastReceiver (Java)
- [x] Android notification channels + foreground service notification (API 26+/28+)
- [x] IDLE connection status on home screen ("Live (IDLE)" / "Polling")
- [x] Reconnect prompt on auth failure + connect screen re-auth mode
- [x] 7-day sync history bar chart (Kivy canvas widget)
- [x] E2E tests: Dovecot in Docker, `fetch_uids_since`, `iter_new_messages`, `IdleMonitor`
- [x] CI: 3-job split, pip cache, Kivy hard-gated, E2E with real Dovecot
- [x] All 5 docs updated: RELEASE_NOTES, README, DESIGN, CLAUDE_REVIEW, CLAUDE.md

---

## v0.7 Priorities

Work these in order if continuing development.

### PHASE 1 — Merge PR + Physical Device Validation

**Goal:** Ship v0.6.0 to APK and verify on a real Android device.

Merge PR #1 → triggers `android.yml` → APK published to `apk-latest` release.

Device verification checklist (cannot be done in CI):
- [ ] Notification appears in Android notification tray after sync
- [ ] Foreground service notification visible in status bar
- [ ] IMAP IDLE fires within 10s of new Yahoo email arriving
- [ ] BOOT_COMPLETED restarts service after device reboot (`adb logcat -s MailSyncBoot`)
- [ ] APK installs and launches without crash on Android 8+ device

### PHASE 2 — Per-UID Watermark (skip tier-3 dedup above known-clean UID)

**Goal:** Eliminate the `message_exists()` Graph API call for UIDs that were
written in the current session — we know they're new, no API check needed.

- Add `last_clean_uid` to `sync_state` — updated to the current run's highest written UID
- In `sync_engine`, skip `message_exists()` for `uid > last_clean_uid`
- Only fall through to tier-3 API check for UIDs that could overlap with previous runs

### PHASE 3 — Kivy UI Integration Tests (beyond smoke tests)

**Goal:** Test actual user flows, not just widget instantiation.

- Simulate button taps with `widget.dispatch('on_release')`
- Test home screen → connect screen navigation
- Test sync button state transitions (idle → syncing → done)
- Test settings disconnect flow (confirm popup → account removed → card shows disconnected)

### PHASE 4 — Sync State Export / Import

**Goal:** Move sync state to a new device without losing the migration checkpoint.

- `database.export_sync_state()` → JSON with `yahoo_email`, `outlook_email`, `last_yahoo_uid`
- UI: "Export state" button in settings → saves to Downloads
- UI: "Import state" button → reads JSON, calls `get_or_create_sync_state` with seeded UID
- Does NOT export credentials (those must be re-entered on the new device)

### PHASE 5 — Version Bump + Docs + Push

- Bump `APP_VERSION` to `0.7.0` in `core/constants.py` and `buildozer.spec`
- Update all 5 docs
- Push and confirm CI green

---

## Key Commands

```bash
# Run unit tests
python3 -m pytest tests/ -q --ignore=tests/test_screens.py

# Run E2E tests (requires Docker)
docker compose -f docker-compose.test.yml up -d
pytest tests/e2e/ -m e2e -q

# Check CI
gh run list --branch development --limit 5

# Merge PR (when ready)
gh pr merge 1 --merge

# Check APK build after merge
gh run list --branch main --limit 3
```

---

## Module Map Quick Reference

```
service/notification_helper.py  — Android notification channels (new in v0.6)
core/database.py                — idle_last_seen, get_sync_stats_by_day (new in v0.6)
ui/widgets/history_chart.py     — 7-day Kivy canvas bar chart (new in v0.6)
ui/screens/home_screen.py       — stat_sync_mode, history_chart, reconnect btns (v0.6)
ui/screens/connect_screen.py    — on_enter re-auth mode (new in v0.6)
tests/e2e/                      — Dovecot IMAP E2E tests (new in v0.6)
```
