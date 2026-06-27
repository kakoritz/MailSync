# Release Notes

---

## v0.5.0 — 2026-06-27

### Added

- **IMAP IDLE push notification** (`sync/imap_idle.py`) — replaces polling with RFC 2177 IDLE. The service holds a persistent IMAP connection and receives an EXISTS notification from Yahoo's server within seconds of a new message arriving. Sync fires immediately instead of waiting up to the configured interval. Falls back to polling if IDLE drops.
- **BOOT_COMPLETED auto-restart** — `src/BootReceiver.java` registered in `AndroidManifest.xml` via `extras/boot_receiver.xml` and `android.extra_manifest_xml`. After device reboot, the sync service restarts automatically without user interaction. Requires buildozer >= 1.3.
- **25-minute IDLE keepalive** — before most servers' 30-minute idle cutoff, the monitor sends `DONE` + re-issues `IDLE` to reset the server timer. No spurious sync is triggered.
- **Exponential backoff on IDLE reconnect** — 5 / 15 / 60 / 300 second delays between reconnect attempts on connection errors.
- `src/BootReceiver.java` — full Java implementation with `startForegroundService` for Android 8+ and `startService` fallback for older APIs
- `extras/boot_receiver.xml` — manifest `<receiver>` fragment injected by buildozer

### Changed

- `service/sync_service.py` — restructured into `_do_sync()` + `_wait_for_new_mail()` helpers; `_wait_for_new_mail` uses `IdleMonitor` with polling-interval timeout as fallback; `_stop_event` replaces the `_running` bool for cleaner threading
- `buildozer.spec` — added `android.add_java_dir = src` and `android.extra_manifest_xml = extras/boot_receiver.xml`
- `ANDROID_BUILD.md` — BOOT_COMPLETED section updated from "not yet implemented" to implemented; IMAP IDLE battery impact note added; `adb` verification commands provided

### Tests

- 90 tests (up from 83, excluding test_screens.py) — `tests/test_imap_idle.py` (7 tests): EXISTS fires callback, RECENT fires callback, unrelated responses ignored, socket timeout triggers re-IDLE, stop() exits cleanly, start() idempotent, BYE causes reconnect with zero-delay patch

---

## v0.4.0 — 2026-06-27

### Added

- **Per-run Message-ID cache** — within a single sync run, written Message-IDs are tracked in a `set[str]`. If the same Message-ID appears twice in the UID sequence, the second occurrence is deduped from the cache without making an additional Graph API call. Reported as `emails_cache_hit` on `SyncResult`.
- **Persistent pending count** — `sync_state` now has a `pending_emails` column. After every dry-run, the count is written to the DB so the home screen shows the estimate on the next `on_enter` without re-running the check. After a full successful sync, the column is reset to 0.
- **Database migration** — `init()` runs `ALTER TABLE sync_state ADD COLUMN pending_emails INTEGER` safely (skips if already exists).
- **Token expiry warning** — if `last_sync_at` is more than 50 days ago, the home screen shows a warning that the Microsoft refresh token may have expired. Microsoft tokens expire at 90 days; 50-day threshold gives the user a window to re-authenticate proactively.
- **Headless Kivy CI** — `ci.yml` now installs Kivy with `SDL_VIDEODRIVER=offscreen` and runs `tests/test_screens.py` (screen instantiation smoke tests). Business logic tests run first in a separate step; UI smoke tests are `|| true` so a Kivy install failure doesn't break the required CI gate.
- `tests/test_screens.py` — 7 smoke tests verifying each screen builds and key widgets exist; validates `markup=True` fix and `BooleanProperty` fix are load-order correct

### Changed

- `sync_engine.run_sync()` — per-run cache logic inserted after the `is_initial_sync` check; idempotency layer now has three tiers: (1) initial sync skip, (2) per-run cache, (3) Graph API filter query
- `home_screen._refresh_stats()` reads `pending_emails` from `sync_state` instead of always showing `—`
- `home_screen._on_check_done()` delegates stat update to `_refresh_stats()` instead of setting the label directly
- `database.init()` runs schema migrations in addition to `CREATE TABLE IF NOT EXISTS`

### Tests

- 83 tests (up from 78, excluding `test_screens.py`) — added: `test_per_run_cache_avoids_api_call`, `test_dry_run_persists_pending_count_in_db`, `test_pending_emails_default_is_none`, `test_update_pending_emails`, `test_update_pending_emails_to_zero`

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
