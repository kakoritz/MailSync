# CLAUDE.md — MailSync Project Instructions

Standard protocol for every code change. No exceptions.

---

## Branch & Push Protocol

- **All work on `development`** — never commit directly to `main`
- `main` is the release branch — protected, requires PR to merge
- CI runs `pytest tests/ -q` on every push to `development` and every PR to `main`
- Open PR only when CI is green and all five docs are updated

### Docs to update before every PR

| File | Purpose |
|------|---------|
| `RELEASE_NOTES.md` | Changelog entry (Added / Changed / Fixed) |
| `README.md` | Feature list, setup guide — keep current |
| `DESIGN.md` | Architecture and design intent |
| `CLAUDE_REVIEW.md` | Honest critical review + rating update |
| `CLAUDE.md` | This file — update if protocol changes |

Version format: `v0.MAJOR.MINOR` — bump MINOR for any visible change.

---

## Project Facts

- **Language**: Python 3.10+
- **UI**: Kivy 2.3+
- **Android**: Buildozer + python-for-android
- **Auth**: Yahoo IMAP App Password · Microsoft MSAL Device Code Flow
- **Storage**: SQLite3 (stdlib) — `mailsync.db` in `MAILSYNC_DATA_DIR`
- **Encryption**: `cryptography.fernet.Fernet` — all credentials encrypted at rest
- **Tests**: pytest, all network calls mocked

---

## Module Map

```
main.py                 App bootstrap + ScreenManager
service/
  sync_service.py       Android background service (hourly sync)
core/
  constants.py          App-wide constants — no logic
  config.py             JSON settings persistence
  database.py           SQLite CRUD — accounts, sync_state, sync_log
  app_state.py          State machine enum + AppState class
security/
  crypto.py             Fernet key derivation + encrypt/decrypt
auth/
  yahoo_auth.py              IMAP connect + validate credentials
  microsoft_auth.py          MSAL Device Code Flow + token refresh
  token_store.py             Encrypted credential read/write via database
  credential_validator.py    Lightweight startup ping for both services
sync/
  yahoo_reader.py       Fetch messages from Yahoo IMAP by UID
  outlook_writer.py     POST RFC822 to Microsoft Graph API
  sync_engine.py        Orchestrates one sync pass; owns UID tracking + initial-sync fast path
  scheduler.py          Desktop threading scheduler (fires immediately then every interval)
  imap_idle.py          RFC 2177 IMAP IDLE push monitor — fires callback on EXISTS notification
ui/
  theme.py              All colors, font sizes, spacing — single source of truth
  screens/
    home_screen.py      Dashboard: account cards, SYNC + Check Pending, stats, error detail
    connect_screen.py   Yahoo + Microsoft connection flows
    history_screen.py   Sync log table
    settings_screen.py  Disconnect (with confirm popup), configurable interval, history nav
  widgets/
    account_card.py     Reusable account status card
    sync_button.py      Animated SYNC NOW button
    stat_row.py         Label + value row for stats panel
    health_gauge.py     Progress bar health indicator
    open_outlook_btn.py Android Intent launcher (BooleanProperty android_available)
scripts/
  test.sh               Run pytest
  build-apk.sh          Run buildozer android debug
tests/
  test_crypto.py
  test_database.py
  test_auth.py
  test_yahoo_reader.py
  test_outlook_writer.py
  test_sync_engine.py
  test_scheduler.py
  test_credential_validator.py
  test_imap_idle.py
```

## Dependency Rule

```
constants.py      → nothing
database.py       → constants
crypto.py         → nothing (stdlib + cryptography)
token_store.py              → database, crypto
yahoo_auth.py               → token_store, constants
microsoft_auth.py           → token_store, constants
credential_validator.py     → token_store, yahoo_auth, microsoft_auth (lazy imports to avoid circular)
yahoo_reader.py             → yahoo_auth
outlook_writer.py           → microsoft_auth, constants
sync_engine.py              → yahoo_reader, outlook_writer, database
scheduler.py                → constants (no sync imports at module level)
ui/                         → core, sync, auth (never the reverse)
main.py                     → everything
```

---

## Security Rules

- No plaintext credentials in logs, config files, or memory beyond immediate use
- `del` sensitive strings after encryption (best-effort in Python)
- `MAILSYNC_CLIENT_ID` set via environment variable, never hardcoded
- `.salt` and `mailsync.db` are gitignored — never commit them
- The global `secret-scanner.sh` hook runs on every Write

---

## Environment Variables

| Variable | Purpose |
|---|---|
| `MAILSYNC_DATA_DIR` | Directory for `mailsync.db`, `mailsync_config.json`, `.salt` |
| `MAILSYNC_CLIENT_ID` | Azure App Registration client ID |

---

## Android Build

See `ANDROID_BUILD.md` for full local + CI build guide.

Key points:
- `buildozer.spec` sets `build_dir = /home/kakoritz/.mailsync-build`
- CI: GitHub Actions → `buildozer android debug` → published to `apk-latest` release
- Background service: `android.services = sync:service/sync_service.py`
- Permissions: INTERNET, RECEIVE_BOOT_COMPLETED, FOREGROUND_SERVICE, WAKE_LOCK, POST_NOTIFICATIONS

---

## Code Style

- No comments unless the WHY is genuinely non-obvious
- No `.env` ever committed
- All theme values in `ui/theme.py` — never inline
- State transitions are explicit string constants (IDLE, SYNCING, etc.)
- Tests mock all network calls — no live IMAP or Graph API in CI
