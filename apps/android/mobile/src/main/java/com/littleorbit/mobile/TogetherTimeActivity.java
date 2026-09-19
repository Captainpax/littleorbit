package com.littleorbit.mobile;

import android.content.Intent;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.view.View;
import com.littleorbit.data.remote.TogetherTimeModels;
import com.littleorbit.data.repository.OrbitRepository;
import com.littleorbit.mobile.databinding.ActivityTogetherTimeBinding;
import dagger.hilt.android.AndroidEntryPoint;
import java.time.Instant;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.time.format.FormatStyle;
import java.util.ArrayList;
import java.util.List;
import javax.inject.Inject;

/** Live nearby-time dashboard with explicit health and history destinations. */
@AndroidEntryPoint
public final class TogetherTimeActivity extends OrbitShellActivity {
    private static final long REFRESH_MILLIS = 30_000;
    @Inject OrbitRepository orbit;
    @Inject TogetherHealthReporter healthReporter;
    private final Handler mainHandler = new Handler(Looper.getMainLooper());
    private final Runnable ticker = this::tick;
    private final Runnable refresher = this::refresh;
    private ActivityTogetherTimeBinding binding;
    private TogetherTimeProjection projection;
    private boolean visible;
    private int summaryRequest;

    @Override protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        binding = ActivityTogetherTimeBinding.inflate(getLayoutInflater());
        setContentView(binding.getRoot());
        binding.fixCountingButton.setOnClickListener(view -> open(TogetherTimeFixActivity.class));
        binding.dailyDetailsButton.setOnClickListener(
                view -> open(TogetherTimeDayActivity.class));
        binding.correctDayButton.setOnClickListener(
                view -> open(TogetherTimeCorrectionActivity.class));
        setOrbitContextActions(List.of(
                new ContextAction(getString(R.string.fix_counting),
                        () -> open(TogetherTimeFixActivity.class)),
                new ContextAction(getString(R.string.see_daily_details),
                        () -> open(TogetherTimeDayActivity.class))));
    }

    @Override protected void onStart() {
        super.onStart();
        visible = true;
        refresh();
        mainHandler.post(ticker);
    }

    @Override protected void onStop() {
        visible = false;
        summaryRequest++;
        mainHandler.removeCallbacks(ticker);
        mainHandler.removeCallbacks(refresher);
        super.onStop();
    }

    @Override protected OrbitDestination orbitDestination() {
        return OrbitDestination.TOGETHER;
    }

    private void open(Class<?> destination) {
        OrbitMotion.start(this, new Intent(this, destination));
    }

    private void refresh() {
        if (!visible) return;
        loadSummary();
        loadHistory();
        loadHealth();
        healthReporter.publish();
        mainHandler.removeCallbacks(refresher);
        mainHandler.postDelayed(refresher, REFRESH_MILLIS);
    }

    private void tick() {
        if (!visible) return;
        renderDuration();
        mainHandler.postDelayed(ticker, 1000 - SystemClock.elapsedRealtime() % 1000);
    }

    private void loadSummary() {
        int request = ++summaryRequest;
        orbit.togetherSummaryV3().whenComplete((value, failure) -> runOnUiThread(() -> {
            if (!visible || request != summaryRequest || isDestroyed()) return;
            if (failure != null || value == null) {
                binding.statusText.setText(R.string.request_failed);
                return;
            }
            binding.statusText.setText("");
            showSummary(value);
        }));
    }

    private void showSummary(TogetherTimeModels.PairSummary summary) {
        long now = SystemClock.elapsedRealtime();
        long previous = projection == null ? -1 : projection.valueAt(now);
        projection = TogetherTimeProjection.from(summary, now);
        binding.adjustmentText.setVisibility(
                previous > projection.valueAt(now) + 1 ? View.VISIBLE : View.GONE);
        binding.collectionState.setText(stateDescription(summary.countingState));
        binding.evidenceText.setText(evidenceDescription(summary));
        binding.legacyText.setVisibility(
                summary.includesLegacyEstimates ? View.VISIBLE : View.GONE);
        renderDuration();
    }

    private void renderDuration() {
        if (projection == null) return;
        long seconds = projection.valueAt(SystemClock.elapsedRealtime());
        long days = seconds / 86_400;
        long hours = seconds % 86_400 / 3_600;
        long minutes = seconds % 3_600 / 60;
        long remainder = seconds % 60;
        binding.summaryText.setText(days > 0
                ? getString(R.string.nearby_duration_days, days, hours, minutes, remainder)
                : getString(R.string.nearby_duration, hours, minutes, remainder));
    }

    private String evidenceDescription(TogetherTimeModels.PairSummary summary) {
        String processed = summary.nearbyLastProcessedAt == null
                ? getString(R.string.never)
                : DateTimeFormatter.ofLocalizedDateTime(FormatStyle.MEDIUM)
                        .withZone(ZoneId.systemDefault())
                        .format(Instant.parse(summary.nearbyLastProcessedAt));
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
            case "sharing_disabled" -> R.string.nearby_state_sharing_disabled;
            default -> R.string.location_server_off;
        };
    }

    private void loadHistory() {
        orbit.togetherHistory().thenAccept(history -> runOnUiThread(() -> {
            List<String> rows = new ArrayList<>();
            int first = Math.max(0, history.size() - 7);
            for (TogetherTimeModels.HistoryDay day : history.subList(first, history.size())) {
                if (day.estimatedSeconds == 0 && !day.corrected) continue;
                rows.add(getString(R.string.together_history_breakdown,
                        day.day,
                        day.estimatedSeconds / 3_600,
                        day.estimatedSeconds % 3_600 / 60,
                        day.bridgedSeconds / 60));
            }
            binding.historyText.setText(rows.isEmpty()
                    ? getString(R.string.no_nearby_history) : String.join("\n", rows));
        })).exceptionally(failure -> null);
    }

    private void loadHealth() {
        orbit.togetherDeviceHealth().thenAccept(value -> runOnUiThread(() ->
                binding.deviceHealthText.setText(getString(
                        R.string.phone_health_summary,
                        value.mine.isEmpty()
                                ? getString(R.string.health_private)
                                : getString(R.string.health_shared),
                        value.partner.isEmpty()
                                ? getString(R.string.health_private)
                                : getString(R.string.health_shared)))))
                .exceptionally(failure -> null);
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
