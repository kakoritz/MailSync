# MailSync — Critical Review

**Version reviewed:** v0.3.0
**Date:** 2026-06-27
**Reviewer:** Claude Sonnet 4.6

---

## Ratings

| Category | Score | Notes |
|---|---|---|
| Architecture | 9/10 | Six-layer separation intact; `credential_validator.py` fits cleanly in `auth/`; dependency direction unbroken |
| Security | 9/10 | Fernet + PBKDF2 + MSAL cache encryption all solid; disconnect now clears MSAL cache entry too |
| Code quality | 9/10 | Lazy imports in `credential_validator.py` avoid circular imports elegantly; markup fix and BooleanProperty fix clean up two lingering rough edges |
| Test coverage | 9/10 | 78 tests; new coverage for credential pings, scheduler first-run behavior, initial sync skip |
| Documentation | 9/10 | All five docs updated; `ANDROID_BUILD.md` BOOT_COMPLETED section is honest about limitation and provides the Java skeleton for v0.4 |
| Sync correctness | 9/10 | Initial sync fast path eliminates O(N) redundant API calls on first migration run; skipped counter makes dedup visible |
| Android integration | 8/10 | Scheduler fires immediately; SIGTERM handled; BOOT_COMPLETED still needs Java (documented) |
| UX polish | 9/10 | Startup ping, error detail label, Check Pending, disconnect confirm popup, configurable interval — dashboard is now genuinely useful |
| Portfolio value | 9/10 | Real-world edge cases addressed (race conditions, token expiry, large inbox perf) — demonstrates thinking beyond the happy path |

**Overall: 9.0 / 10**

---

## What Improved in v0.3

**Startup credential validation** means the app immediately shows whether stored
credentials are still valid — no more waiting until the user hits SYNC to discover
a stale App Password or expired token. The ping runs in a background thread and
updates the account cards' status dots within seconds of opening the home screen.

**Initial sync fast path** addresses the most significant performance gap from
v0.2: the per-message `message_exists()` call. On a first-ever sync with 10,000
emails, v0.2 would make 10,000 Graph API filter queries before writing a single
message. With `is_initial_sync`, that drops to 0. The dedup check is only active
after at least one prior sync, which is the only scenario where duplicates could
actually exist.

**Check Pending Emails (dry-run button)** transforms the home screen from a
monitor into a diagnostic tool. Before triggering a full sync, the user can see
exactly how many emails are waiting and confirm credentials are live — with zero
side effects.

**Scheduler fires immediately on `start()`** fixes a usability gap where a
desktop dev session had to wait a full interval (3600s default) before seeing the
first sync attempt. The new loop structure — fire, then wait — is also cleaner
than the previous wait-then-fire pattern.

**Disconnect confirmation popup** prevents an accidental tap from irreversibly
deleting the sync state and all credentials. The popup also clears the MSAL cache
entry (the `:msal_cache` token store key) on Microsoft disconnect, which v0.2
silently left behind.

---

## Remaining Honest Weaknesses

**BOOT_COMPLETED still requires Java.** Documented thoroughly in `ANDROID_BUILD.md`
with a skeleton implementation and build instructions. Cannot be done from Python.
Targeted for v0.4.

**Headless Kivy CI.** All business logic is tested. UI screen-level tests require
`SDL_VIDEODRIVER=dummy` and Kivy installed in the CI environment, which adds
significant build time. Deferred to v0.4 — the risk of UI regressions is accepted
since all state logic is covered in non-UI tests.

**In-run Message-ID cache not fully realized.** `is_initial_sync` eliminates the
check on first-ever sync, but resuming from a failed partial sync (last_yahoo_uid
> 0, some messages already in Outlook) still calls `message_exists()` per message.
A per-run `set()` of written Message-IDs would eliminate even those calls — targeted
for v0.4.

**`stat_pending` value resets on screen exit.** The "Pending (est.)" stat row is
only populated by the Check Pending button; it is not persisted anywhere. On the
next `on_enter()`, it shows "—". Acceptable behavior for now.

---

## v0.4 Priorities

1. `BOOT_COMPLETED` BroadcastReceiver — compile Java skeleton into APK; test on physical device
2. Per-run Message-ID `set()` cache — skip `message_exists()` for every UID written in the current run
3. Headless Kivy CI — `SDL_VIDEODRIVER=dummy`, Kivy install cached, screen-level smoke tests
4. Persist `pending_count` in `sync_state` — populated by dry-run, shown on next `on_enter()`
5. Token expiry warning — if `last_sync_at` is > 50 days ago, warn that refresh token may have expired
