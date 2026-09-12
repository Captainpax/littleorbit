package com.littleorbit.mobile;

import android.os.Bundle;
import android.widget.ArrayAdapter;
import androidx.appcompat.app.AppCompatActivity;
import com.littleorbit.data.remote.ApiModels;
import com.littleorbit.data.remote.TogetherTimeModels;
import com.littleorbit.data.repository.OrbitRepository;
import com.littleorbit.mobile.databinding.ActivityTogetherTimeBinding;
import dagger.hilt.android.AndroidEntryPoint;
import java.util.ArrayList;
import java.util.List;
import java.time.Duration;
import java.time.LocalDate;
import java.util.UUID;
import javax.inject.Inject;

/** Coordinate-free together-time estimate and audited correction surface. */
@AndroidEntryPoint
public final class TogetherTimeActivity extends InsetAwareActivity {
    @Inject OrbitRepository orbit;
    private ActivityTogetherTimeBinding binding;
    private List<ApiModels.TogetherBucket> buckets = List.of();
    private TogetherTimeModels.StartDateProposal pendingProposal;
    private String proposalOperationId;
    private String proposalOperationDate;
    private String decisionOperationId;
    private String decisionKey;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        binding = ActivityTogetherTimeBinding.inflate(getLayoutInflater());
        setContentView(binding.getRoot());
        binding.correctButton.setOnClickListener(view -> correct());
        binding.proposeDateButton.setOnClickListener(view -> proposeDate());
        binding.acceptDateButton.setOnClickListener(view -> decideDate("accept"));
        binding.declineDateButton.setOnClickListener(view -> decideDate("decline"));
        binding.cancelDateButton.setOnClickListener(view -> decideDate("cancel"));
        load();
    }

    private void load() {
        AsyncUi.observe(this, orbit.togetherSummaryV2(), binding.statusText, this::showSummary);
        AsyncUi.observe(this, orbit.togetherHistory(), binding.statusText, this::showHistory);
        AsyncUi.observe(this, orbit.togetherBuckets(), binding.statusText, this::showBuckets);
    }

    private void showSummary(TogetherTimeModels.Summary summary) {
        String relationship = summary.relationshipDays == null
                ? getString(R.string.start_date_unset)
                : getString(R.string.relationship_age_days, summary.relationshipDays);
        long nearbyHours = summary.nearbyEstimatedSeconds / 3_600;
        long nearbyMinutes = (summary.nearbyEstimatedSeconds % 3_600) / 60;
        String processed = summary.nearbyLastProcessedAt == null
                ? getString(R.string.never)
                : summary.nearbyLastProcessedAt;
        binding.summaryText.setText(getString(
                R.string.together_summary_v2,
                relationship,
                nearbyHours,
                nearbyMinutes,
                processed));
        if (summary.relationshipStartDate != null
                && binding.startDateInput.getText().length() == 0) {
            binding.startDateInput.setText(summary.relationshipStartDate);
        }
        pendingProposal = summary.pendingStartDate;
        renderProposal();
    }

    private void showHistory(List<TogetherTimeModels.HistoryDay> history) {
        StringBuilder text = new StringBuilder();
        for (TogetherTimeModels.HistoryDay day : history) {
            if (day.estimatedSeconds == 0 && !day.corrected) continue;
            text.append(day.day)
                    .append(" · ")
                    .append(day.estimatedSeconds / 3_600)
                    .append("h ")
                    .append((day.estimatedSeconds % 3_600) / 60)
                    .append("m")
                    .append(day.corrected ? " · corrected" : "")
                    .append('\n');
        }
        binding.historyText.setText(
                text.length() == 0 ? getString(R.string.no_nearby_history) : text.toString().trim());
    }

    private void proposeDate() {
        String value = binding.startDateInput.getText().toString().trim();
        try {
            LocalDate.parse(value);
        } catch (RuntimeException invalid) {
            binding.statusText.setText(R.string.start_date_format);
            return;
        }
        if (!value.equals(proposalOperationDate)) {
            proposalOperationDate = value;
            proposalOperationId = UUID.randomUUID().toString();
        }
        TogetherTimeModels.ProposalRequest request =
                new TogetherTimeModels.ProposalRequest(proposalOperationId, value);
        AsyncUi.observe(this, orbit.proposeStartDate(request), binding.statusText, result -> {
            proposalOperationId = null;
            proposalOperationDate = null;
            load();
        });
    }

    private void decideDate(String decision) {
        if (pendingProposal == null) return;
        String key = pendingProposal.id + ":" + decision;
        if (!key.equals(decisionKey)) {
            decisionKey = key;
            decisionOperationId = UUID.randomUUID().toString();
        }
        TogetherTimeModels.DecisionRequest request =
                new TogetherTimeModels.DecisionRequest(decisionOperationId, decision);
        AsyncUi.observe(
                this,
                orbit.decideStartDate(pendingProposal.id, request),
                binding.statusText,
                result -> {
                    decisionKey = null;
                    decisionOperationId = null;
                    load();
                });
    }

    private void renderProposal() {
        boolean visible = pendingProposal != null;
        binding.pendingDateText.setVisibility(visible ? android.view.View.VISIBLE : android.view.View.GONE);
        binding.acceptDateButton.setVisibility(
                visible && !pendingProposal.proposedByMe
                        ? android.view.View.VISIBLE : android.view.View.GONE);
        binding.declineDateButton.setVisibility(
                visible && !pendingProposal.proposedByMe
                        ? android.view.View.VISIBLE : android.view.View.GONE);
        binding.cancelDateButton.setVisibility(
                visible && pendingProposal.proposedByMe
                        ? android.view.View.VISIBLE : android.view.View.GONE);
        if (visible) {
            binding.pendingDateText.setText(getString(
                    pendingProposal.proposedByMe
                            ? R.string.start_date_waiting
                            : R.string.start_date_partner_proposed,
                    pendingProposal.proposedDate));
        }
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
