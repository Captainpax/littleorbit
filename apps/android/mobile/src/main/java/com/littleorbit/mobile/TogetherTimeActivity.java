package com.littleorbit.mobile;

import android.os.Bundle;
import android.widget.ArrayAdapter;
import androidx.appcompat.app.AppCompatActivity;
import com.littleorbit.data.remote.ApiModels;
import com.littleorbit.data.repository.OrbitRepository;
import com.littleorbit.mobile.databinding.ActivityTogetherTimeBinding;
import dagger.hilt.android.AndroidEntryPoint;
import java.util.ArrayList;
import java.util.List;
import javax.inject.Inject;

/** Coordinate-free together-time estimate and audited correction surface. */
@AndroidEntryPoint
public final class TogetherTimeActivity extends AppCompatActivity {
    @Inject OrbitRepository orbit;
    private ActivityTogetherTimeBinding binding;
    private List<ApiModels.TogetherBucket> buckets = List.of();

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        binding = ActivityTogetherTimeBinding.inflate(getLayoutInflater());
        setContentView(binding.getRoot());
        binding.correctButton.setOnClickListener(view -> correct());
        load();
    }

    private void load() {
        AsyncUi.observe(this, orbit.togetherSummary(), binding.statusText, this::showSummary);
        AsyncUi.observe(this, orbit.togetherBuckets(), binding.statusText, this::showBuckets);
    }

    private void showSummary(ApiModels.TogetherSummary summary) {
        String updated = summary.lastUpdatedAt == null ? "never" : summary.lastUpdatedAt;
        binding.summaryText.setText(getString(
                R.string.together_estimate, summary.estimatedSeconds / 60, updated));
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
        if (buckets.isEmpty()) {
            binding.statusText.setText(R.string.no_together_buckets);
        }
    }

    private void correct() {
        int index = binding.bucketPicker.getSelectedItemPosition();
        if (index < 0 || index >= buckets.size()) {
            return;
        }
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
        AsyncUi.observe(
                this,
                orbit.correctTogetherBucket(
                        buckets.get(index).id,
                        new ApiModels.TogetherCorrectionRequest(seconds, reason)),
                binding.statusText,
                ignored -> load());
    }
}
