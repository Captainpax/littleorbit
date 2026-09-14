package com.littleorbit.mobile;

import android.Manifest;
import android.animation.ValueAnimator;
import android.content.pm.PackageManager;
import android.graphics.Typeface;
import android.os.Build;
import android.os.Bundle;
import android.view.View;
import android.widget.LinearLayout;
import android.widget.TextView;
import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;
import androidx.core.content.ContextCompat;
import androidx.transition.TransitionManager;
import com.littleorbit.data.remote.CountdownApiModels;
import com.littleorbit.data.repository.OrbitRepository;
import com.littleorbit.mobile.databinding.ActivityCountdownBinding;
import dagger.hilt.android.AndroidEntryPoint;
import java.time.Duration;
import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneId;
import java.time.ZonedDateTime;
import java.time.format.DateTimeFormatter;
import java.time.format.FormatStyle;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import javax.inject.Inject;

/** Calendar-first countdown timeline with private reminders and one-way export. */
@AndroidEntryPoint
public final class CountdownActivity extends OrbitShellActivity {
    @Inject OrbitRepository orbit;
    private ActivityCountdownBinding binding;
    private List<CountdownApiModels.Countdown> countdowns = List.of();
    private List<CountdownApiModels.Countdown> past = List.of();
    private CountdownApiModels.Countdown next;
    private final ActivityResultLauncher<String> notificationPermission =
            registerForActivityResult(
                    new ActivityResultContracts.RequestPermission(),
                    granted -> {
                        if (!granted) binding.statusText.setText(R.string.notifications_needed);
                    });

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        binding = ActivityCountdownBinding.inflate(getLayoutInflater());
        setContentView(binding.getRoot());
        binding.newButton.setOnClickListener(view -> openEditor(null));
        binding.editHero.setOnClickListener(view -> openEditor(next));
        binding.addHeroToCalendar.setOnClickListener(view -> addToCalendar(next));
        binding.pastToggle.setOnClickListener(view -> togglePast());
        setOrbitContextActions(List.of(
                new ContextAction(getString(R.string.new_countdown), () -> openEditor(null)),
                new ContextAction(getString(R.string.show_past_moments), this::togglePast)));
        load();
    }

    @Override
    protected OrbitDestination orbitDestination() { return OrbitDestination.COUNTDOWNS; }

    private void load() {
        AsyncUi.observe(this, orbit.countdowns(), binding.statusText, this::render);
    }

    private void render(List<CountdownApiModels.Countdown> results) {
        animate();
        List<CountdownApiModels.Countdown> sorted = new ArrayList<>(results);
        sorted.sort(Comparator.comparing(CountdownActivity::eventInstant));
        countdowns = List.copyOf(sorted);
        List<CountdownApiModels.Countdown> future = new ArrayList<>();
        List<CountdownApiModels.Countdown> history = new ArrayList<>();
        for (CountdownApiModels.Countdown item : countdowns) {
            (isPast(item) ? history : future).add(item);
        }
        next = future.isEmpty() ? null : future.get(0);
        Collections.reverse(history);
        past = List.copyOf(history);
        renderHero();
        renderRows(binding.upcomingContainer, next == null ? future : future.subList(1, future.size()));
        renderRows(binding.pastContainer, past);
        boolean empty = countdowns.isEmpty();
        binding.emptyText.setVisibility(empty ? View.VISIBLE : View.GONE);
        binding.upcomingLabel.setVisibility(future.size() > 1 ? View.VISIBLE : View.GONE);
        binding.pastToggle.setVisibility(past.isEmpty() ? View.GONE : View.VISIBLE);
        CountdownReminderScheduler.reconcile(this, countdowns);
    }

    private void renderHero() {
        binding.heroCard.setVisibility(next == null ? View.GONE : View.VISIBLE);
        if (next == null) return;
        binding.heroTitle.setText(next.title);
        binding.heroRemaining.setText(remaining(next));
        binding.heroDate.setText(displayTime(next));
    }

    private void renderRows(LinearLayout container, List<CountdownApiModels.Countdown> values) {
        container.removeAllViews();
        for (CountdownApiModels.Countdown item : values) container.addView(row(item));
    }

    private View row(CountdownApiModels.Countdown item) {
        LinearLayout card = new LinearLayout(this);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setPadding(dp(20), dp(16), dp(20), dp(16));
        card.setBackgroundResource(R.drawable.card_background_muted);
        TextView title = text(item.title, 20, true);
        TextView when = text(displayTime(item) + syncLabel(item), 15, false);
        when.setTextColor(getColor(R.color.lavender_soft));
        card.addView(title);
        card.addView(when);
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        params.topMargin = dp(10);
        card.setLayoutParams(params);
        card.setOnClickListener(view -> openEditor(item));
        return card;
    }

    private TextView text(String value, int size, boolean bold) {
        TextView view = new TextView(this);
        view.setText(value);
        view.setTextColor(getColor(R.color.cloud));
        view.setTextSize(size);
        if (bold) view.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        return view;
    }

    private void openEditor(CountdownApiModels.Countdown existing) {
        new CountdownEditorDialog(this, existing, new CountdownEditorDialog.Listener() {
            @Override public void save(CountdownEditorDialog.EditResult result) {
                saveEdit(existing, result);
            }
            @Override public void delete(CountdownApiModels.Countdown countdown) {
                deleteCountdown(countdown);
            }
        }).show();
    }

    private void saveEdit(
            CountdownApiModels.Countdown existing, CountdownEditorDialog.EditResult edit) {
        CompletableFuture<CountdownApiModels.Countdown> mutation = existing == null
                ? orbit.createCountdown(edit.mutation())
                : orbit.updateCountdown(existing.id, edit.mutation());
        CompletableFuture<CountdownApiModels.Countdown> complete = mutation.thenCompose(saved ->
                saved.pendingSync
                        ? CompletableFuture.completedFuture(saved)
                        : orbit.replaceCountdownReminders(saved.id, edit.reminders()));
        AsyncUi.observe(this, complete, binding.statusText, saved -> {
            binding.statusText.setText(R.string.countdown_saved);
            if (!edit.reminders().isEmpty()) requestNotificationPermission();
            if (edit.addToCalendar()) CountdownCalendarExporter.open(this, saved);
            load();
        });
    }

    private void deleteCountdown(CountdownApiModels.Countdown selected) {
        CountdownApiModels.DeleteRequest request = new CountdownApiModels.DeleteRequest(
                UUID.randomUUID().toString(), selected.revision);
        AsyncUi.observe(this, orbit.deleteCountdown(selected.id, request), binding.statusText,
                ignored -> {
                    binding.statusText.setText(R.string.countdown_deleted);
                    load();
                });
    }

    private void requestNotificationPermission() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU
                && ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS)
                        != PackageManager.PERMISSION_GRANTED) {
            notificationPermission.launch(Manifest.permission.POST_NOTIFICATIONS);
        }
    }

    private void addToCalendar(CountdownApiModels.Countdown value) {
        if (value != null) CountdownCalendarExporter.open(this, value);
    }

    private void togglePast() {
        if (past.isEmpty()) return;
        animate();
        boolean show = binding.pastContainer.getVisibility() != View.VISIBLE;
        binding.pastContainer.setVisibility(show ? View.VISIBLE : View.GONE);
        binding.pastToggle.setText(show ? R.string.hide_past_moments : R.string.show_past_moments);
    }

    private void animate() {
        if (ValueAnimator.areAnimatorsEnabled()) TransitionManager.beginDelayedTransition(binding.getRoot());
    }

    private static boolean isPast(CountdownApiModels.Countdown value) {
        if ("all_day".equals(value.timingKind) && value.occursOn != null) {
            return LocalDate.parse(value.occursOn).isBefore(LocalDate.now());
        }
        return eventInstant(value).isBefore(Instant.now());
    }

    private static Instant eventInstant(CountdownApiModels.Countdown value) {
        return Instant.parse(value.occursAt);
    }

    private String displayTime(CountdownApiModels.Countdown value) {
        if ("all_day".equals(value.timingKind) && value.occursOn != null) {
            return LocalDate.parse(value.occursOn)
                    .format(DateTimeFormatter.ofLocalizedDate(FormatStyle.MEDIUM))
                    + " · " + getString(R.string.all_day_event);
        }
        ZoneId deviceZone = ZoneId.systemDefault();
        ZonedDateTime local = eventInstant(value).atZone(deviceZone);
        String result = local.format(DateTimeFormatter.ofLocalizedDateTime(FormatStyle.MEDIUM));
        return deviceZone.getId().equals(value.timezone)
                ? result : result + " · " + value.timezone;
    }

    private static String remaining(CountdownApiModels.Countdown value) {
        long hours = Math.max(0, Duration.between(Instant.now(), eventInstant(value)).toHours());
        return (hours / 24) + " days  " + String.format(java.util.Locale.getDefault(), "%02d", hours % 24)
                + " hours";
    }

    private static String syncLabel(CountdownApiModels.Countdown value) {
        if (value.syncConflict) return " · sync conflict";
        return value.pendingSync ? " · pending sync" : "";
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }
}
