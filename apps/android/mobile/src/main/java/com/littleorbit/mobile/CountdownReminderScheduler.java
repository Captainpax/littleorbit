package com.littleorbit.mobile;

import android.content.Context;
import androidx.work.Data;
import androidx.work.ExistingWorkPolicy;
import androidx.work.OneTimeWorkRequest;
import androidx.work.WorkManager;
import com.littleorbit.data.remote.CountdownApiModels;
import java.time.Duration;
import java.time.Instant;
import java.time.LocalDate;
import java.time.LocalTime;
import java.time.ZoneId;
import java.util.List;
import java.util.concurrent.TimeUnit;

/** Reconciles private local reminder work from account-synced countdown state. */
final class CountdownReminderScheduler {
    static final String TAG = "little-orbit-countdown-reminder";

    private CountdownReminderScheduler() {}

    static void reconcile(Context context, List<CountdownApiModels.Countdown> values) {
        WorkManager manager = WorkManager.getInstance(context);
        manager.cancelAllWorkByTag(TAG);
        for (CountdownApiModels.Countdown value : values) {
            for (int offset : value.reminderOffsets) schedule(manager, value, offset);
        }
    }

    private static void schedule(
            WorkManager manager, CountdownApiModels.Countdown value, int offsetMinutes) {
        Instant alert = reminderInstant(value).minus(Duration.ofMinutes(offsetMinutes));
        long delay = Duration.between(Instant.now(), alert).toMillis();
        if (delay <= 0) return;
        Data input = new Data.Builder()
                .putString("countdown_id", value.id)
                .putString("title", value.title)
                .build();
        OneTimeWorkRequest work = new OneTimeWorkRequest.Builder(CountdownReminderWorker.class)
                .setInputData(input)
                .setInitialDelay(delay, TimeUnit.MILLISECONDS)
                .addTag(TAG)
                .build();
        manager.enqueueUniqueWork(
                TAG + "-" + value.id + "-" + offsetMinutes,
                ExistingWorkPolicy.REPLACE,
                work);
    }

    static Instant reminderInstant(CountdownApiModels.Countdown value) {
        if ("all_day".equals(value.timingKind) && value.occursOn != null) {
            return LocalDate.parse(value.occursOn)
                    .atTime(LocalTime.of(9, 0))
                    .atZone(ZoneId.of(value.timezone))
                    .toInstant();
        }
        return Instant.parse(value.occursAt);
    }
}
