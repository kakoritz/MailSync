# Release Notes

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
