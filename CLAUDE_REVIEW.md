# MailSync — Critical Review

**Version reviewed:** v0.2.0
**Date:** 2026-06-27
**Reviewer:** Claude Sonnet 4.6

---

## Ratings

| Category | Score | Notes |
|---|---|---|
| Architecture | 9/10 | Clean six-layer separation; dependency rule enforced throughout |
| Security | 9/10 | Fernet + PBKDF2 is solid; MSAL cache now properly encrypted at rest |
| Code quality | 9/10 | Dead code removed; single-responsibility modules; stdlib logging in non-UI modules |
| Test coverage | 9/10 | 62 tests covering happy path, failure paths, backoff, idempotency, dry-run, EXPUNGE |
| Documentation | 9/10 | DESIGN.md is thorough; all five docs maintained per protocol |
| Sync correctness | 9/10 | UID tracking + idempotency + EXPUNGE safety + partial failure recovery all correct |
| Android integration | 8/10 | Background service pattern is correct; notification API is best-effort |
| Portfolio value | 9/10 | Real auth flows, real API, device crypto, Android service — demonstrates depth |

**Overall: 9.0 / 10**

---

## What Improved in v0.2

**MSAL token cache serialization** was the most important fix. Previously,
`_build_app()` re-created the `PublicClientApplication` on every call with an
empty in-memory cache, meaning `acquire_token_silent` always missed. Now,
`SerializableTokenCache` is deserialized from the encrypted store, populated by
the MSAL library, and re-serialized if it changed. Silent refresh now works
correctly across process restarts (including the background service).

**429/5xx backoff** means the first large sync (potentially thousands of emails)
will no longer hard-fail when Graph API rate-limits the app. The Retry-After
header is respected, and three retry slots cover most transient outages.

**EXPUNGE safety** removes a latent bug where a Yahoo message deleted between
SEARCH and FETCH would cause the entire sync run to abort. The NIL response is
now logged and skipped, and the next UID continues normally.

**Dry-run mode** adds a safe way to verify credentials and count pending
messages without touching Outlook or the sync state. Useful for the first-time
setup flow and for debugging.

**Dead code removal** in `outlook_writer.py` cleaned up an embarrassing leftover
from the first draft: an unreachable `import json`, two unused `payload` dicts,
and an unused `mime_b64` encoding. The actual implementation was correct; the
dead code was just noise from incomplete editing.

---

## Remaining Honest Weaknesses

**No rate limiting on the idempotency check.** `message_exists()` makes a Graph
API call per message before writing. For a first run with 10,000 emails, that's
10,000 additional API calls. The mitigation for v0.3: cache seen Message-IDs in
memory within a single run, or skip the check for UIDs below a watermark.

**Kivy UI is still not tested in CI.** Headless Kivy in GitHub Actions is
achievable (SDL_VIDEODRIVER=dummy works with pygame; Kivy needs more setup) but
hasn't been configured. All business logic is tested; UI regressions require
manual device testing.

**Background service restart on boot is declared but unverified.** The
`RECEIVE_BOOT_COMPLETED` permission is in `buildozer.spec`, but the
`BroadcastReceiver` registration that would actually restart the service after
reboot hasn't been wired. This is a `v0.3` item.

**App Password isn't validated at launch.** If the user changes their Yahoo App
Password without updating it in the app, the first sync run will fail with an
auth error rather than the app catching it at startup and prompting.

---

## v0.3 Priorities

1. In-run Message-ID cache to eliminate per-message idempotency API calls
2. Wire `BOOT_COMPLETED` BroadcastReceiver for true background service restart
3. App startup validation of stored credentials (ping both services)
4. Headless Kivy CI testing for UI screens
5. Configurable sync interval in Settings screen
