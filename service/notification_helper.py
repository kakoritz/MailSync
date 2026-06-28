"""
Android notification helper.

Wraps the android.notifications API to:
  - Create a notification channel (required on Android 8+ / API 26+)
  - Send notifications through that channel
  - Post the persistent foreground service notification (required on Android 9+ / API 28+)

On non-Android platforms every function is a no-op so the module can be
imported in tests and on desktop without crashing.
"""

CHANNEL_ID = "mailsync_sync"
CHANNEL_NAME = "MailSync Sync"
FOREGROUND_NOTIF_ID = 1


def create_channel() -> None:
    """Create the mailsync_sync notification channel (idempotent)."""
    try:
        from android import mActivity
        from jnius import autoclass

        NotificationManager = autoclass("android.app.NotificationManager")
        NotificationChannel = autoclass("android.app.NotificationChannel")
        IMPORTANCE_LOW = NotificationManager.IMPORTANCE_LOW

        channel = NotificationChannel(CHANNEL_ID, CHANNEL_NAME, IMPORTANCE_LOW)
        channel.setDescription("MailSync background sync status")

        manager = mActivity.getSystemService(NotificationManager._class.getName())
        manager.createNotificationChannel(channel)
    except Exception:
        pass


def send_notification(title: str, body: str) -> None:
    """Post a notification to the mailsync_sync channel."""
    try:
        from android import mActivity
        from jnius import autoclass

        NotificationCompat = autoclass("androidx.core.app.NotificationCompat")
        NotificationManagerCompat = autoclass("androidx.core.app.NotificationManagerCompat")

        notification = (
            NotificationCompat.Builder(mActivity, CHANNEL_ID)
            .setSmallIcon(autoclass("android.R$drawable").ic_dialog_info)
            .setContentTitle(title)
            .setContentText(body)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .setAutoCancel(True)
            .build()
        )

        manager = NotificationManagerCompat.from_(mActivity)
        import time
        manager.notify(int(time.time()) & 0x7FFFFFFF, notification)
    except Exception:
        pass


def start_foreground(service_context) -> None:
    """Post the persistent foreground notification that keeps the service alive.

    Must be called within 5 seconds of service start on Android 9+ or the OS
    will kill the service.
    """
    try:
        from jnius import autoclass

        NotificationCompat = autoclass("androidx.core.app.NotificationCompat")
        ServiceCompat = autoclass("androidx.core.app.ServiceCompat")

        notification = (
            NotificationCompat.Builder(service_context, CHANNEL_ID)
            .setSmallIcon(autoclass("android.R$drawable").ic_dialog_info)
            .setContentTitle("MailSync")
            .setContentText("Sync service running")
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .setOngoing(True)
            .build()
        )

        service_context.startForeground(FOREGROUND_NOTIF_ID, notification)
    except Exception:
        pass
