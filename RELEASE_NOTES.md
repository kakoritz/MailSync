# Release Notes

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
