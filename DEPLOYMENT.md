# MailSync — Deployment Guide

---

## Release Flow

```
development  →  CI green  →  PR to main  →  merge  →  android.yml builds APK  →  apk-latest release
```

1. All work and all doc updates happen on `development`
2. Push to `development` → CI runs `pytest tests/ -q`
3. When CI is green and all five docs are updated, open PR: `development → main`
4. Merge PR → `android.yml` triggers automatically
5. APK is published to GitHub Release `apk-latest` within ~20 minutes
6. Download APK from Release, sideload to device

---

## Sideloading Instructions

1. Download `mailsync-*.apk` from the `apk-latest` release
2. Transfer to Android device (USB, email to self, Google Drive, etc.)
3. On device: open the APK file
4. If prompted: Settings → Security → Install unknown apps → allow
5. App installs as "MailSync"

---

## First-Time Setup on Device

1. Open MailSync
2. Tap "Settings / Accounts" → "Connect Accounts"
3. **Yahoo**: enter Yahoo email + App Password
   - Generate App Password at: `login.yahoo.com → Account Security → Generate app password`
4. **Microsoft**: tap "Connect Microsoft Account"
   - Visit the URL shown, enter the code, sign in with your Microsoft account
   - App waits for sign-in automatically
5. Return to home screen — both accounts should show "Connected"
6. Tap **SYNC NOW** for the first full sync (may take a while for large inboxes)
7. Background service starts automatically and syncs every hour

---

## Azure App Registration (One-Time)

Required for the Microsoft auth flow. Free, no credit card if using an
existing Microsoft 365 account to access the Azure portal.

1. Go to `portal.azure.com` → sign in with your Microsoft 365 account
2. Azure Active Directory → App registrations → New registration
   - Name: `MailSync`
   - Supported account types: "Accounts in any organizational directory and personal Microsoft accounts"
   - Redirect URI: none (Device Code Flow doesn't need one)
3. After creation: Authentication → Add platform → Mobile and desktop applications
4. API permissions → Add permission → Microsoft Graph → Delegated
   - `Mail.ReadWrite`
   - `offline_access`
5. Copy the **Application (client) ID**
6. Set `MAILSYNC_CLIENT_ID` to that value in `auth/microsoft_auth.py` or via env var

---

## Version Bumping

1. Update `buildozer.spec`: `version = 0.X.Y`
2. Update `RELEASE_NOTES.md` with the new version entry
3. Update `CLAUDE_REVIEW.md` rating if significant changes
4. Commit to `development`, push, open PR
