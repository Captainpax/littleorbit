package com.littleorbit.mobile;

import android.Manifest;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Bundle;
import android.view.View;
import android.widget.AdapterView;
import android.widget.ArrayAdapter;
import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.content.ContextCompat;
import androidx.work.Data;
import androidx.work.ExistingWorkPolicy;
import androidx.work.OneTimeWorkRequest;
import androidx.work.WorkManager;
import com.littleorbit.data.remote.ApiModels;
import com.littleorbit.data.repository.OrbitRepository;
import com.littleorbit.mobile.databinding.ActivityCountdownBinding;
import dagger.hilt.android.AndroidEntryPoint;
import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.TimeUnit;
import javax.inject.Inject;

/** Shared countdown CRUD with optimistic revisions and local reminder scheduling. */
@AndroidEntryPoint
public final class CountdownActivity extends InsetAwareActivity {
    @Inject OrbitRepository orbit;
    private ActivityCountdownBinding binding;
    private List<ApiModels.Countdown> countdowns = List.of();
    private ApiModels.Countdown pendingReminder;
    private final ActivityResultLauncher<String> notificationPermission =
            registerForActivityResult(
                    new ActivityResultContracts.RequestPermission(),
                    granted -> {
                        if (granted && pendingReminder != null) {
                            QuizStatusWorker.schedule(this);
                            scheduleReminder(pendingReminder);
                        } else if (!granted) {
                            binding.statusText.setText(R.string.notifications_needed);
                        }
                        pendingReminder = null;
                    });

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        binding = ActivityCountdownBinding.inflate(getLayoutInflater());
        setContentView(binding.getRoot());
        binding.createButton.setOnClickListener(view -> create());
        binding.updateButton.setOnClickListener(view -> update());
        binding.deleteButton.setOnClickListener(view -> delete());
        binding.countdownPicker.setOnItemSelectedListener(new CountdownSelection());
        load();
    }

    private void load() {
        AsyncUi.observe(this, orbit.countdowns(), binding.statusText, this::render);
    }

    private void render(List<ApiModels.Countdown> results) {
        countdowns = results;
        String content = countdowns.stream()
                .map(item -> item.title + "\n" + item.occursAt + " · " + item.timezone
                        + syncLabel(item))
                .reduce((left, right) -> left + "\n\n" + right)
                .orElse(getString(R.string.no_countdowns));
        binding.countdownList.setText(content);
        List<String> titles = new ArrayList<>();
        for (ApiModels.Countdown countdown : countdowns) {
            titles.add(countdown.title);
        }
        binding.countdownPicker.setAdapter(new ArrayAdapter<>(
                this,
                android.R.layout.simple_spinner_dropdown_item,
                titles));
        binding.updateButton.setEnabled(!countdowns.isEmpty());
        binding.deleteButton.setEnabled(!countdowns.isEmpty());
    }

    private static String syncLabel(ApiModels.Countdown item) {
        if (item.syncConflict) {
            return " · sync conflict — review and save again";
        }
        return item.pendingSync ? " · pending sync" : "";
    }

    private void create() {
        ApiModels.CountdownMutation mutation = mutationFromForm(null);
        if (mutation == null) {
            return;
        }
        AsyncUi.observe(this, orbit.createCountdown(mutation), binding.statusText, result -> {
            requestReminder(result);
            load();
        });
    }

    private void update() {
        ApiModels.Countdown selected = selected();
        if (selected == null) {
            return;
        }
        ApiModels.CountdownMutation mutation = mutationFromForm(selected.revision);
        if (mutation == null) {
            return;
        }
        AsyncUi.observe(
                this,
                orbit.updateCountdown(selected.id, mutation),
                binding.statusText,
                result -> {
                    requestReminder(result);
                    load();
                });
    }

    private void delete() {
        ApiModels.Countdown selected = selected();
        if (selected == null) {
            return;
        }
        ApiModels.CountdownDeleteRequest request = new ApiModels.CountdownDeleteRequest(
                UUID.randomUUID().toString(), selected.revision);
        AsyncUi.observe(
                this,
                orbit.deleteCountdown(selected.id, request),
                binding.statusText,
                ignored -> {
                    WorkManager.getInstance(this).cancelUniqueWork(reminderName(selected.id));
                    load();
                });
    }

    private ApiModels.CountdownMutation mutationFromForm(Integer revision) {
        String title = binding.titleInput.getText().toString().trim();
        String occursAt = binding.timeInput.getText().toString().trim();
        String timezone = binding.timezoneInput.getText().toString().trim();
        try {
            Instant.parse(occursAt);
        } catch (RuntimeException invalid) {
            binding.statusText.setText(R.string.iso_time_required);
            return null;
        }
        if (title.isEmpty() || timezone.isEmpty()) {
            binding.statusText.setText(R.string.complete_required_fields);
            return null;
        }
        return new ApiModels.CountdownMutation(
                UUID.randomUUID().toString(),
                title,
                occursAt,
                timezone,
                binding.notesInput.getText().toString(),
                revision);
    }

    private ApiModels.Countdown selected() {
        int position = binding.countdownPicker.getSelectedItemPosition();
        return position >= 0 && position < countdowns.size() ? countdowns.get(position) : null;
    }

    private void requestReminder(ApiModels.Countdown countdown) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU
                || ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS)
                        == PackageManager.PERMISSION_GRANTED) {
            scheduleReminder(countdown);
            return;
        }
        pendingReminder = countdown;
        notificationPermission.launch(Manifest.permission.POST_NOTIFICATIONS);
    }

    private void scheduleReminder(ApiModels.Countdown countdown) {
        long delay = Math.max(
                0,
                Duration.between(Instant.now(), Instant.parse(countdown.occursAt)).toMillis());
        Data input = new Data.Builder().putString("title", countdown.title).build();
        OneTimeWorkRequest request = new OneTimeWorkRequest.Builder(CountdownReminderWorker.class)
                .setInputData(input)
                .setInitialDelay(delay, TimeUnit.MILLISECONDS)
                .build();
        WorkManager.getInstance(this).enqueueUniqueWork(
                reminderName(countdown.id), ExistingWorkPolicy.REPLACE, request);
    }

    private static String reminderName(String countdownId) {
        return "countdown-reminder-" + countdownId;
    }

    private final class CountdownSelection implements AdapterView.OnItemSelectedListener {
        @Override
        public void onItemSelected(AdapterView<?> parent, View view, int position, long id) {
            ApiModels.Countdown selected = countdowns.get(position);
            binding.titleInput.setText(selected.title);
            binding.timeInput.setText(selected.occursAt);
            binding.timezoneInput.setText(selected.timezone);
            binding.notesInput.setText(selected.notes);
        }

        @Override
        public void onNothingSelected(AdapterView<?> parent) {
            // Empty lists intentionally leave the create form untouched.
        }
    }
}
