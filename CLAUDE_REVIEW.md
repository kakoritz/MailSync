# MailSync — Critical Review

**Version reviewed:** v0.1.0
**Date:** 2026-06-27
**Reviewer:** Claude Sonnet 4.6

---

## Ratings

| Category | Score | Notes |
|---|---|---|
| Architecture | 9/10 | Clean six-layer separation; dependency rule enforced |
| Security | 8/10 | Fernet + PBKDF2 is solid; memory hygiene is best-effort in Python |
| Code quality | 9/10 | Single-responsibility modules; no god files |
| Test coverage | 8/10 | All business logic covered; UI untested (Kivy headless is painful) |
| Documentation | 9/10 | DESIGN.md is thorough; ANDROID_BUILD.md covers the sharp edges |
| Sync correctness | 9/10 | UID-based tracking + idempotency check is right; edge case noted below |
| Android integration | 8/10 | Background service pattern is correct; OSC comms is fragile |
| Portfolio value | 9/10 | Real auth flows, real API, real device crypto — demonstrates depth |

**Overall: 8.6 / 10**

---

## What's Strong

**UID-based sync tracking** is the right call. IMAP UIDs are stable across
reconnections (unlike sequence numbers), and storing `last_yahoo_uid` in SQLite
means the migration checkpoint survives everything short of the database being
deleted. The `first_sync_at` column being set-once-never-updated is a good detail.

**Idempotency via Message-ID check** is correct and necessary. A sync run that
crashes halfway through will retry, and without the duplicate check those messages
would appear twice in Outlook. The check adds one Graph API call per message but
that's the right trade-off.

**Fernet + PBKDF2 with 260k iterations** is a reasonable credential storage
approach for a personal app. The device fingerprint binding means the database
file isn't useful on another machine.

**Six-layer module structure** with an enforced dependency rule is the right call
for a project this size. It prevents test pollution (sync logic doesn't need Kivy
to run) and makes each layer independently replaceable.

---

## Honest Weaknesses

**OSC for service→UI communication is fragile.** If the UI isn't running when
the service finishes a sync, the notification fires but the stats panel doesn't
update until the user opens the app. This is acceptable for v0.1 but should be
replaced with a shared SQLite read (which the UI already polls on `on_enter`).

**MSAL token cache isn't wired.** The `PublicClientApplication` instance is
re-created on every token call. MSAL's built-in token cache isn't being persisted
between calls, so `acquire_token_silent` will always miss unless the cache is
serialized. This means more refresh token round-trips than necessary. This should
be fixed in v0.2 by serializing the MSAL token cache to the encrypted store.

**No rate limiting on Graph API.** If a large inbox (thousands of emails) is being
migrated for the first time, the Graph API will eventually 429. The writer doesn't
implement exponential backoff. Acceptable for v0.1 (single-user, personal inbox)
but needs addressing before any wider use.

**Kivy UI is not tested.** The ScreenManager, widgets, and screen logic are
excluded from CI. This is the norm for Kivy apps (headless Kivy in CI is complex)
but it means visual bugs won't be caught automatically.

**`service/sync_service.py` opens IMAP once per sleep cycle.** For an hourly sync
with a modest inbox this is fine, but it's slightly wasteful. Not a real problem
at this scale.

---

## v0.2 Priorities

1. Persist MSAL token cache properly
2. Exponential backoff on Graph API 429
3. Replace OSC with database-polling for service→UI stats refresh
4. Add `--dry-run` flag to sync engine for safe testing against live accounts
5. Handle Yahoo IMAP `EXPUNGE` events (deleted messages shouldn't block UID advance)
