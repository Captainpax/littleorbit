package com.littleorbit.mobile;

import android.app.Notification;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import androidx.annotation.NonNull;
import androidx.core.app.NotificationCompat;
import androidx.core.app.NotificationManagerCompat;
import androidx.hilt.work.HiltWorker;
import androidx.work.Constraints;
import androidx.work.ExistingPeriodicWorkPolicy;
import androidx.work.ExistingWorkPolicy;
import androidx.work.NetworkType;
import androidx.work.OneTimeWorkRequest;
import androidx.work.PeriodicWorkRequest;
import androidx.work.WorkManager;
import androidx.work.Worker;
import androidx.work.WorkerParameters;
import com.littleorbit.data.remote.SmoochApiModels;
import com.littleorbit.data.repository.OrbitRepository;
import dagger.assisted.Assisted;
import dagger.assisted.AssistedInject;
import java.time.DayOfWeek;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.TimeUnit;

/** Polls the self-hosted API for private Smooch and weekly recap notifications. */
@HiltWorker
public final class SmoochStatusWorker extends Worker {
    private static final String PERIODIC = "little-orbit-smooch-status";
    private final Context context;
    private final OrbitRepository orbit;

    /** Creates the notification worker. */
    @AssistedInject
    public SmoochStatusWorker(@Assisted @NonNull Context context,
            @Assisted @NonNull WorkerParameters parameters, OrbitRepository orbit) {
        super(context, parameters);
        this.context = context;
        this.orbit = orbit;
    }

    @NonNull
    @Override
    public Result doWork() {
        if (!PermissionChecks.notificationsGranted(context)) return Result.success();
        try {
            List<SmoochApiModels.Delivery> pending = orbit.pendingSmooches()
                    .get(30, TimeUnit.SECONDS);
            List<String> displayed = new ArrayList<>();
            for (SmoochApiModels.Delivery item : pending) {
                if (notifySmooch(item)) displayed.add(item.id);
            }
            if (!displayed.isEmpty()) {
                orbit.acknowledgeSmooches(displayed).get(30, TimeUnit.SECONDS);
            }
            maybeNotifyWeeklyRecap();
            return Result.success();
        } catch (Exception unavailable) {
            return getRunAttemptCount() < 3 ? Result.retry() : Result.failure();
        }
    }

    private boolean notifySmooch(SmoochApiModels.Delivery item) {
        Intent open = new Intent(context, SmoochActivity.class)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        PendingIntent content = PendingIntent.getActivity(context, item.id.hashCode(), open,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        boolean reveal = context.getSharedPreferences("smooch_settings", Context.MODE_PRIVATE)
                .getBoolean("full_lock_screen", false);
        String full = SmoochPhrases.render(
                context, item.phraseKey, item.partnerName, item.emoji);
        Notification publicVersion = new NotificationCompat.Builder(
                context, NotificationChannels.SMOOCHES)
                .setSmallIcon(R.drawable.ic_smooch)
                .setContentTitle(context.getString(R.string.smooch_notification_private_title))
                .setContentText(context.getString(R.string.smooch_notification_private_message))
                .build();
        Notification notification = new NotificationCompat.Builder(
                context, NotificationChannels.SMOOCHES)
                .setSmallIcon(R.drawable.ic_smooch)
                .setContentTitle(context.getString(R.string.smooches))
                .setContentText(full)
                .setStyle(new NotificationCompat.BigTextStyle().bigText(full))
                .setContentIntent(content)
                .setAutoCancel(true)
                .setVisibility(reveal
                        ? NotificationCompat.VISIBILITY_PUBLIC
                        : NotificationCompat.VISIBILITY_PRIVATE)
                .setPublicVersion(publicVersion)
                .build();
        try {
            NotificationManagerCompat.from(context).notify(item.id.hashCode(), notification);
            return true;
        } catch (SecurityException revoked) {
            // Do not acknowledge; the server keeps it pending until permission returns.
            return false;
        }
    }

    private void maybeNotifyWeeklyRecap() throws Exception {
        LocalDate today = LocalDate.now();
        if (today.getDayOfWeek() != DayOfWeek.MONDAY) return;
        List<SmoochApiModels.Week> weeks = orbit.smoochWeeks(2).get(30, TimeUnit.SECONDS);
        if (weeks.size() < 2) return;
        SmoochApiModels.Week prior = weeks.get(0);
        android.content.SharedPreferences state = context.getSharedPreferences(
                "smooch_settings", Context.MODE_PRIVATE);
        if (prior.weekEnd.equals(state.getString("last_recap", ""))) return;
        String text = context.getString(R.string.smooch_weekly_notification, prior.combined);
        Notification notification = new NotificationCompat.Builder(
                context, NotificationChannels.SMOOCHES)
                .setSmallIcon(R.drawable.ic_smooch)
                .setContentTitle(context.getString(R.string.smooch_weekly_title))
                .setContentText(text)
                .setAutoCancel(true)
                .setVisibility(NotificationCompat.VISIBILITY_PRIVATE)
                .build();
        try {
            NotificationManagerCompat.from(context).notify(7310, notification);
            state.edit().putString("last_recap", prior.weekEnd).apply();
        } catch (SecurityException revoked) {
            // Permission can change after the worker's initial check.
        }
    }

    /** Schedules the normal fifteen-minute fallback poll. */
    public static void schedule(Context context, boolean enabled) {
        WorkManager manager = WorkManager.getInstance(context);
        if (!enabled) {
            manager.cancelUniqueWork(PERIODIC);
            return;
        }
        Constraints network = new Constraints.Builder()
                .setRequiredNetworkType(NetworkType.CONNECTED).build();
        PeriodicWorkRequest request = new PeriodicWorkRequest.Builder(
                SmoochStatusWorker.class, 15, TimeUnit.MINUTES)
                .setConstraints(network).build();
        manager.enqueueUniquePeriodicWork(
                PERIODIC, ExistingPeriodicWorkPolicy.UPDATE, request);
    }

    /** Requests an immediate conditional poll without duplicating active work. */
    public static void enqueue(Context context) {
        Constraints network = new Constraints.Builder()
                .setRequiredNetworkType(NetworkType.CONNECTED).build();
        OneTimeWorkRequest request = new OneTimeWorkRequest.Builder(SmoochStatusWorker.class)
                .setConstraints(network).build();
        WorkManager.getInstance(context).enqueueUniqueWork(
                "little-orbit-smooch-now", ExistingWorkPolicy.KEEP, request);
    }
}
