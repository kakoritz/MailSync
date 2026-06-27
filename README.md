# MailSync

**Yahoo Mail → Microsoft Outlook 365 migration app for Android**

Built with Python + Kivy. Solves the problem of Yahoo not offering free email
forwarding when migrating to a new email provider.

---

## What it does

- Connects to your Yahoo Mail account (IMAP + App Password)
- Connects to your Microsoft Outlook 365 account (OAuth2 Device Code Flow)
- Reads new emails from Yahoo, writes them to your Outlook Inbox
- Runs automatically every hour in the background
- Tracks the last synced email permanently — picks up exactly where it left off
- Shows stats: total synced, today's count, health percentage, last sync time
- Lets you launch the Outlook app directly from within MailSync

---

## Why this exists

Yahoo does not offer email forwarding without a paid subscription. Rather than
pay Yahoo for a feature that exists elsewhere for free — or manually export/import
— MailSync automates the migration continuously until the Yahoo account is retired.

---

## Setup

### Prerequisites

- Android phone (API 26 / Android 8.0 or newer)
- Yahoo account with an **App Password** generated
  - [Generate at Yahoo Account Security](https://login.yahoo.com/) → Account Security → Generate app password
- Microsoft 365 account (personal Outlook.com or work/school account)
- An **Azure App Registration** with `Mail.ReadWrite` scope (free — see [DEPLOYMENT.md](DEPLOYMENT.md))

### Install

Download the latest APK from [Releases → apk-latest](../../releases/tag/apk-latest)
and sideload it to your device. See [DEPLOYMENT.md](DEPLOYMENT.md) for full instructions.

### First sync

1. Open MailSync → tap Settings / Accounts → Connect Accounts
2. Enter Yahoo email + App Password
3. Tap Connect Microsoft Account → follow the on-screen device code flow
4. Return home → tap **SYNC NOW**

---

## Features

| Feature | Detail |
|---|---|
| Yahoo auth | IMAP + App Password — no developer account needed |
| Microsoft auth | MSAL Device Code Flow — no redirect URI, no web server |
| Sync mode | On-demand (SYNC NOW) + automatic hourly background service |
| Sync tracking | UID-based, persistent — survives restarts and crashes |
| Idempotent | Re-running never creates duplicates (Message-ID dedup) |
| Stats | Total synced, today, since-date, health % (30-day success rate) |
| Open Outlook | One tap to switch to the Outlook app |
| Security | All credentials Fernet-encrypted with device-bound key derivation |
| Notifications | Android notification when new emails are synced |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.10+ |
| UI | Kivy 2.3+ |
| Android build | Buildozer + python-for-android |
| Yahoo | imaplib + IMAP4_SSL |
| Microsoft | MSAL + Microsoft Graph API |
| Storage | SQLite3 (stdlib) |
| Encryption | cryptography (Fernet + PBKDF2) |
| HTTP | requests |
| Tests | pytest |

---

## Project Structure

```
main.py               App bootstrap
service/              Android background service
core/                 Constants, config, database, state machine
auth/                 Yahoo + Microsoft auth, encrypted token store
sync/                 Yahoo reader, Outlook writer, sync engine, scheduler
ui/                   Kivy screens and reusable widgets
security/             Key derivation and Fernet encryption
tests/                pytest test suite (40+ tests, all network mocked)
```

---

## Building from Source

See [ANDROID_BUILD.md](ANDROID_BUILD.md) for local and CI build instructions.

```bash
pip install buildozer cython
buildozer android debug
```

---

## Running Tests

```bash
pip install requests msal cryptography pytest
pytest tests/ -q
```

---

## Design & Architecture

See [DESIGN.md](DESIGN.md) for a full architecture document including auth flow
diagrams, database schema, sync engine design, and security model.

---

## Changelog

See [RELEASE_NOTES.md](RELEASE_NOTES.md).

---

## Portfolio Context

MailSync is a real solution to a real problem. It demonstrates:

- OAuth2 Device Code Flow on mobile — no web server, no redirect URI
- IMAP programming with stable UID tracking and partial failure recovery
- Encrypted credential storage with device-bound PBKDF2 key derivation
- Android background service integration from Python (Kivy service layer)
- Clean six-layer architecture with enforced dependency direction
- Idempotent sync design — safe to re-run at any point
- 40+ unit tests covering all business logic with fully mocked external dependencies
