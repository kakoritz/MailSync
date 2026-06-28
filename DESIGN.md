# MailSync — Product Design Document

**Project:** MailSync
**Repo:** [github.com/kakoritz/MailSync](https://github.com/kakoritz/MailSync)
**Version:** v0.6.0

---

## 1. Problem Statement

Yahoo Mail does not offer email forwarding without a paid subscription. When
shutting down a Yahoo account and migrating to Microsoft Outlook 365, there is
no free automated path to move existing and new messages. MailSync solves this
by running continuously on Android, reading new messages from Yahoo via IMAP
and writing them to Outlook via the Microsoft Graph API.

---

## 2. Core Requirements

| # | Requirement | Notes |
|---|---|---|
| 1 | Authenticate to Yahoo Mail | IMAP + App Password |
| 2 | Authenticate to Microsoft Outlook 365 | MSAL Device Code Flow |
| 3 | Show connection status for both accounts | Connected / Disconnected / Error |
| 4 | Sync emails Yahoo → Outlook on demand | SYNC NOW button |
| 5 | Sync automatically every hour | Android background service |
| 6 | Track last synced email persistently | `last_yahoo_uid` in SQLite — never reset |
| 7 | Show sync statistics | Total, today, since date, health % |
| 8 | Launch Outlook from within the app | Android Intent |
| 9 | Secure credential storage | Fernet-encrypted, device-bound |

---

## 3. Architecture

### 3.1 Layer diagram

```
┌─────────────────────────────────────────────┐
│                 Kivy UI                     │
│  HomeScreen · ConnectScreen · HistoryScreen │
│  SettingsScreen · Widgets                   │
└─────────────────┬───────────────────────────┘
                  │ calls
┌─────────────────▼───────────────────────────┐
│              Sync Engine                    │
│  sync_engine.py → yahoo_reader.py           │
│                 → outlook_writer.py         │
└──────┬──────────────────────┬───────────────┘
       │                      │
┌──────▼──────┐    ┌──────────▼──────┐
│  Yahoo IMAP │    │  Graph API      │
│  (imaplib)  │    │  (requests)     │
└─────────────┘    └─────────────────┘
       │                      │
┌──────▼──────────────────────▼───────────────┐
│              Auth Layer                     │
│  yahoo_auth.py · microsoft_auth.py          │
│  token_store.py (→ crypto.py)               │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│              Core / Storage                 │
│  database.py (SQLite) · config.py (JSON)    │
└─────────────────────────────────────────────┘
```

### 3.2 Module dependency rule

Lower layers never import from upper layers. `ui/` imports from `sync/`,
`auth/`, and `core/`. `sync/` imports from `auth/` and `core/`. `auth/`
imports from `core/`. `core/` imports nothing internal.

This guarantees the sync and auth layers are testable without a display,
and the UI can be replaced without touching business logic.

---

## 4. Auth Flows

### 4.1 Yahoo

Yahoo killed basic IMAP auth in 2022. The only approach that doesn't require
developer registration is IMAP with an **App Password** generated at
`login.yahoo.com → Security → Generate app password`.

Flow:
1. User enters email + App Password in ConnectScreen
2. `yahoo_auth.validate_credentials()` opens SSL IMAP and attempts login
3. On success, App Password is Fernet-encrypted and stored in SQLite
4. Each sync run calls `yahoo_auth.connect()` which decrypts and re-authenticates

### 4.2 Microsoft

Microsoft requires OAuth2 for all Exchange Online access. The **Device Code Flow**
was chosen because:
- No redirect URI or web server needed
- Works on mobile without embedding a browser
- User authenticates once; refresh tokens handle subsequent runs

Flow:
1. User taps "Connect Microsoft Account"
2. `microsoft_auth.initiate_device_flow()` returns a URL and one-time code
3. App displays the URL and code (user visits on any browser)
4. `poll_device_flow()` blocks until the user completes sign-in
5. Full token JSON (access + refresh) is Fernet-encrypted and stored in SQLite
6. Each API call transparently refreshes the token via MSAL silent flow or refresh token

Required Azure App Registration settings:
- Platform: Mobile and desktop applications
- Scopes: `Mail.ReadWrite`, `offline_access`
- Client ID set via `MAILSYNC_CLIENT_ID` environment variable

---

## 5. Sync Engine

### 5.1 UID-based tracking

IMAP UIDs are stable, monotonically increasing message identifiers within a
mailbox. The sync engine stores `last_yahoo_uid` in the `sync_state` table.
On each sync run:

```
SEARCH UID (last_yahoo_uid + 1):*
```

This returns only messages newer than the last successful sync. UIDs are
processed in ascending order so `last_yahoo_uid` always reflects the highest
successfully migrated message.

`last_yahoo_uid` is **never reset** unless the user explicitly removes the
Yahoo account from the app. This is by design — it is the migration checkpoint
and must survive app restarts, crashes, and OS kills.

### 5.2 Idempotency and the Initial Sync Fast Path

When `last_yahoo_uid == 0` at the start of a run (i.e., the first ever sync),
the Outlook mailbox is guaranteed empty — no messages have ever been written.
The per-message `message_exists()` check is skipped entirely for this run,
saving N Graph API calls on large inboxes.

For all subsequent runs (`last_yahoo_uid > 0`), before writing each message
the engine checks whether a message with the same `Message-ID` header already
exists via Graph API filter query. If it does, the UID is advanced without
writing. This makes resuming a failed sync safe — no duplicate messages are
created.

The dedup strategy has three tiers:

1. **Initial sync fast path** (`is_initial_sync`) — skip all existence checks
   when `last_yahoo_uid == 0`. Outlook is guaranteed empty.
2. **Per-run Message-ID cache** — a `set[str]` of Message-IDs written this run.
   O(1) lookup; catches same-ID re-appearances within a single run without any
   network call.
3. **Graph API filter query** (`message_exists()`) — the fallback for messages
   that might already exist in Outlook from a previous run.

`SyncResult` tracks `emails_skipped` (tier 3 dedup) and `emails_cache_hit`
(tier 2 cache) separately for observability.

### 5.3 Partial failure recovery

If a Graph API write fails mid-run (e.g., 503 transient error), the engine
stops the current run and writes a `partial` log entry. `last_yahoo_uid`
reflects only the last successfully written message. The next run resumes
from that point.

### 5.4 Per-sync batching

One IMAP connection is opened per sync run and held open for the full batch.
This is significantly more efficient than opening a new connection per message.

---

## 6. Security

### 6.1 Credential storage

All credentials and tokens are encrypted with `cryptography.fernet.Fernet`
before writing to SQLite. The encryption key is derived from:

- A **device fingerprint** (`android_id` on Android, machine-id on Linux/Mac)
- A **random 32-byte salt** generated on first run and stored in `.salt`

Key derivation uses PBKDF2-HMAC-SHA256 with 260,000 iterations. The resulting
blobs are device-bound — they cannot be decrypted on a different device.

### 6.2 Memory hygiene

App Passwords and token JSON strings are `del`-ed after encryption. Python
does not guarantee immediate memory reclamation, but this eliminates the
plaintext from the local namespace at the earliest possible point.

### 6.3 No secrets in config or logs

`config.py` stores only non-sensitive preferences (sync interval, theme).
`MAILSYNC_CLIENT_ID` is an environment variable, never hardcoded. The
`.gitignore` excludes `mailsync.db`, `.salt`, and config files.

---

## 7. Background Service

The Android service (`service/sync_service.py`) runs as a separate process,
declared in `buildozer.spec` as:

```ini
android.services = sync:service/sync_service.py
```

The service:
1. Calls `database.init()` independently (separate SQLite connection)
2. Runs `run_sync()` immediately on every iteration
3. Opens an IMAP IDLE connection and waits for EXISTS push notification
4. Falls back to the configured sync interval if IDLE does not fire
5. Posts an Android notification if new emails were synced

### 7.1 IMAP IDLE (RFC 2177)

Rather than polling every N minutes, the service uses IMAP IDLE to receive
push notifications from Yahoo's server when new mail arrives:

```
Service → Yahoo IMAP: A001 IDLE\r\n
Yahoo IMAP → Service: + idling\r\n
... new message arrives ...
Yahoo IMAP → Service: * 5 EXISTS\r\n
Service → Yahoo IMAP: DONE\r\n
Yahoo IMAP → Service: A001 OK IDLE terminated\r\n
Service: run_sync() immediately
```

The IDLE connection is held in `sync/imap_idle.py` (`IdleMonitor`). A 25-minute
keepalive (DONE + re-IDLE) prevents the server from closing the connection before
the configured sync interval elapses. On any connection error, the monitor
reconnects with exponential backoff.

### 7.2 BOOT_COMPLETED

`src/BootReceiver.java` is compiled into the APK and registered in
`AndroidManifest.xml` via `extras/boot_receiver.xml`. After device reboot,
Android dispatches `ACTION_BOOT_COMPLETED` to the receiver, which starts
`PythonService` as a foreground service.

The `FOREGROUND_SERVICE` permission keeps the process alive when the app is
backgrounded. `RECEIVE_BOOT_COMPLETED` restarts the service after device reboot.

### 7.3 Notification Channels (Android 8+ / API 26+)

`service/notification_helper.py` wraps the Android notification API:

- `create_channel()` — creates the `mailsync_sync` channel with `IMPORTANCE_LOW`.
  Called once at service startup. Idempotent — safe to call every restart.
- `send_notification(title, body)` — posts through the channel. Uses a
  time-based notification ID so back-to-back notifications don't overwrite each other.
- `start_foreground(service_context)` — posts the persistent "MailSync active"
  notification required by Android 9+ (API 28+) to keep a foreground service alive.
  Must be called within 5 seconds of service start.

On non-Android platforms (tests, desktop) every function is a no-op.

---

## 8. Database Schema

```sql
-- Permanent migration state. last_yahoo_uid is never reset.
CREATE TABLE sync_state (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    yahoo_email     TEXT NOT NULL UNIQUE,
    outlook_email   TEXT NOT NULL,
    last_yahoo_uid  INTEGER NOT NULL DEFAULT 0,
    pending_emails  INTEGER,   -- last dry-run count; NULL until first dry-run
    idle_last_seen  TEXT,      -- UTC timestamp of last IDLE EXISTS push; NULL until first IDLE fire
    first_sync_at   TEXT,      -- set once, never updated
    last_sync_at    TEXT,
    created_at      TEXT NOT NULL
);

-- One row per sync run. Source of truth for stats.
CREATE TABLE sync_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    sync_state_id   INTEGER NOT NULL REFERENCES sync_state(id),
    started_at      TEXT NOT NULL,
    completed_at    TEXT,
    emails_synced   INTEGER NOT NULL DEFAULT 0,
    status          TEXT CHECK(status IN ('success','partial','error')),
    error_msg       TEXT
);

-- Encrypted credential storage. Never plaintext.
CREATE TABLE accounts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    service     TEXT NOT NULL CHECK(service IN ('yahoo','microsoft')),
    email       TEXT NOT NULL UNIQUE,
    cred_blob   BLOB NOT NULL,
    added_at    TEXT NOT NULL
);
```

---

## 9. UI Layout

### 9.1 Home screen

```
┌─────────────────────────────────┐
│  MailSync                       │
├─────────────────────────────────┤
│  ● Yahoo     user@yahoo.com  ✓ │
│  ● Outlook   user@ms.com     ✓ │
├─────────────────────────────────┤
│         [ SYNC NOW ]            │
│    [ Check Pending Emails ]     │
├─────────────────────────────────┤
│  Syncing since     Jan 15, 2026 │
│  Total synced          1,247    │
│  Synced today             14    │
│  Last sync          2 min ago   │
│  Pending (est.)           12    │
│  Health  ████████░░  82%        │
├─────────────────────────────────┤
│  [ Open Outlook ↗ ]             │
│  [ Settings / Accounts ]        │
└─────────────────────────────────┘
```

### 9.2 Screen flow

```
HomeScreen
  ├── ConnectScreen  (tap "Settings/Accounts" when no accounts)
  ├── SettingsScreen (tap "Settings/Accounts" when connected)
  │     └── HistoryScreen
  └── ConnectScreen  (tap "Connect Accounts" in settings)
```

---

## 10. CI/CD

| Workflow | Trigger | Action |
|---|---|---|
| `ci.yml` | push to `development`, PR to `main` | Three parallel jobs: logic, e2e, ui |
| `android.yml` | merge to `main`, manual dispatch | `buildozer android debug` → APK released |

### CI job structure

```
test-logic  (fast, ~2 min)
  └── installs: requests msal cryptography pytest
  └── runs: pytest tests/ -q --ignore=tests/test_screens.py

test-e2e    (starts dovecot/dovecot:latest via docker compose in a step after checkout)
  └── needs: test-logic
  └── runs: pytest tests/e2e/ -m e2e -q

test-ui     (slow, ~10 min — Kivy compile or cache hit)
  └── needs: test-logic
  └── installs: kivy[base]>=2.3.0 (pip-cached by requirements hash)
  └── runs: pytest tests/test_screens.py -q (hard gate — no || true)
```

`pip cache` is shared across runs using `actions/cache` keyed on `requirements*.txt` hash.

## 11. E2E Testing

Unit tests mock all external calls. E2E tests use a real Dovecot IMAP server in
Docker to verify the actual IMAP stack end-to-end.

```
tests/e2e/
  conftest.py              — e2e marker, skip guard, clear_inbox fixture
  test_yahoo_imap_e2e.py   — fetch_uids_since + iter_new_messages against Dovecot
  test_idle_e2e.py         — IdleMonitor callback fires on APPEND; stop() is clean
  dovecot/
    10-auth.conf           — plaintext auth, static password for test user
    10-mail.conf           — maildir storage
    10-ssl.conf            — SSL disabled (localhost test only)
```

E2E tests patch `auth.yahoo_auth.connect` to return a plain `IMAP4` connection
to `localhost:143` instead of an SSL connection to Yahoo's servers. The IMAP
protocol logic being tested is identical either way.

Skip behaviour: if `localhost:143` is not reachable, all 9 e2e tests skip
automatically. The unit test run (102 tests) is unaffected.

**CI note:** the `test-e2e` job uses `docker compose` (Compose V2 plugin, not the
standalone `docker-compose` v1 binary which is absent from ubuntu-22.04 runners).
The server starts in a step *after* `actions/checkout` so the config volume files
at `tests/e2e/dovecot/` are available before Dovecot starts.

Skip behaviour: if `localhost:143` is not reachable, all 9 e2e tests skip
automatically. The unit test run (102 tests) is unaffected.

---

## 11. Portfolio Context

MailSync demonstrates:
- **Real OAuth2 flows** on mobile (Device Code Flow — no redirect URI, no web server)
- **IMAP programming** with UID-based stable iteration and partial failure recovery
- **Encrypted storage** with device-bound key derivation (PBKDF2 + Fernet)
- **Android service** integration from Python (Kivy background service)
- **Clean architecture** — six distinct layers with enforced dependency direction
- **Idempotent sync** — re-running never creates duplicates
- **Full test coverage** of all business logic with mocked external dependencies
