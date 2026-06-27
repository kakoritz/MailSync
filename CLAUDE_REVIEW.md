# MailSync — Critical Review

**Version reviewed:** v0.4.0
**Date:** 2026-06-27
**Reviewer:** Claude Sonnet 4.6

---

## Ratings

| Category | Score | Notes |
|---|---|---|
| Architecture | 9/10 | Migration path added cleanly; three-tier dedup is elegant and well-documented |
| Security | 9/10 | No changes to security model; still solid |
| Code quality | 9/10 | Per-run cache uses a simple `set` — correct tool, no over-engineering |
| Test coverage | 9/10 | 83 non-UI tests + 7 UI smoke tests; per-run cache test verifies the API call count directly |
| Documentation | 9/10 | All five docs updated; CI change explained; migration rationale clear |
| Sync correctness | 9/10 | Three-tier dedup: initial-skip → cache → API; covers all scenarios correctly |
| Android integration | 8/10 | BOOT_COMPLETED still needs Java — documented, not forgotten |
| UX polish | 9/10 | Pending count survives screen navigation; token expiry warning is proactive |
| Portfolio value | 9/10 | Performance optimization with O(1) cache lookup, DB migration handling, headless CI — all practical senior-level patterns |

**Overall: 9.0 / 10**

---

## What Improved in v0.4

**Per-run Message-ID cache** closes the last significant dedup overhead. The
three-tier strategy is now:
1. `is_initial_sync` — skip all checks on first run (O(1) check, N API calls saved)
2. Per-run `set[str]` cache — O(1) lookup, catches same-ID re-appearances in one run
3. Graph API `message_exists()` — for existing messages on resume after failure

Tier 3 is now called only in the minimal case: a message was already in Outlook
before this run started. All other cases are handled without a network call.

**Persistent pending count** removes the "stat resets on back-press" annoyance.
The dry-run result is written to `sync_state.pending_emails` and read back by
`_refresh_stats()` on every `on_enter`. The count resets to 0 after a successful
sync. The column is nullable so existing rows show `None` (displayed as `—`)
until the user runs a Check Pending or a sync.

**Database migration** was added quietly but correctly. The `ALTER TABLE` approach
with `try/except OperationalError` is exactly how SQLite migrations are done
without a migration framework. It runs in `init()` so all environments (Android,
desktop, CI) pick it up automatically.

**Token expiry warning** is a quality-of-life catch. Microsoft refresh tokens
expire at 90 days of disuse. At 50 days, the home screen warns proactively.
Without this, users discover stale tokens only when a sync fails after weeks
of inactivity — confusing and easy to mistake for a network error.

**Headless Kivy CI** is the final gap in the test strategy. Business logic was
always covered; now screen construction is verified in CI. The `|| true` on the
UI step is an intentional soft gate — a Kivy install failure in CI should not
break the merge gate, but a working install does validate the screens.

---

## Remaining Honest Weaknesses

**BOOT_COMPLETED still requires Java.** Still the biggest real-world gap.
Documented thoroughly; skeleton code provided. Waiting on v0.5.

**Tier 3 still fires on resume-from-failure.** If a sync fails at UID 500 with
last_yahoo_uid=499, the next run starts at 500 again with `is_initial_sync=False`,
so `message_exists()` fires for every message. This is correct — we genuinely
don't know which messages made it to Outlook. A more sophisticated approach would
be to store a per-run "verified clean from UID X" watermark. Deferred.

**UI smoke tests are soft-gated.** The `|| true` means a broken screen build
won't fail CI. This is intentional (Kivy install variability in Ubuntu CI) but
means regressions can slip through if Kivy fails to install rather than tests
failing. Can be hardened once the Kivy CI install is stable.

**No E2E test.** All tests are unit-level with mocks. A test using a real IMAP
test server (e.g. Dovecot in Docker) would catch integration failures. Out of
scope for a personal migration tool but worth noting for portfolio context.

---

## v0.5 Priorities

1. `BOOT_COMPLETED` BroadcastReceiver — compile Java skeleton; test on physical device
2. Per-run "verified clean from UID X" watermark — skip tier-3 check for UIDs above the watermark in the current run
3. Harden Kivy CI — cache Kivy install, remove `|| true`, make UI tests a hard gate
4. E2E test with Dovecot IMAP in Docker (optional — portfolio bonus)
5. IMAP IDLE connection for real-time sync (replaces polling; requires persistent connection management)
