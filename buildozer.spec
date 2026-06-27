[app]
title           = MailSync
package.name    = mailsync
package.domain  = org.kakoritz
source.dir      = .
source.include_exts = py,json
source.exclude_dirs = tests,.git,.claude,__pycache__,.venv

version         = 0.2.0

requirements    = python3,kivy,requests,msal,cryptography

orientation     = portrait
fullscreen      = 1

android.minapi      = 26
android.targetapi   = 34
android.ndk         = 28c
android.archs       = arm64-v8a

android.accept_sdk_license = True

android.permissions = INTERNET,RECEIVE_BOOT_COMPLETED,FOREGROUND_SERVICE,WAKE_LOCK,POST_NOTIFICATIONS

android.services = sync:service/sync_service.py

icon.filename    = %(source.dir)s/icon.png
presplash        = %(source.dir)s/presplash.png
presplash.color  = #0D0D1A

[buildozer]
log_level   = 2
warn_on_root = 1
build_dir   = /home/kakoritz/.mailsync-build
