package com.littleorbit.mobile;

import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.view.View;
import android.widget.ArrayAdapter;
import com.littleorbit.data.remote.TogetherTimeModels;
import com.littleorbit.data.repository.OrbitRepository;
import com.littleorbit.mobile.databinding.ActivityTogetherTimeBinding;
import dagger.hilt.android.AndroidEntryPoint;
import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneId;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.time.format.DateTimeParseException;
import java.time.format.FormatStyle;
import java.util.ArrayList;
import java.util.List;
import javax.inject.Inject;

/** Live nearby-time estimate and audited coordinate-free daily corrections. */
@AndroidEntryPoint
public final class TogetherTimeActivity extends OrbitShellActivity {
    private static final long SUMMARY_REFRESH_MILLIS = 30_000;
    @Inject OrbitRepository orbit;
    private final Handler mainHandler = new Handler(Looper.getMainLooper());
    private final Runnable ticker = this::tick;
    private final Runnable refresher = this::refresh;
    private ActivityTogetherTimeBinding binding;
    private List<TogetherTimeModels.HistoryDay> correctableDays = List.of();
    private TogetherTimeProjection projection;
    private boolean visible;
    private int summaryRequest;
    private int historyRequest;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        binding = ActivityTogetherTimeBinding.inflate(getLayoutInflater());
        setContentView(binding.getRoot());
        setOrbitContextActions(List.of(new ContextAction(
                getString(R.string.location_setup),
                () -> startActivity(new android.content.Intent(
                        this, DeviceSetupActivity.class)))));
        binding.correctButton.setOnClickListener(view -> correct());
    }

    @Override
    protected void onStart() {
        super.onStart();
        visible = true;
        loadSummary();
        loadHistory();
        mainHandler.post(ticker);
        mainHandler.postDelayed(refresher, SUMMARY_REFRESH_MILLIS);
    }

    @Override
    protected void onStop() {
        visible = false;
        summaryRequest++;
        historyRequest++;
        mainHandler.removeCallbacks(ticker);
        mainHandler.removeCallbacks(refresher);
        super.onStop();
    }

    @Override
    protected OrbitDestination orbitDestination() {
        return OrbitDestination.TOGETHER;
    }

    private void refresh() {
        if (!visible) return;
        loadSummary();
        mainHandler.postDelayed(refresher, SUMMARY_REFRESH_MILLIS);
    }

    private void tick() {
        if (!visible) return;
        renderDuration();
        long delay = 1000 - SystemClock.elapsedRealtime() % 1000;
        mainHandler.postDelayed(ticker, delay);
    }

    private void loadSummary() {
        int request = ++summaryRequest;
        orbit.togetherSummaryV3().whenComplete((value, failure) -> runOnUiThread(() -> {
            if (!currentSummaryRequest(request)) return;
            if (failure != null || value == null) {
                binding.statusText.setText(R.string.request_failed);
                return;
            }
            binding.statusText.setText("");
            showSummary(value);
        }));
    }

    private void loadHistory() {
        int request = ++historyRequest;
        orbit.togetherHistory().whenComplete((value, failure) -> runOnUiThread(() -> {
            if (!currentHistoryRequest(request)) return;
            if (failure != null || value == null) {
                binding.statusText.setText(R.string.request_failed);
                return;
            }
            showHistory(value);
        }));
    }

    private boolean currentSummaryRequest(int request) {
        return visible && request == summaryRequest && !isDestroyed();
    }

    private boolean currentHistoryRequest(int request) {
        return visible && request == historyRequest && !isDestroyed();
    }

    private void showSummary(TogetherTimeModels.PairSummary summary) {
        long now = SystemClock.elapsedRealtime();
        long previous = projection == null ? -1 : projection.valueAt(now);
        projection = TogetherTimeProjection.from(summary, now);
        long current = projection.valueAt(now);
        binding.adjustmentText.setVisibility(previous > current + 1 ? View.VISIBLE : View.GONE);
        binding.collectionState.setText(stateDescription(summary.countingState));
        binding.evidenceText.setText(evidenceDescription(summary));
        binding.legacyText.setVisibility(
                summary.includesLegacyEstimates ? View.VISIBLE : View.GONE);
        renderDuration();
    }

    private void renderDuration() {
        if (projection == null) return;
        long seconds = projection.valueAt(SystemClock.elapsedRealtime());
        binding.summaryText.setText(compactDuration(seconds));
        binding.summaryText.setContentDescription(spokenDuration(seconds));
    }

    private String compactDuration(long totalSeconds) {
        long days = totalSeconds / 86_400;
        long hours = totalSeconds % 86_400 / 3_600;
        long minutes = totalSeconds % 3_600 / 60;
        long seconds = totalSeconds % 60;
        return days > 0
                ? getString(R.string.nearby_duration_days, days, hours, minutes, seconds)
                : getString(R.string.nearby_duration, hours, minutes, seconds);
    }

    private String spokenDuration(long totalSeconds) {
        int days = (int) Math.min(Integer.MAX_VALUE, totalSeconds / 86_400);
        int hours = (int) (totalSeconds % 86_400 / 3_600);
        int minutes = (int) (totalSeconds % 3_600 / 60);
        int seconds = (int) (totalSeconds % 60);
        return getString(R.string.nearby_duration_spoken,
                getResources().getQuantityString(R.plurals.days, days, days),
                getResources().getQuantityString(R.plurals.hours, hours, hours),
                getResources().getQuantityString(R.plurals.minutes, minutes, minutes),
                getResources().getQuantityString(R.plurals.seconds, seconds, seconds));
    }

    private String evidenceDescription(TogetherTimeModels.PairSummary summary) {
        String processed = summary.nearbyLastProcessedAt == null
                ? getString(R.string.never) : displayInstant(summary.nearbyLastProcessedAt);
        return getString(R.string.nearby_evidence,
                processed, confidenceLabel(summary.nearbyConfidence),
                summary.proximityThresholdM);
    }

    private int stateDescription(String state) {
        return switch (state) {
            case "nearby" -> R.string.nearby_state_counting;
            case "confirming" -> R.string.nearby_state_confirming;
            case "apart" -> R.string.nearby_state_apart;
            case "poor_accuracy" -> R.string.nearby_state_poor_accuracy;
            case "stale" -> R.string.nearby_state_stale;
            case "waiting_for_partner" -> R.string.location_waiting_partner;
            default -> R.string.location_server_off;
        };
    }

    private static String displayInstant(String value) {
        return DateTimeFormatter.ofLocalizedDateTime(FormatStyle.MEDIUM)
                .withZone(ZoneId.systemDefault()).format(Instant.parse(value));
    }

    private void showHistory(List<TogetherTimeModels.HistoryDay> history) {
        List<String> rows = new ArrayList<>();
        for (TogetherTimeModels.HistoryDay day : history) {
            if (day.estimatedSeconds != 0 || day.corrected) rows.add(historyRow(day));
        }
        binding.historyText.setText(rows.isEmpty()
                ? getString(R.string.no_nearby_history) : String.join("\n", rows));
        showCorrectableDays(history);
    }

    private String historyRow(TogetherTimeModels.HistoryDay day) {
        String correction = day.corrected ? getString(
                R.string.corrected_suffix,
                day.correctedByDisplayName == null
                        ? getString(R.string.a_partner) : day.correctedByDisplayName) : "";
        String provenance = switch (day.estimateMethod) {
            case "legacy_v2" -> getString(R.string.legacy_estimate_suffix);
            case "mixed" -> getString(R.string.mixed_estimate_suffix);
            default -> "";
        };
        return getString(R.string.visual_nearby_history_row,
                displayDay(day.day), day.estimatedSeconds / 3_600,
                day.estimatedSeconds % 3_600 / 60, correction + provenance);
    }

    private static String displayDay(String value) {
        try {
            return LocalDate.parse(value).format(
                    DateTimeFormatter.ofLocalizedDate(FormatStyle.MEDIUM));
        } catch (DateTimeParseException invalid) {
            return value;
        }
    }

    private void showCorrectableDays(List<TogetherTimeModels.HistoryDay> results) {
        LocalDate today = LocalDate.now(ZoneOffset.UTC);
        List<TogetherTimeModels.HistoryDay> filtered = new ArrayList<>();
        for (TogetherTimeModels.HistoryDay day : results) {
            if (LocalDate.parse(day.day).isBefore(today)) filtered.add(day);
        }
        correctableDays = List.copyOf(filtered);
        List<String> labels = new ArrayList<>();
        for (TogetherTimeModels.HistoryDay day : correctableDays) {
            labels.add(getString(R.string.nearby_day_choice, day.day,
                    day.estimatedSeconds / 3_600,
                    day.estimatedSeconds % 3_600 / 60));
        }
        binding.dayPicker.setAdapter(new ArrayAdapter<>(
                this, android.R.layout.simple_spinner_dropdown_item, labels));
        binding.correctButton.setEnabled(!correctableDays.isEmpty());
    }

    private void correct() {
        int index = binding.dayPicker.getSelectedItemPosition();
        if (index < 0 || index >= correctableDays.size()) return;
        Integer hours = integer(binding.hoursInput.getText().toString());
        Integer minutes = integer(binding.minutesInput.getText().toString());
        String reason = binding.reasonInput.getText().toString().trim();
        if (!validCorrection(hours, minutes, reason)) {
            binding.statusText.setText(R.string.complete_required_fields);
            return;
        }
        TogetherTimeModels.HistoryDay selected = correctableDays.get(index);
        AsyncUi.observe(this, orbit.correctTogetherDay(selected.day,
                new TogetherTimeModels.DayCorrection(
                        hours * 3_600L + minutes * 60L, selected.revision, reason)),
                binding.statusText, ignored -> {
                    loadSummary();
                    loadHistory();
                });
    }

    private static Integer integer(String value) {
        try {
            return Integer.valueOf(value);
        } catch (NumberFormatException invalid) {
            return null;
        }
    }

    private static boolean validCorrection(Integer hours, Integer minutes, String reason) {
        return hours != null && minutes != null && hours >= 0 && hours <= 24
                && minutes >= 0 && minutes <= 59 && (hours != 24 || minutes == 0)
                && reason.length() >= 3;
    }

    private String confidenceLabel(String confidence) {
        return switch (confidence) {
            case "high" -> getString(R.string.confidence_high);
            case "medium" -> getString(R.string.confidence_medium);
            case "low" -> getString(R.string.confidence_low);
            default -> getString(R.string.confidence_unavailable);
        };
    }
}
