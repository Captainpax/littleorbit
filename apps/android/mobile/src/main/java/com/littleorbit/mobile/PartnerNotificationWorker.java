package com.littleorbit.mobile;

import android.Manifest;
import android.app.Notification;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import androidx.annotation.NonNull;
import androidx.core.app.NotificationCompat;
import androidx.core.app.NotificationManagerCompat;
import androidx.core.content.ContextCompat;
import androidx.hilt.work.HiltWorker;
import androidx.work.BackoffPolicy;
import androidx.work.Constraints;
import androidx.work.ExistingPeriodicWorkPolicy;
import androidx.work.ExistingWorkPolicy;
import androidx.work.NetworkType;
import androidx.work.OneTimeWorkRequest;
import androidx.work.PeriodicWorkRequest;
import androidx.work.WorkManager;
import androidx.work.Worker;
import androidx.work.WorkerParameters;
import com.littleorbit.data.remote.NotificationApiModels;
import com.littleorbit.data.remote.SmoochApiModels;
import com.littleorbit.data.repository.OrbitServiceException;
import com.littleorbit.data.repository.OrbitRepository;
import dagger.assisted.Assisted;
import dagger.assisted.AssistedInject;
import java.time.DayOfWeek;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.TimeUnit;

/** Polls the self-hosted API and acknowledges alerts only after Android posts them. */
@HiltWorker
public final class PartnerNotificationWorker extends Worker {
    private static final String PERIODIC = "little-orbit-partner-notifications";
    private static final String NOW = "little-orbit-partner-notifications-now";
    private final Context context;
    private final OrbitRepository orbit;
    private final NotificationDeviceStore device;
    private NotificationSettingsStore settings;

    /** Creates an authenticated, per-installation notification worker. */
    @AssistedInject
    public PartnerNotificationWorker(
            @Assisted @NonNull Context context,
            @Assisted @NonNull WorkerParameters parameters,
            OrbitRepository orbit,
            NotificationDeviceStore device) {
        super(context, parameters);
        this.context = context;
        this.orbit = orbit;
        this.device = device;
        this.settings = new NotificationSettingsStore(context);
    }

    @NonNull
    @Override
    public Result doWork() {
        if (!orbit.isSignedIn()) return Result.success();
        try {
            boolean allowed = PermissionChecks.notificationsGranted(context);
            register(allowed);
            NotificationApiModels.Preferences preferences = orbit.notificationPreferences()
                    .get(30, TimeUnit.SECONDS);
            settings.save(preferences);
            reconcileCountdowns(preferences, allowed);
            if (!allowed || !preferences.master) {
                device.failed(allowed ? "Notifications paused in Little Orbit" : "Android permission is off");
                return Result.success();
            }
            int count = deliver(preferences);
            maybeNotifyWeeklyRecap(preferences);
            device.checked(count);
            return Result.success();
        } catch (Exception failure) {
            if (signedOut(failure)) {
                device.failed("Sign in again to receive alerts");
                return Result.success();
            }
            device.failed("Server check will retry");
            return getRunAttemptCount() < 3 ? Result.retry() : Result.failure();
        }
    }

    private void register(boolean allowed) throws Exception {
        orbit.registerNotificationDevice(device.id(),
                new NotificationApiModels.DeviceUpsert(BuildConfig.VERSION_CODE, allowed))
                .get(30, TimeUnit.SECONDS);
    }

    private int deliver(NotificationApiModels.Preferences preferences) throws Exception {
        List<NotificationApiModels.Event> pending = orbit.pendingNotifications(device.id())
                .get(30, TimeUnit.SECONDS);
        List<String> displayed = new ArrayList<>();
        for (NotificationApiModels.Event event : pending) {
            if (enabled(event, preferences) && post(event)) displayed.add(event.id);
        }
        if (!displayed.isEmpty()) {
            orbit.acknowledgeNotifications(device.id(), displayed).get(30, TimeUnit.SECONDS);
        }
        return displayed.size();
    }

    private static boolean enabled(
            NotificationApiModels.Event event, NotificationApiModels.Preferences preferences) {
        return switch (event.kind) {
            case "smooch_received" -> preferences.smooches;
            case "note_editing" -> preferences.noteEditing;
            case "countdown_created", "countdown_rescheduled" -> preferences.countdowns;
            case "quiz_available", "quiz_partner_finished", "quiz_results_ready" ->
                    preferences.dailyQuiz;
            default -> false;
        };
    }

    private boolean post(NotificationApiModels.Event event) {
        String channel = channel(event.kind);
        if (!PermissionChecks.channelEnabled(context, channel)) return false;
        Intent target = target(event);
        PendingIntent content = PendingIntent.getActivity(context, event.id.hashCode(),
                target.addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_SINGLE_TOP),
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        String body = message(event);
        Notification publicVersion = publicVersion(channel);
        Notification notification = new NotificationCompat.Builder(context, channel)
                .setSmallIcon(icon(event.kind))
                .setContentTitle(title(event.kind))
                .setContentText(body)
                .setStyle(new NotificationCompat.BigTextStyle().bigText(body))
                .setContentIntent(content)
                .setAutoCancel(true)
                .setVisibility(NotificationCompat.VISIBILITY_PRIVATE)
                .setPublicVersion(publicVersion)
                .build();
        try {
            NotificationManagerCompat.from(context).notify(event.id.hashCode(), notification);
            return true;
        } catch (SecurityException revoked) {
            return false;
        }
    }

    private String message(NotificationApiModels.Event event) {
        String partner = event.actorName == null
                ? context.getString(R.string.your_partner) : event.actorName;
        if ("note_editing".equals(event.kind)) {
            String title = event.noteTitle == null
                    ? context.getString(R.string.shared_note) : event.noteTitle;
            return context.getString(R.string.partner_editing_note, partner, title);
        }
        if ("countdown_created".equals(event.kind)) {
            return context.getString(R.string.countdown_created_notification, partner,
                    event.countdownTitle == null ? context.getString(R.string.countdowns) : event.countdownTitle);
        }
        if ("countdown_rescheduled".equals(event.kind)) {
            return context.getString(R.string.countdown_rescheduled_notification, partner,
                    event.countdownTitle == null ? context.getString(R.string.countdowns) : event.countdownTitle);
        }
        if ("quiz_available".equals(event.kind)) {
            return context.getString(R.string.quiz_available_notification);
        }
        if ("quiz_partner_finished".equals(event.kind)) {
            return context.getString(R.string.quiz_partner_finished_notification, partner);
        }
        if ("quiz_results_ready".equals(event.kind)) {
            return context.getString(R.string.quiz_results_notification);
        }
        return SmoochPhrases.render(context, event.phraseKey, partner, event.emoji);
    }

    private static String channel(String kind) {
        if ("note_editing".equals(kind)) return NotificationChannels.SHARED_SPACE;
        if (kind.startsWith("countdown_")) return NotificationChannels.COUNTDOWNS;
        if (kind.startsWith("quiz_")) return NotificationChannels.QUIZ;
        return NotificationChannels.SMOOCHES;
    }

    private Intent target(NotificationApiModels.Event event) {
        if ("note_editing".equals(event.kind)) {
            return new Intent(context, NotesActivity.class)
                    .putExtra(NotesActivity.EXTRA_NOTE_ID, event.noteId);
        }
        if (event.kind.startsWith("countdown_")) return new Intent(context, CountdownActivity.class);
        if (event.kind.startsWith("quiz_")) return new Intent(context, QuizActivity.class);
        return new Intent(context, SmoochActivity.class);
    }

    private int icon(String kind) {
        if ("note_editing".equals(kind)) return R.drawable.ic_notes;
        if (kind.startsWith("countdown_")) return R.drawable.ic_countdown;
        if (kind.startsWith("quiz_")) return R.drawable.ic_quiz;
        return R.drawable.ic_smooch;
    }

    private String title(String kind) {
        if ("note_editing".equals(kind)) return context.getString(R.string.space_notification_title);
        if (kind.startsWith("countdown_")) return context.getString(R.string.countdowns);
        if (kind.startsWith("quiz_")) return context.getString(R.string.quiz);
        return context.getString(R.string.smooches);
    }

    private Notification publicVersion(String channel) {
        return new NotificationCompat.Builder(context, channel)
                .setSmallIcon(R.drawable.ic_launcher_foreground)
                .setContentTitle(context.getString(R.string.private_notification_title))
                .setContentText(context.getString(R.string.private_notification_message))
                .build();
    }

    private void reconcileCountdowns(
            NotificationApiModels.Preferences preferences, boolean allowed) throws Exception {
        if (!allowed || !preferences.master || !preferences.countdowns) {
            CountdownReminderScheduler.reconcile(context, List.of());
            return;
        }
        CountdownReminderScheduler.reconcile(
                context, orbit.countdowns().get(30, TimeUnit.SECONDS));
    }

    private void maybeNotifyWeeklyRecap(NotificationApiModels.Preferences prefs) throws Exception {
        if (!prefs.weeklySummary || LocalDate.now().getDayOfWeek() != DayOfWeek.MONDAY) return;
        List<SmoochApiModels.Week> weeks = orbit.smoochWeeks(2).get(30, TimeUnit.SECONDS);
        if (weeks.size() < 2) return;
        SmoochApiModels.Week prior = weeks.get(0);
        android.content.SharedPreferences state = context.getSharedPreferences(
                "smooch_settings", Context.MODE_PRIVATE);
        if (prior.weekEnd.equals(state.getString("last_recap", ""))) return;
        String text = context.getString(R.string.smooch_weekly_notification, prior.combined);
        Notification notification = new NotificationCompat.Builder(context, NotificationChannels.SMOOCHES)
                .setSmallIcon(R.drawable.ic_smooch)
                .setContentTitle(context.getString(R.string.smooch_weekly_title))
                .setContentText(text).setAutoCancel(true)
                .setVisibility(NotificationCompat.VISIBILITY_PRIVATE)
                .setPublicVersion(publicVersion(NotificationChannels.SMOOCHES)).build();
        try {
            NotificationManagerCompat.from(context).notify(7310, notification);
            state.edit().putString("last_recap", prior.weekEnd).apply();
        } catch (SecurityException revoked) {
            // Permission can change after the worker's initial check.
        }
    }

    private static boolean signedOut(Exception failure) {
        Throwable cause = failure instanceof ExecutionException ? failure.getCause() : failure;
        return cause instanceof OrbitServiceException service
                && (service.statusCode() == 401 || service.statusCode() == 409);
    }

    /** Maintains one Android-minimum fallback poll while a session exists. */
    public static void schedule(Context context, boolean enabled) {
        WorkManager manager = WorkManager.getInstance(context);
        // Cancel RC11's account-wide queue so an in-place update cannot double-deliver.
        manager.cancelUniqueWork("little-orbit-smooch-status");
        manager.cancelUniqueWork("little-orbit-smooch-now");
        if (!enabled) {
            manager.cancelUniqueWork(PERIODIC);
            manager.cancelUniqueWork(NOW);
            return;
        }
        PeriodicWorkRequest request = new PeriodicWorkRequest.Builder(
                PartnerNotificationWorker.class, 15, TimeUnit.MINUTES)
                .setConstraints(network()).setBackoffCriteria(
                        BackoffPolicy.EXPONENTIAL, 30, TimeUnit.SECONDS).build();
        manager.enqueueUniquePeriodicWork(PERIODIC, ExistingPeriodicWorkPolicy.UPDATE, request);
    }

    /** Requests a prompt server check after a foreground hint or app resume. */
    public static void enqueue(Context context) {
        OneTimeWorkRequest request = new OneTimeWorkRequest.Builder(PartnerNotificationWorker.class)
                .setConstraints(network()).setBackoffCriteria(
                        BackoffPolicy.EXPONENTIAL, 30, TimeUnit.SECONDS).build();
        WorkManager.getInstance(context).enqueueUniqueWork(NOW, ExistingWorkPolicy.REPLACE, request);
    }

    private static Constraints network() {
        return new Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build();
    }
}
