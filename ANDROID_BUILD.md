# MailSync — Android Build Guide

---

## Overview

MailSync builds to an Android APK using Buildozer + python-for-android.
CI builds automatically on every merge to `main`. Local builds are supported
for development iteration.

---

## CI Build (Automatic)

Every merge to `main` triggers `.github/workflows/android.yml`:

1. Ubuntu 22.04, Python 3.10, Java 17
2. `pip install buildozer cython`
3. `buildozer -v android debug`
4. APK published to GitHub Release `apk-latest`

Build time: ~20 min first run (SDK/NDK download), ~5 min with cache hit.

### Installing from CI

1. Go to the repo Releases → `apk-latest`
2. Download `mailsync-*.apk`
3. Transfer to your Android device
4. On the device: Settings → Security → Install unknown apps → allow your browser/file manager
5. Open the APK file

---

## Local Build

### Prerequisites

```bash
# 1. Python venv (avoid system pip issues on Ubuntu 22+)
python3 -m venv ~/.mailsync-env
source ~/.mailsync-env/bin/activate
pip install buildozer cython

# 2. System dependencies
sudo apt-get install -y \
  git zip unzip autoconf libtool pkg-config \
  zlib1g-dev cmake libffi-dev libssl-dev openjdk-17-jdk

# 3. Set JAVA_HOME
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
```

### Build

```bash
cd /path/to/MailSync
source ~/.mailsync-env/bin/activate
buildozer android debug
# APK lands at bin/mailsync-*.apk
```

### Install to connected device

```bash
adb install bin/mailsync-*.apk
```

---

## buildozer.spec Notes

| Setting | Value | Why |
|---|---|---|
| `requirements` | `python3,kivy,requests,msal,cryptography` | All runtime deps |
| `android.services` | `sync:service/sync_service.py` | Background hourly sync |
| `android.minapi` | 26 | Android 8.0+ (foreground service requires API 26) |
| `android.targetapi` | 34 | Required for Play Store compliance |
| `android.archs` | `arm64-v8a` | All phones since ~2019 |
| `build_dir` | `/home/kakoritz/.mailsync-build` | Avoids spaces in path |

---

## Environment Variable Setup on Device

The `MAILSYNC_CLIENT_ID` (Azure App Registration client ID) must be set.
On Android, set it in `service/sync_service.py` or inject it via a config
file that is not committed to the repo.

---

## Troubleshooting

**"No module named 'cryptography'"** — add `cryptography` to `requirements` in
`buildozer.spec` if it's missing. It must be listed explicitly.

**Build fails with "path contains spaces"** — `build_dir` in `[buildozer]`
section must not have spaces. Set it to `/home/<user>/.mailsync-build`.

**MSAL device flow doesn't work on device** — ensure `INTERNET` permission is
declared in `buildozer.spec` and the device has network access.

**Background service stops after 30 minutes** — Android 8+ requires
`FOREGROUND_SERVICE` permission and a persistent notification. Both are
configured in `buildozer.spec` and `service/sync_service.py`.

**401 from Graph API after a few days** — the access token expired and the
refresh token path failed. Re-run the Device Code Flow via ConnectScreen.

---

## BOOT_COMPLETED Auto-restart (Status: Not Yet Implemented)

The `RECEIVE_BOOT_COMPLETED` permission is declared in `buildozer.spec` but
does not yet restart the service automatically after a device reboot. Doing
this purely from Python is not currently possible — it requires a Java
`BroadcastReceiver` compiled into the APK.

### Why it requires Java

Android dispatches the `BOOT_COMPLETED` intent before any Python runtime
exists. You need a Java class registered in `AndroidManifest.xml` that starts
the Kivy service when the intent fires. python-for-android does not generate
this automatically.

### Implementation plan (v0.4)

1. Create `src/BootReceiver.java`:

```java
package org.kakoritz.mailsync;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

public class BootReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context ctx, Intent intent) {
        if (Intent.ACTION_BOOT_COMPLETED.equals(intent.getAction())) {
            Intent svc = new Intent(ctx, org.kivy.android.PythonService.class);
            svc.putExtra("androidPrivateStorage", ctx.getFilesDir().getAbsolutePath());
            svc.putExtra("pythonName", "mailsync_sync");
            ctx.startForegroundService(svc);
        }
    }
}
```

2. Register it in `buildozer.spec` via `android.add_src = src/BootReceiver.java`
   and patch `AndroidManifest.xml` with a custom `p4a` hook.

3. Build and test on a physical device (emulators often suppress BOOT_COMPLETED).

Until v0.4, users must manually open the app after a reboot for background
sync to resume.
