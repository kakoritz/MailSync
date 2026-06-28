package org.kakoritz.mailsync;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.os.Build;
import android.util.Log;

/**
 * Restarts the MailSync background sync service after device reboot.
 *
 * Declared in AndroidManifest.xml via extras/boot_receiver.xml.
 * Requires RECEIVE_BOOT_COMPLETED permission in buildozer.spec.
 *
 * The python-for-android runtime (PythonService) is started as a foreground
 * service so Android 8+ does not kill it immediately after boot.
 *
 * Build requirement: buildozer >= 1.3 (android.extra_manifest_xml support)
 */
public class BootReceiver extends BroadcastReceiver {

    private static final String TAG = "MailSyncBoot";

    @Override
    public void onReceive(Context ctx, Intent intent) {
        if (!Intent.ACTION_BOOT_COMPLETED.equals(intent.getAction())) {
            return;
        }

        Log.i(TAG, "BOOT_COMPLETED received — starting MailSync sync service");

        try {
            Intent svc = new Intent(ctx, org.kivy.android.PythonService.class);

            // Path where the APK installed Python files
            svc.putExtra("androidPrivateStorage",
                    ctx.getFilesDir().getAbsolutePath());

            // Service metadata (matches buildozer.spec android.services entry)
            svc.putExtra("pythonName", "sync");
            svc.putExtra("serviceEntrypoint", "service/sync_service.py");
            svc.putExtra("serviceTitle", "MailSync");
            svc.putExtra("serviceDescription", "Background email sync running");
            svc.putExtra("androidArgument", "");

            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                ctx.startForegroundService(svc);
            } else {
                ctx.startService(svc);
            }

            Log.i(TAG, "Sync service start requested");

        } catch (Exception e) {
            // PythonService not available (app not fully installed yet) — ignore
            Log.w(TAG, "Could not start sync service: " + e.getMessage());
        }
    }
}
