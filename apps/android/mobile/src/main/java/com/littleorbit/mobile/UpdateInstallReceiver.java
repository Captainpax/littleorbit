package com.littleorbit.mobile;

import android.app.Activity;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageInstaller;

/** Receives sanitized PackageInstaller results and opens Android's confirmation screen. */
public final class UpdateInstallReceiver extends BroadcastReceiver {
    public static final String ACTION_INSTALL_RESULT =
            "com.littleorbit.mobile.action.UPDATE_INSTALL_RESULT";

    @Override
    public void onReceive(Context context, Intent intent) {
        int status = intent.getIntExtra(
                PackageInstaller.EXTRA_STATUS, PackageInstaller.STATUS_FAILURE);
        if (status == PackageInstaller.STATUS_PENDING_USER_ACTION) {
            Intent confirmation;
            if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.TIRAMISU) {
                confirmation = intent.getParcelableExtra(Intent.EXTRA_INTENT, Intent.class);
            } else {
                @SuppressWarnings("deprecation")
                Intent legacy = intent.getParcelableExtra(Intent.EXTRA_INTENT);
                confirmation = legacy;
            }
            if (confirmation != null) {
                confirmation.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                context.startActivity(confirmation);
                write(context, "awaiting_confirmation", "");
            } else {
                write(context, "retry_install", "install_confirmation_missing");
            }
            return;
        }
        if (status == PackageInstaller.STATUS_SUCCESS) {
            write(context, "installed", "");
        } else if (status == PackageInstaller.STATUS_FAILURE_ABORTED) {
            write(context, "retry_install", "install_cancelled");
        } else if (status == PackageInstaller.STATUS_FAILURE_STORAGE) {
            write(context, "retry_install", "install_storage");
        } else if (status == PackageInstaller.STATUS_FAILURE_BLOCKED) {
            write(context, "retry_install", "install_blocked");
        } else {
            write(context, "retry_install", "install_failed");
        }
        setResultCode(Activity.RESULT_OK);
    }

    private static void write(Context context, String phase, String failure) {
        SharedPreferences preferences = context.getSharedPreferences(
                "little-orbit-updater-state", Context.MODE_PRIVATE);
        preferences.edit().putString("phase", phase).putString("failure", failure).apply();
    }
}
