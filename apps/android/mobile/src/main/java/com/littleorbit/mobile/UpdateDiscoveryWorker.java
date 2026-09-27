package com.littleorbit.mobile;

import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.os.Build;
import androidx.annotation.NonNull;
import androidx.core.app.NotificationCompat;
import androidx.core.app.NotificationManagerCompat;
import androidx.hilt.work.HiltWorker;
import androidx.work.Constraints;
import androidx.work.ExistingPeriodicWorkPolicy;
import androidx.work.NetworkType;
import androidx.work.PeriodicWorkRequest;
import androidx.work.WorkManager;
import androidx.work.Worker;
import androidx.work.WorkerParameters;
import com.littleorbit.data.repository.ReleaseRepository;
import com.littleorbit.data.ManagedWatchStore;
import com.littleorbit.domain.ReleaseUpdate;
import com.littleorbit.domain.UpdatePolicy;
import dagger.assisted.Assisted;
import dagger.assisted.AssistedInject;
import java.time.Instant;
import java.util.concurrent.TimeUnit;

/** Six-hour metadata-only update discovery with no automatic APK download. */
@HiltWorker
public final class UpdateDiscoveryWorker extends Worker {
    private static final String UNIQUE = "little-orbit-update-discovery";
    private final Context context;
    private final ReleaseRepository releases;
    private final ApkVerifier verifier;
    private final WearReleaseClient wearReleases;
    private final ManagedWatchStore watches;

    /** Creates the background discovery boundary. */
    @AssistedInject
    public UpdateDiscoveryWorker(@Assisted @NonNull Context context,
            @Assisted @NonNull WorkerParameters parameters, ReleaseRepository releases,
            ApkVerifier verifier, WearReleaseClient wearReleases, ManagedWatchStore watches) {
        super(context, parameters);
        this.context = context;
        this.releases = releases;
        this.verifier = verifier;
        this.wearReleases = wearReleases;
        this.watches = watches;
    }

    @NonNull
    @Override
    public Result doWork() {
        try {
            ReleaseUpdate release = releases.refresh().get(30, TimeUnit.SECONDS);
            UpdatePolicy.Decision decision = UpdatePolicy.evaluate(
                    release, (int) verifier.installedVersionCode(), Build.VERSION.SDK_INT,
                    Instant.now());
            boolean enabled = context.getSharedPreferences(
                    "little-orbit-updater-state", Context.MODE_PRIVATE)
                    .getBoolean("auto_detection_enabled", false);
            if (decision == UpdatePolicy.Decision.REQUIRED
                    || enabled && decision == UpdatePolicy.Decision.OPTIONAL) {
                notifyAvailable(release, decision == UpdatePolicy.Decision.REQUIRED);
            }
            checkWatchUpdate();
            return Result.success();
        } catch (Exception unavailable) {
            return getRunAttemptCount() < 3 ? Result.retry() : Result.failure();
        }
    }

    private void checkWatchUpdate() {
        ManagedWatchStore.Snapshot watch = watches.read();
        if (!watch.enabled() || !watch.updateAlerts() || watch.versionCode() <= 0) return;
        try {
            WearReleaseMetadata release = wearReleases.metadata();
            if (release.versionCode() > watch.versionCode()) notifyWatchAvailable(release);
        } catch (Exception ignored) {
            // Phone update discovery can still succeed when independent Wear metadata is absent.
        }
    }

    private void notifyWatchAvailable(WearReleaseMetadata release) {
        if (!PermissionChecks.notificationsGranted(context)) return;
        android.content.SharedPreferences state = context.getSharedPreferences(
                "little-orbit-watch-update-notices", Context.MODE_PRIVATE);
        if (release.version().equals(state.getString("notified_version", ""))) return;
        state.edit().putString("notified_version", release.version()).apply();
        Intent open = new Intent(context, WatchSettingsActivity.class)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        PendingIntent content = PendingIntent.getActivity(context, 7303, open,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        NotificationCompat.Builder notification = new NotificationCompat.Builder(
                context, NotificationChannels.UPDATES)
                .setSmallIcon(R.drawable.ic_watch)
                .setContentTitle(context.getString(R.string.watch_update_notification_title))
                .setContentText(context.getString(
                        R.string.watch_update_available, release.version()))
                .setContentIntent(content).setAutoCancel(true)
                .setVisibility(NotificationCompat.VISIBILITY_PRIVATE);
        try {
            NotificationManagerCompat.from(context).notify(7303, notification.build());
        } catch (SecurityException revoked) {
            // The Watch settings page still shows the metadata result when opened.
        }
    }

    private void notifyAvailable(ReleaseUpdate release, boolean required) {
        if (!PermissionChecks.notificationsGranted(context)) return;
        android.content.SharedPreferences state = context.getSharedPreferences(
                "little-orbit-updater-state", Context.MODE_PRIVATE);
        String prior = state.getString("notified_release_id", "");
        if (release.releaseId().equals(prior) && !required) return;
        state.edit().putString("notified_release_id", release.releaseId()).apply();
        Intent open = new Intent(context, AppUpdatesActivity.class)
                .putExtra(AppUpdatesActivity.EXTRA_SHOW_UPDATE, true)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        PendingIntent content = PendingIntent.getActivity(context, 7302, open,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        NotificationCompat.Builder notification = new NotificationCompat.Builder(
                context, NotificationChannels.UPDATES)
                .setSmallIcon(R.drawable.ic_countdown)
                .setContentTitle(context.getString(required
                        ? R.string.update_required_title : R.string.update_available))
                .setContentText(context.getString(
                        R.string.update_notification_message, release.version()))
                .setContentIntent(content)
                .setAutoCancel(true)
                .setVisibility(NotificationCompat.VISIBILITY_PRIVATE);
        try {
            NotificationManagerCompat.from(context).notify(7302, notification.build());
        } catch (SecurityException revoked) {
            // Required update still appears when the app next opens.
        }
    }

    /** Keeps required-update discovery active; preference controls optional prompts. */
    public static void schedule(Context context) {
        Constraints network = new Constraints.Builder()
                .setRequiredNetworkType(NetworkType.CONNECTED).build();
        PeriodicWorkRequest request = new PeriodicWorkRequest.Builder(
                UpdateDiscoveryWorker.class, 6, TimeUnit.HOURS)
                .setConstraints(network).build();
        WorkManager.getInstance(context).enqueueUniquePeriodicWork(
                UNIQUE, ExistingPeriodicWorkPolicy.UPDATE, request);
    }
}
