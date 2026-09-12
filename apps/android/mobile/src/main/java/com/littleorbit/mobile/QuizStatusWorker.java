package com.littleorbit.mobile;

import android.Manifest;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import androidx.annotation.NonNull;
import androidx.core.app.NotificationCompat;
import androidx.core.content.ContextCompat;
import androidx.hilt.work.HiltWorker;
import androidx.work.Constraints;
import androidx.work.ExistingPeriodicWorkPolicy;
import androidx.work.NetworkType;
import androidx.work.PeriodicWorkRequest;
import androidx.work.WorkManager;
import androidx.work.Worker;
import androidx.work.WorkerParameters;
import com.littleorbit.data.remote.QuizApiModels;
import com.littleorbit.data.repository.NetworkOrbitRepository;
import com.littleorbit.data.repository.OrbitRepository;
import dagger.assisted.Assisted;
import dagger.assisted.AssistedInject;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.TimeUnit;

/** Polls content-free quiz state and announces only meaningful partner transitions. */
@HiltWorker
public final class QuizStatusWorker extends Worker {
    private static final String CHANNEL = "quiz_updates";
    private static final String PREFS = "quiz_status";
    private final OrbitRepository orbit;

    /** Creates the authenticated polling worker. */
    @AssistedInject
    public QuizStatusWorker(
            @Assisted @NonNull Context context,
            @Assisted @NonNull WorkerParameters parameters,
            OrbitRepository orbit) {
        super(context, parameters);
        this.orbit = orbit;
    }

    @NonNull
    @Override
    public Result doWork() {
        try {
            QuizApiModels.Status status = orbit.quizStatus().get(30, TimeUnit.SECONDS);
            publishTransitions(status);
            return Result.success();
        } catch (Exception unavailable) {
            if (isSignedOut(unavailable)) return Result.success();
            return retryOrFail();
        }
    }

    private static boolean isSignedOut(Exception failure) {
        Throwable cause = failure instanceof ExecutionException ? failure.getCause() : failure;
        return cause instanceof NetworkOrbitRepository.OrbitServiceException service
                && (service.statusCode() == 401 || service.statusCode() == 409);
    }

    private void publishTransitions(QuizApiModels.Status status) {
        SharedPreferences preferences = getApplicationContext()
                .getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        String priorDate = preferences.getString("quiz_date", "");
        boolean priorPartner = priorDate.equals(status.quizDate)
                && preferences.getBoolean("partner_finished", false);
        boolean priorReveal = priorDate.equals(status.quizDate)
                && preferences.getBoolean("revealed", false);
        if (!priorReveal && status.revealed) {
            notifyUser("Your answers are ready together", "See where your orbit aligned today.", 5202);
        } else if (!priorPartner && status.partnerFinished && !status.revealed) {
            notifyUser("Your partner finished today’s orbit", "Finish yours when you’re ready.", 5201);
        }
        preferences.edit()
                .putString("quiz_date", status.quizDate)
                .putBoolean("partner_finished", status.partnerFinished)
                .putBoolean("revealed", status.revealed)
                .apply();
    }

    private void notifyUser(String title, String text, int id) {
        Context context = getApplicationContext();
        if (ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS)
                != PackageManager.PERMISSION_GRANTED) return;
        NotificationManager manager = context.getSystemService(NotificationManager.class);
        manager.createNotificationChannel(new NotificationChannel(
                CHANNEL, "Daily quiz", NotificationManager.IMPORTANCE_DEFAULT));
        Intent intent = new Intent(context, QuizActivity.class);
        PendingIntent pending = PendingIntent.getActivity(
                context, id, intent, PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
        manager.notify(id, new NotificationCompat.Builder(context, CHANNEL)
                .setSmallIcon(R.mipmap.ic_launcher)
                .setContentTitle(title)
                .setContentText(text)
                .setContentIntent(pending)
                .setAutoCancel(true)
                .build());
    }

    private Result retryOrFail() {
        return getRunAttemptCount() < 3 ? Result.retry() : Result.failure();
    }

    /** Schedules Android's minimum 15-minute server-only status polling. */
    public static void schedule(Context context) {
        Constraints constraints = new Constraints.Builder()
                .setRequiredNetworkType(NetworkType.CONNECTED)
                .build();
        PeriodicWorkRequest request = new PeriodicWorkRequest.Builder(
                QuizStatusWorker.class, 15, TimeUnit.MINUTES)
                .setConstraints(constraints)
                .build();
        WorkManager.getInstance(context).enqueueUniquePeriodicWork(
                "little-orbit-quiz-status", ExistingPeriodicWorkPolicy.UPDATE, request);
    }
}
