# MailSync — All-Night Coding Session Handoff

**Last updated:** 2026-06-27
**Branch:** `development` (5 commits ahead of where `main` will start)
**Test count:** 90 passing (+ 7 UI smoke tests in test_screens.py)
**Current version:** v0.5.0

---

## Read This First — Project Context

MailSync is a Python + Kivy Android app that migrates email from Yahoo Mail
to Microsoft Outlook 365 via IMAP read + Microsoft Graph API write. Yahoo
doesn't offer free forwarding, so this app syncs continuously.

This is a **portfolio piece** — every decision prioritizes code quality,
architecture, and demonstrating real engineering over hacks. The target has
always been 9/10+ across the board.

**Before touching anything**, read these files in this order:
1. `CLAUDE.md` — branch protocol, module map, dependency rules
2. `DESIGN.md` — architecture, auth flows, sync engine, database schema
3. `CLAUDE_REVIEW.md` — honest current state and v0.6 priorities
4. `RELEASE_NOTES.md` — full history of what was built and when

---

## ONE MANUAL STEP REQUIRED FIRST

**The user must run this before any coding session starts:**

```bash
cd /path/to/MailSync
git checkout -b main 6c64247 && git push -u origin main && git checkout development
```

This creates the `main` branch at the initial commit so a PR can be opened
(`development → main`). Without this, no PR is possible. This has been blocked
by CI/safety hooks in every previous session — only the user can do it manually.

After main exists, open the PR:
```bash
gh pr create --base main --head development \
  --title "MailSync v0.5.0 — Yahoo → Outlook email migration app" \
  --body "$(cat <<'EOF'
## Summary

- Full Yahoo → Outlook email migration app (Python + Kivy, Android APK)
- IMAP + App Password auth for Yahoo; MSAL Device Code Flow for Microsoft
- Sync engine with UID tracking, 3-tier dedup, partial failure recovery
- IMAP IDLE push notification (RFC 2177) — new mail triggers sync within seconds
- BOOT_COMPLETED BroadcastReceiver (Java) — service restarts after device reboot
- Encrypted credential storage (Fernet + PBKDF2 device-bound key)
- 90 unit tests, all network calls mocked; headless Kivy UI smoke tests in CI

## Test plan

- [ ] All 90 tests passing in CI
- [ ] UI smoke tests pass (test_screens.py)
- [ ] APK builds in android.yml CI
- [ ] Physical device: IMAP IDLE fires on new mail
- [ ] Physical device: BOOT_COMPLETED restarts service after reboot

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Current Architecture (Quick Reference)

```
6 layers, strict dependency direction (lower never imports upper):

constants → database → crypto → token_store → auth → sync → ui → main

Key modules:
  auth/credential_validator.py  — startup IMAP ping + MSAL token check
  auth/microsoft_auth.py        — MSAL Device Code Flow + SerializableTokenCache
  auth/yahoo_auth.py            — IMAP4_SSL connect + validate
  sync/imap_idle.py             — RFC 2177 IDLE monitor (EXISTS push)
  sync/sync_engine.py           — 3-tier dedup: initial skip → cache → API
  sync/scheduler.py             — desktop threading scheduler (fires immediately)
  service/sync_service.py       — Android service: sync + IDLE + SIGTERM
  src/BootReceiver.java         — BOOT_COMPLETED BroadcastReceiver
  extras/boot_receiver.xml      — manifest <receiver> fragment
```

---

## What's Already Built (DO NOT REBUILD)

Every item below is complete, tested, and committed. Do not re-implement.

- [x] Yahoo IMAP auth (App Password), credential validator, token store
- [x] Microsoft MSAL Device Code Flow, SerializableTokenCache encrypted at rest
- [x] Sync engine: UID tracking, 3-tier dedup, dry-run mode, partial failure recovery
- [x] IMAP IDLE (RFC 2177) push monitor with reconnect + keepalive
- [x] BOOT_COMPLETED Java BroadcastReceiver + buildozer wiring
- [x] SQLite schema with migration (pending_emails column)
- [x] Fernet + PBKDF2 device-bound credential encryption
- [x] Kivy UI: HomeScreen, ConnectScreen, HistoryScreen, SettingsScreen
- [x] Home screen: startup credential ping, error detail label, Check Pending (dry-run)
- [x] Settings: configurable sync interval (5 options), disconnect confirmation popup
- [x] Background service: IDLE push + interval fallback + SIGTERM clean stop
- [x] CI: GitHub Actions (pytest + headless Kivy), Android APK build workflow
- [x] 90 tests: crypto, database, auth, yahoo_reader, outlook_writer, sync_engine,
       scheduler, credential_validator, imap_idle
- [x] Docs: DESIGN.md, README.md, RELEASE_NOTES.md, CLAUDE_REVIEW.md, CLAUDE.md,
       ANDROID_BUILD.md, DEPLOYMENT.md

---

## The All-Night Build List — v0.6.0

Work these in order. Each phase is independent enough to commit separately.
Do not skip phases — each one builds on the last.

---

### PHASE 1 — Ship the PR + CI Hardening (do this first)

**Goal:** CI is fully green and hard-gated. PR is open.

#### 1A. Open PR (after user creates main branch — see above)
- Run the `gh pr create` command above

#### 1B. Harden Kivy CI (`ci.yml`)
- Cache the Kivy install so it doesn't reinstall every run
- Remove `|| true` from the UI smoke test step — make it a hard gate
- Add `pip cache` action step before installs
- Split into two jobs: `test-logic` (fast, no Kivy) and `test-ui` (Kivy, cached)

```yaml
# Cache key:
key: kivy-${{ runner.os }}-${{ hashFiles('requirements.txt') }}
```

#### 1C. `.github/pull_request_template.md`
Create this file:
```markdown
## Checklist
- [ ] All 5 docs updated (RELEASE_NOTES, README, DESIGN, CLAUDE_REVIEW, CLAUDE.md)
- [ ] Version bumped in constants.py and buildozer.spec
- [ ] Tests pass: `pytest tests/ -q`
- [ ] No `.env` or credentials committed
- [ ] CLAUDE_REVIEW.md rating updated
```

---

### PHASE 2 — Android Notification Channels + Foreground Service (critical for Android 8+)

**Goal:** Notifications actually work on modern Android. Without notification
channels, `android.notifications.notify()` silently does nothing on Android 8+.

#### 2A. `service/notification_helper.py` (new file)
```python
# Create a notification channel on Android 8+, send notifications through it
# Also handles the foreground service notification (required by Android 9+)
```

Implement:
- `create_channel()` — creates `mailsync_sync` notification channel (IMPORTANCE_LOW)
- `send_notification(title, body)` — posts to the channel
- `start_foreground(service_context)` — posts the persistent "MailSync active" notification
  that keeps the foreground service alive on Android 9+

#### 2B. Update `service/sync_service.py`
- Import and call `notification_helper.create_channel()` at startup
- Replace `_notify()` calls with `notification_helper.send_notification()`
- Call `notification_helper.start_foreground()` on service start

#### 2C. Tests
- `tests/test_notification_helper.py` — mock Android imports, test channel creation + notification send

---

### PHASE 3 — IDLE Connection Status on Home Screen

**Goal:** Make the IDLE feature visible. User sees "Live" vs "Polling" mode.

#### 3A. Add IDLE status to `home_screen.py`
- Add a `StatRow(label="Sync mode")` to the stats panel
- On `on_enter()`, check if `_yahoo_email` exists and attempt to determine if IDLE is active
- Show: `"Live (IDLE)"` if last sync was < 30s ago (IDLE is working), `"Polling"` otherwise,
  `"—"` if no account connected

#### 3B. Add `idle_connected` stat to `sync_state` table
- Add column `idle_last_seen TEXT` — updated by the service when IDLE fires
- `home_screen._refresh_stats()` reads this to show "Live" if it's recent

Actually simpler: just read `last_sync_at` — if it's within 2x the configured interval, IDLE is healthy.

---

### PHASE 4 — Reconnect Prompt on Auth Failure

**Goal:** When startup credential ping fails, show actionable UI instead of just red text.

#### 4A. Update `home_screen._apply_yahoo_validity()` and `_apply_ms_validity()`
- Instead of just calling `_show_detail(error)`, also render a `Button("Reconnect →", ...)`
- Button navigates to `connect_screen`
- Button only appears when that specific account is connected but failing

#### 4B. Connect screen improvements
- Add a "Re-authenticate" header when arriving with an existing account
- Pre-fill Yahoo email field if account exists (password still blank for security)
- Show "Update credentials" instead of "Connect" in the button text

---

### PHASE 5 — E2E Tests with Dovecot IMAP in Docker

**Goal:** One honest integration test that doesn't use mocks. Proves the IMAP
stack actually works against a real server.

#### 5A. `docker-compose.test.yml`
```yaml
services:
  imap:
    image: dovecot/dovecot:latest
    ports: ["993:993"]
    volumes:
      - ./tests/e2e/dovecot:/etc/dovecot/conf.d
```

#### 5B. `tests/e2e/` directory
- `conftest.py` — `pytest.mark.e2e` marker, `skip if Docker not available`
- `test_yahoo_imap_e2e.py` — real IMAP connect, send test message, read it back
- `test_idle_e2e.py` — connect IDLE monitor to Dovecot, inject message via APPEND, verify callback fires

#### 5C. CI update (`ci.yml`)
- Add a third job `test-e2e` with `services: imap: image: dovecot/dovecot`
- Runs `pytest tests/e2e/ -m e2e -q`
- Skipped on PRs where Docker service setup would add > 3 min to CI

---

### PHASE 6 — Sync History Mini-Chart

**Goal:** Replace plain stats rows with a 7-day visual bar chart.

#### 6A. `ui/widgets/history_chart.py` (new Kivy widget)
```python
class HistoryChart(Widget):
    # 7 bars (Mon–Sun), height proportional to emails_synced that day
    # Kivy canvas: Rectangle for each bar, Label for day abbreviation
    # Color: STATUS_OK if > 0 synced, STATUS_IDLE if 0
```

#### 6B. Add to `home_screen.py`
- Add `HistoryChart()` below the health gauge
- Populate from `database.get_sync_stats_by_day(state["id"], days=7)` (new DB function)

#### 6C. `database.get_sync_stats_by_day()`
```python
def get_sync_stats_by_day(sync_state_id: int, days: int = 7) -> list[dict]:
    # Returns [{date: "2026-06-21", emails_synced: 14}, ...]
```

---

### PHASE 7 — Version Bump + All Docs + Push

**Goal:** Everything committed, CI green, PR updated.

#### 7A. Bump version to v0.6.0
- `core/constants.py`: `APP_VERSION = "0.6.0"`
- `buildozer.spec`: `version = 0.6.0`

#### 7B. Update all 5 required docs
- `RELEASE_NOTES.md` — full v0.6.0 changelog
- `README.md` — feature table updated, test count updated
- `DESIGN.md` — notification channel architecture, E2E test section
- `CLAUDE_REVIEW.md` — new ratings (target: 9.8/10 overall), v0.7 priorities
- `CLAUDE.md` — module map updated (notification_helper, history_chart, e2e/)

#### 7C. Push and confirm CI
```bash
git push origin development
# Wait for CI green, then PR is ready to merge
```

---

## Projected Final State After All-Night Session

| Category | v0.5 | v0.6 target |
|---|---|---|
| Architecture | 9/10 | 9/10 |
| Security | 9/10 | 9/10 |
| Code quality | 9/10 | 9/10 |
| Test coverage | 9/10 | 10/10 (E2E Dovecot) |
| Documentation | 9/10 | 10/10 |
| Sync correctness | 9/10 | 9/10 |
| Android integration | 9/10 | 10/10 (notification channels, foreground notif) |
| UX polish | 9/10 | 10/10 (IDLE indicator, reconnect prompt, history chart) |
| Portfolio value | 10/10 | 10/10 |
| **Overall** | **9.2** | **9.7** |

---

## What the Session Cannot Do (Needs Physical Device)

These must be verified by the user on a real Android device after APK install:

- [ ] IMAP IDLE fires within 10s of new Yahoo email
- [ ] BOOT_COMPLETED restarts service after reboot (`adb logcat -s MailSyncBoot`)
- [ ] Notification appears in Android notification tray
- [ ] Foreground service notification visible in status bar
- [ ] "Open Outlook →" button launches Outlook or Play Store
- [ ] APK installs and launches without crash

---

## Key Commands for the Session

```bash
# Run tests (excluding UI smoke tests)
python -m pytest tests/ -q --ignore=tests/test_screens.py

# Run with UI smoke tests (needs Kivy installed)
SDL_VIDEODRIVER=offscreen python -m pytest tests/ -q

# Run only E2E tests (needs Docker)
pytest tests/e2e/ -m e2e -q

# Push
git push origin development

# Check CI status
gh run list --branch development --limit 5

# Build APK locally (if buildozer installed)
./scripts/build-apk.sh
```

---

## File Locations Quick Reference

```
/home/kakoritz/nas-Data/Documents/vscode/MailSync/
├── core/constants.py          ← APP_VERSION lives here
├── buildozer.spec             ← version = X.Y.Z lives here
├── tests/                     ← all pytest tests
├── tests/e2e/                 ← create this for E2E tests
├── service/                   ← Android background service
├── src/                       ← Java source (BootReceiver.java)
├── extras/                    ← manifest fragments (boot_receiver.xml)
├── scripts/test.sh            ← run pytest
├── scripts/build-apk.sh       ← run buildozer
└── .github/workflows/         ← ci.yml + android.yml
```

---

## Session Protocol

Follow the CLAUDE.md rules exactly:
- All work on `development` branch — never commit to `main`
- Run `pytest tests/ -q` before every commit
- Update all 5 docs before the final push
- No credentials, no `.env` committed
- Version bumped in both `constants.py` and `buildozer.spec`

Good luck. The foundation is solid — this session is about polish and completeness.
