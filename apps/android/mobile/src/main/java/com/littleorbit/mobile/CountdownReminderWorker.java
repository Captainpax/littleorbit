package com.littleorbit.mobile;

import android.Manifest;
import android.app.NotificationManager;
import android.app.Notification;
import android.app.PendingIntent;
import android.content.Intent;
import android.content.Context;
import android.content.pm.PackageManager;
import android.os.Build;
import androidx.annotation.NonNull;
import androidx.core.app.NotificationCompat;
import androidx.core.content.ContextCompat;
import androidx.work.Worker;
import androidx.work.WorkerParameters;

/** Local-only countdown reminder that contains no notes or partner data. */
public final class CountdownReminderWorker extends Worker {
    /** Creates a local reminder worker. */
    public CountdownReminderWorker(
            @NonNull Context context, @NonNull WorkerParameters parameters) {
        super(context, parameters);
    }

    /** Posts the user-selected event title without a network call. */
    @NonNull
    @Override
    public Result doWork() {
        Context context = getApplicationContext();
        NotificationSettingsStore choices = new NotificationSettingsStore(context);
        if (!choices.master() || !choices.countdowns()
                || !PermissionChecks.channelEnabled(context, NotificationChannels.COUNTDOWNS)) {
            return Result.success();
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU
                && ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS)
                        != PackageManager.PERMISSION_GRANTED) {
            return Result.success();
        }
        NotificationManager manager = context.getSystemService(NotificationManager.class);
        String title = getInputData().getString("title");
        Intent open = new Intent(context, CountdownActivity.class)
                .addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_SINGLE_TOP);
        PendingIntent content = PendingIntent.getActivity(
                context, getId().hashCode(), open,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        Notification publicVersion = new NotificationCompat.Builder(
                context, NotificationChannels.COUNTDOWNS)
                .setSmallIcon(R.drawable.ic_countdown)
                .setContentTitle(context.getString(R.string.private_notification_title))
                .setContentText(context.getString(R.string.private_notification_message))
                .build();
        manager.notify(
                getId().hashCode(),
                new NotificationCompat.Builder(context, NotificationChannels.COUNTDOWNS)
                        .setSmallIcon(R.drawable.ic_countdown)
                        .setContentTitle(title == null ? context.getString(R.string.countdown_due) : title)
                        .setContentText(context.getString(R.string.countdown_due))
                        .setContentIntent(content)
                        .setAutoCancel(true)
                        .setVisibility(NotificationCompat.VISIBILITY_PRIVATE)
                        .setPublicVersion(publicVersion)
                        .build());
        return Result.success();
    }
}
