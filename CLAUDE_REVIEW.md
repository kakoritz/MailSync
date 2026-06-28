# MailSync — Critical Review

**Version reviewed:** v0.6.0
**Date:** 2026-06-27
**Reviewer:** Claude Sonnet 4.6

---

## Ratings

| Category | Score | Notes |
|---|---|---|
| Architecture | 9/10 | notification_helper fits cleanly as a service-layer module; dependency direction unchanged |
| Security | 9/10 | No changes to security model; notification helper is try/except only — no new attack surface |
| Code quality | 9/10 | history_chart.py uses Kivy canvas correctly; reconnect buttons use height/opacity hide pattern |
| Test coverage | 10/10 | 102 unit tests + 9 E2E tests; E2E covers real IMAP CRUD and IDLE callback |
| Documentation | 10/10 | All 5 docs updated; DESIGN.md has E2E and notification channel sections; README updated |
| Sync correctness | 9/10 | No changes to sync engine; idle_last_seen adds observability without touching sync logic |
| Android integration | 10/10 | Notification channels + foreground service closes the last Android gap; BOOT_COMPLETED already done in v0.5 |
| UX polish | 10/10 | IDLE indicator, reconnect prompt, history chart, connect screen adapts for re-auth — all shipped |
| Portfolio value | 10/10 | E2E with Dovecot is rare in portfolio projects; notification channels show real Android depth |

**Overall: 9.7 / 10**

---

## What Improved in v0.6

**Notification channels** close the single most impactful Android gap from v0.5.
Android 8 (API 26) introduced notification channels as a hard requirement — any
app that skips `createNotificationChannel()` silently drops every notification on
modern Android. `notification_helper.py` handles all three cases correctly:
channel creation (idempotent), per-notification posting (unique time-based IDs),
and foreground service notification (required within 5s of service start on API 28+).

**E2E tests with Dovecot** are the most technically interesting addition.
Unit tests with mocked IMAP verify code paths but cannot catch protocol edge cases:
incorrect command ordering, wrong response parsing, socket state issues after
EXPUNGE. The E2E suite runs `fetch_uids_since`, `iter_new_messages`, and
`IdleMonitor` against a real Dovecot server and verifies actual bytes on the wire.
The skip-guard design (auto-skip when `localhost:143` unreachable) keeps the normal
`pytest tests/` run fast and unaffected.

**Reconnect prompt** turns a passive error indicator into an actionable recovery
flow. Previously, a stale credential showed red text — the user had to remember
to navigate to settings. Now the correct button appears immediately where the error
is shown. The connect screen also adapts (pre-filled email, "Update credentials"
text) to signal that this is a re-auth, not a first-time setup.

**IDLE status indicator** makes the push feature visible. Users can now confirm
that IDLE is active ("Live (IDLE)") rather than wondering whether polling is the
only mechanism working.

**7-day history chart** replaces a stats-only view with a visual. The Kivy canvas
implementation is correct (binds `size` and `pos` for responsive redraws) and
handles the empty-data case (minimum bar height of 2px so the bar area is visible
even with no syncs).

**CI hardening** completes a long-pending improvement: `|| true` on the UI smoke
tests is gone. The three-job split means the fast logic tests fail quickly without
waiting for Kivy to compile. Pip caching cuts repeated run time significantly.

---

## Remaining Weaknesses

**IDLE and BOOT_COMPLETED still unverified on physical device.** Every v0.5
caveat still applies. The notification channel code is correct by API spec but
needs device verification to confirm `startForeground` is called within the 5s
window and that the persistent notification appears in the status bar.

**E2E tests verified green in CI.** The `test-e2e` job runs against `dovecot/dovecot:latest`
via `docker compose` (Compose V2) in a step after checkout. All 9 E2E tests pass in GitHub
Actions. The three-job CI split (`test-logic` / `test-e2e` / `test-ui`) is fully green.

**`idle_last_seen` is only written when IDLE fires.** On desktop (no background
service), `idle_last_seen` stays NULL and the home screen always shows "Polling".
This is correct behaviour — IDLE genuinely isn't running on desktop — but could
confuse a desktop test user. Acceptable for an Android-first app.

**history_chart height is fixed.** The 80dp chart height is hard-coded. On small
screens this may crowd the stats panel. A `minimum_height`-based layout with
`ScrollView` (already in place) handles this safely.

---

## v0.7 Priorities (if wanted)

1. Physical device validation — notification channel + foreground notification + IDLE
2. Verify E2E CI in a real GitHub Actions run (may need Dovecot image + config tweak)
3. Kivy UI integration tests beyond smoke tests — simulate button taps, verify navigation
4. Per-UID watermark to skip tier-3 `message_exists()` for UIDs above a known-clean threshold
5. Export / import sync state for device migration
