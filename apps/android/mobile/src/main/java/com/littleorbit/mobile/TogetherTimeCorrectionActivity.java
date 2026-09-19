package com.littleorbit.mobile;

import android.os.Bundle;
import com.google.android.material.datepicker.MaterialDatePicker;
import com.littleorbit.data.remote.TogetherTimeModels;
import com.littleorbit.data.repository.OrbitRepository;
import com.littleorbit.mobile.databinding.ActivityTogetherTimeCorrectionBinding;
import dagger.hilt.android.AndroidEntryPoint;
import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneOffset;
import java.util.List;
import javax.inject.Inject;

/** Audited correction flow for one completed shared-home calendar day. */
@AndroidEntryPoint
public final class TogetherTimeCorrectionActivity extends InsetAwareActivity {
    @Inject OrbitRepository orbit;
    private ActivityTogetherTimeCorrectionBinding binding;
    private List<TogetherTimeModels.HistoryDay> days = List.of();
    private TogetherTimeModels.HistoryDay selected;

    @Override protected void onCreate(Bundle state) {
        super.onCreate(state);
        binding = ActivityTogetherTimeCorrectionBinding.inflate(getLayoutInflater());
        setContentView(binding.getRoot());
        binding.chooseDayButton.setOnClickListener(view -> chooseDay());
        binding.applyButton.setOnClickListener(view -> apply());
        load();
    }

    private void load() {
        orbit.togetherHistory().thenAccept(value -> runOnUiThread(() -> {
            days = List.copyOf(value);
            binding.statusText.setText("");
        })).exceptionally(failure -> {
            runOnUiThread(() -> binding.statusText.setText(R.string.request_failed));
            return null;
        });
    }

    private void chooseDay() {
        MaterialDatePicker<Long> picker = MaterialDatePicker.Builder.datePicker()
                .setTitleText(R.string.choose_completed_day)
                .build();
        picker.addOnPositiveButtonClickListener(value -> {
            LocalDate wanted = Instant.ofEpochMilli(value).atZone(ZoneOffset.UTC).toLocalDate();
            selected = days.stream().filter(day -> wanted.toString().equals(day.day))
                    .findFirst().orElse(null);
            if (selected == null) {
                binding.statusText.setText(R.string.day_not_available);
                return;
            }
            binding.chooseDayButton.setText(selected.day);
            binding.comparisonText.setText(getString(R.string.correction_before,
                    selected.estimatedSeconds / 3_600,
                    selected.estimatedSeconds % 3_600 / 60));
        });
        picker.show(getSupportFragmentManager(), "together-day");
    }

    private void apply() {
        Integer hours = integer(binding.hoursInput.getText().toString());
        Integer minutes = integer(binding.minutesInput.getText().toString());
        String reason = binding.reasonInput.getText().toString().trim();
        if (selected == null || hours == null || minutes == null || hours < 0 || minutes < 0
                || minutes > 59 || reason.length() < 3) {
            binding.statusText.setText(R.string.complete_required_fields);
            return;
        }
        long seconds = hours * 3_600L + minutes * 60L;
        if (seconds > selected.dayLengthSeconds) {
            binding.statusText.setText(R.string.correction_exceeds_day);
            return;
        }
        binding.comparisonText.setText(getString(R.string.correction_before_after,
                selected.estimatedSeconds / 3_600,
                selected.estimatedSeconds % 3_600 / 60,
                hours, minutes));
        AsyncUi.observe(this, orbit.correctTogetherDay(selected.day,
                new TogetherTimeModels.DayCorrection(seconds, selected.revision, reason)),
                binding.statusText, result -> {
                    selected = result;
                    binding.statusText.setText(R.string.correction_saved);
                });
    }

    private static Integer integer(String value) {
        try {
            return Integer.valueOf(value);
        } catch (NumberFormatException invalid) {
            return null;
        }
    }
}
