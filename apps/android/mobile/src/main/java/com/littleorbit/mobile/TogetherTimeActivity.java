package com.littleorbit.mobile;

import android.os.Bundle;
import android.widget.ArrayAdapter;
import com.littleorbit.data.remote.ApiModels;
import com.littleorbit.data.remote.TogetherTimeModels;
import com.littleorbit.data.repository.OrbitRepository;
import com.littleorbit.mobile.databinding.ActivityTogetherTimeBinding;
import dagger.hilt.android.AndroidEntryPoint;
import java.time.Instant;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.List;
import javax.inject.Inject;

/** Pair-age clock, coordinate-free nearby estimate, and audited corrections. */
@AndroidEntryPoint
public final class TogetherTimeActivity extends OrbitShellActivity {
    @Inject OrbitRepository orbit;
    private ActivityTogetherTimeBinding binding;
    private List<ApiModels.TogetherBucket> buckets = List.of();

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
        AsyncUi.observe(this, orbit.togetherBuckets(), binding.statusText, this::showBuckets);
    }

    private void showSummary(TogetherTimeModels.PairSummary summary) {
        long nearbyHours = summary.nearbyEstimatedSeconds / 3_600;
        long nearbyMinutes = (summary.nearbyEstimatedSeconds % 3_600) / 60;
        String processed = summary.nearbyLastProcessedAt == null
                ? getString(R.string.never) : displayInstant(summary.nearbyLastProcessedAt);
        binding.summaryText.setText(getString(
                R.string.together_summary_v3,
                summary.pairedDays,
                displayInstant(summary.pairedAt),
                nearbyHours,
                nearbyMinutes,
                processed,
                summary.proximityThresholdM));
        binding.collectionState.setText(summary.locationByBoth
                ? R.string.nearby_collection_active : summary.locationByMe
                        ? R.string.location_waiting_partner : R.string.location_server_off);
    }

    private static String displayInstant(String value) {
        return DateTimeFormatter.ofPattern("MMM d, yyyy · h:mm a")
                .withZone(ZoneId.systemDefault()).format(Instant.parse(value));
    }

    private void showHistory(List<TogetherTimeModels.HistoryDay> history) {
        StringBuilder text = new StringBuilder();
        for (TogetherTimeModels.HistoryDay day : history) {
            if (day.estimatedSeconds == 0 && !day.corrected) continue;
            text.append(day.day).append(" · ")
                    .append(day.estimatedSeconds / 3_600).append("h ")
                    .append((day.estimatedSeconds % 3_600) / 60).append("m")
                    .append(day.corrected ? " · corrected" : "").append('\n');
        }
        binding.historyText.setText(text.length() == 0
                ? getString(R.string.no_nearby_history) : text.toString().trim());
    }

    private void showBuckets(List<ApiModels.TogetherBucket> results) {
        buckets = results;
        List<String> labels = new ArrayList<>();
        for (ApiModels.TogetherBucket bucket : buckets) {
            labels.add(bucket.bucketStart + " · " + bucket.durationSeconds + "s");
        }
        binding.bucketPicker.setAdapter(new ArrayAdapter<>(
                this, android.R.layout.simple_spinner_dropdown_item, labels));
        binding.correctButton.setEnabled(!buckets.isEmpty());
    }

    private void correct() {
        int index = binding.bucketPicker.getSelectedItemPosition();
        if (index < 0 || index >= buckets.size()) return;
        int seconds;
        try {
            seconds = Integer.parseInt(binding.secondsInput.getText().toString());
        } catch (NumberFormatException invalid) {
            binding.statusText.setText(R.string.complete_required_fields);
            return;
        }
        String reason = binding.reasonInput.getText().toString().trim();
        if (seconds < 0 || seconds > 60 || reason.length() < 3) {
            binding.statusText.setText(R.string.complete_required_fields);
            return;
        }
        AsyncUi.observe(this, orbit.correctTogetherBucket(buckets.get(index).id,
                new ApiModels.TogetherCorrectionRequest(seconds, reason)),
                binding.statusText, ignored -> load());
    }
}
