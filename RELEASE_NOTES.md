# Release Notes

---

## v0.3.0 — 2026-06-27

### Added

- **Startup credential validation** — on every home screen entry, background pings verify both Yahoo IMAP and Microsoft token validity; cards show `Auth failed` immediately if credentials have gone stale, with detail label showing the specific error
- **Check Pending Emails button** — dry-run scan from the home screen shows how many emails are waiting to migrate before committing a full sync; result displayed in new "Pending (est.)" stat row
- **Initial sync fast path** — when `last_yahoo_uid == 0` (first-ever sync), the per-message `message_exists()` Graph API check is skipped entirely; Outlook is guaranteed empty so no dedup check is needed; saves N API calls on initial migration of a large inbox
- **`emails_skipped` counter** on `SyncResult` — tracks messages that were deduped and not re-imported
- **Configurable sync interval** — Settings screen now offers 15 min / 30 min / 1 hour / 2 hours / 6 hours selector; saved via `core/config.py`; the Android service reads it on every wake cycle
- **Disconnect confirmation popup** — Kivy `Popup` with cancel/confirm before deleting any credentials; MSAL cache entry is also cleared when disconnecting Microsoft
- **Scheduler fires immediately on start()** — no more waiting a full interval before the first background sync
- **SIGTERM handler in background service** — clean stop; 10-second sleep slices allow prompt response to OS kills
- `requirements-dev.txt` — pytest moved out of `requirements.txt` into a dev-only file
- `scripts/test.sh` and `scripts/build-apk.sh` — developer convenience scripts
- `.env.example` — documents all required and optional environment variables
- `auth/credential_validator.py` — new module with `ping_yahoo()` and `ping_microsoft()` functions

### Fixed

- `ui/widgets/open_outlook_btn.py` — `android_available` is now a proper Kivy `BooleanProperty` so KV bindings fire correctly when the value changes
- `ui/screens/connect_screen.py` — `markup=True` is now set at widget creation time, not after the text assignment; prevents [b] tags from rendering as literal text on first display
- `ui/screens/settings_screen.py` — moved to `ScrollView`-based layout; settings visible on small screens

### Tests

- 78 tests (up from 62) — new coverage: `test_credential_validator.py` (8 tests), `test_scheduler.py` (5 tests), `test_sync_engine.py` +3 (initial sync skip, subsequent sync calls exists, skipped counter); fixed 2 existing tests to seed non-zero UID where `is_initial_sync=False` is required

---

## v0.2.0 — 2026-06-27

### Added

- **Dry-run mode** — `run_sync(..., dry_run=True)` fetches and counts pending emails without writing to Outlook or updating any database state; useful for verifying credentials against a live account
- **Exponential backoff on Graph API 429 / 5xx** — retries up to 3 times with Retry-After header respected; no more hard failures on transient rate limits
- **MSAL token cache serialization** — MSAL's `SerializableTokenCache` is now encrypted and persisted between process restarts; silent token refresh survives app closes and background service restarts
- **EXPUNGE safety in Yahoo reader** — UIDs that were deleted between SEARCH and FETCH (NIL response) are now skipped with a warning instead of raising; sync continues uninterrupted

### Changed

- `poll_device_flow` signature simplified: `timeout_seconds` parameter removed (MSAL handles the flow timeout internally)
- `service/sync_service.py` — removed fragile OSC IPC; UI now refreshes stats by reading the database directly on screen entry
- `sync/yahoo_reader.py` — now uses stdlib `logging` instead of `kivy.logger` so the module is importable outside the Android/Kivy environment
- `main.py` — removed unused `BroadcastReceiver` import

### Fixed

- `outlook_writer.py` — removed dead code block (unused `json` import, duplicate payload variables, orphaned `base64.b64encode` call)
- `health_gauge.py` — `gauge_color` is now a proper Kivy `ColorProperty` with an `on_health_pct` observer; previously it was a plain Python `@property` that Kivy's KV bindings could not observe
- `microsoft_auth.py` — removed unused `time` import; `_build_app` now accepts an optional `cache` parameter for cache-aware construction

### Tests

- 62 tests (up from 52) — added coverage for: 429 backoff, 500 retry, network exception in `message_exists`, EXPUNGE skip, dry-run semantics (no writes, no log entries, progress callback fires), MSAL cache state-change serialization, device flow error path

---

## v0.1.0 — 2026-06-27

### Added

- **Yahoo Mail authentication** — IMAP + App Password; credentials Fernet-encrypted at rest
- **Microsoft Outlook 365 authentication** — MSAL Device Code Flow; no redirect URI required
- **Account connection screen** — step-by-step flows for both services
- **Home dashboard** — connection status cards, SYNC NOW button, stats panel
- **Sync engine** — UID-based Yahoo → Outlook migration; idempotent, partial-failure safe
- **Persistent sync state** — `last_yahoo_uid` survives app restarts and OS kills
- **Sync statistics** — total emails synced, today count, syncing-since date, health %
- **Background service** — hourly Android sync with push notifications
- **Open Outlook button** — Android Intent launch with Play Store fallback
- **History screen** — last 50 sync log entries with status and email count
- **Settings screen** — disconnect accounts, view history, version info
- **Encrypted credential storage** — device-bound key derivation (PBKDF2 + Fernet)
- **Full test suite** — 40+ pytest tests covering sync engine, auth, database, and crypto
- **CI** — GitHub Actions runs tests on every push to `development`
- **Android APK CI** — buildozer build published to `apk-latest` release on merge to `main`
