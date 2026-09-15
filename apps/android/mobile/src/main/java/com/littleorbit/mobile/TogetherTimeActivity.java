package com.littleorbit.mobile;

import android.os.Bundle;
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

/** Pair-age clock, coordinate-free nearby estimate, and audited corrections. */
@AndroidEntryPoint
public final class TogetherTimeActivity extends OrbitShellActivity {
    @Inject OrbitRepository orbit;
    private ActivityTogetherTimeBinding binding;
    private List<TogetherTimeModels.HistoryDay> correctableDays = List.of();

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        binding = ActivityTogetherTimeBinding.inflate(getLayoutInflater());
        setContentView(binding.getRoot());
        setOrbitContextActions(java.util.List.of(
                new ContextAction(getString(R.string.location_setup),
                        () -> startActivity(new android.content.Intent(
                                this, DeviceSetupActivity.class)))));
        binding.correctButton.setOnClickListener(view -> correct());
        load();
    }

    @Override
    protected OrbitDestination orbitDestination() {
        return OrbitDestination.TOGETHER;
    }

    private void load() {
        AsyncUi.observe(this, orbit.togetherSummaryV3(), binding.statusText, this::showSummary);
        AsyncUi.observe(this, orbit.togetherHistory(), binding.statusText, this::showHistory);
    }

    private void showSummary(TogetherTimeModels.PairSummary summary) {
        long nearbyHours = summary.nearbyEstimatedSeconds / 3_600;
        long nearbyMinutes = (summary.nearbyEstimatedSeconds % 3_600) / 60;
        String processed = summary.nearbyLastProcessedAt == null
                ? getString(R.string.never) : displayInstant(summary.nearbyLastProcessedAt);
        int dayQuantity = (int) Math.min(Integer.MAX_VALUE, summary.pairedDays);
        binding.summaryText.setText(getResources().getQuantityString(
                R.plurals.visual_together_summary,
                dayQuantity,
                summary.pairedDays,
                displayInstant(summary.pairedAt),
                nearbyHours,
                nearbyMinutes,
                processed,
                summary.proximityThresholdM));
        binding.summaryText.append("\n" + getString(
                R.string.nearby_confidence, confidenceLabel(summary.nearbyConfidence)));
        binding.collectionState.setText(summary.locationByBoth
                ? R.string.nearby_collection_active : summary.locationByMe
                        ? R.string.location_waiting_partner : R.string.location_server_off);
    }

    private static String displayInstant(String value) {
        return DateTimeFormatter.ofLocalizedDateTime(FormatStyle.MEDIUM)
                .withZone(ZoneId.systemDefault()).format(Instant.parse(value));
    }

    private void showHistory(List<TogetherTimeModels.HistoryDay> history) {
        StringBuilder text = new StringBuilder();
        for (TogetherTimeModels.HistoryDay day : history) {
            if (day.estimatedSeconds == 0 && !day.corrected) continue;
            String correction = day.corrected ? getString(
                    R.string.corrected_suffix,
                    day.correctedByDisplayName == null
                            ? getString(R.string.a_partner) : day.correctedByDisplayName) : "";
            text.append(getString(
                    R.string.visual_nearby_history_row,
                    displayDay(day.day),
                    day.estimatedSeconds / 3_600,
                    (day.estimatedSeconds % 3_600) / 60,
                    correction)).append('\n');
        }
        binding.historyText.setText(text.length() == 0
                ? getString(R.string.no_nearby_history) : text.toString().trim());
        showCorrectableDays(history);
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
                    (day.estimatedSeconds % 3_600) / 60));
        }
        binding.dayPicker.setAdapter(new ArrayAdapter<>(
                this, android.R.layout.simple_spinner_dropdown_item, labels));
        binding.correctButton.setEnabled(!correctableDays.isEmpty());
    }

    private void correct() {
        int index = binding.dayPicker.getSelectedItemPosition();
        if (index < 0 || index >= correctableDays.size()) return;
        int hours;
        int minutes;
        try {
            hours = Integer.parseInt(binding.hoursInput.getText().toString());
            minutes = Integer.parseInt(binding.minutesInput.getText().toString());
        } catch (NumberFormatException invalid) {
            binding.statusText.setText(R.string.complete_required_fields);
            return;
        }
        String reason = binding.reasonInput.getText().toString().trim();
        if (hours < 0 || hours > 24 || minutes < 0 || minutes > 59
                || (hours == 24 && minutes != 0) || reason.length() < 3) {
            binding.statusText.setText(R.string.complete_required_fields);
            return;
        }
        TogetherTimeModels.HistoryDay selected = correctableDays.get(index);
        AsyncUi.observe(this, orbit.correctTogetherDay(selected.day,
                new TogetherTimeModels.DayCorrection(
                        hours * 3_600L + minutes * 60L, selected.revision, reason)),
                binding.statusText, ignored -> load());
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
