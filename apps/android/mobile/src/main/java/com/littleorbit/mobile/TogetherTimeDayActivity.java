package com.littleorbit.mobile;

import android.os.Bundle;
import android.view.View;
import android.widget.AdapterView;
import android.widget.ArrayAdapter;
import com.littleorbit.data.remote.TogetherTimeModels;
import com.littleorbit.data.repository.OrbitRepository;
import com.littleorbit.mobile.databinding.ActivityTogetherTimeDayBinding;
import dagger.hilt.android.AndroidEntryPoint;
import java.time.Instant;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.List;
import javax.inject.Inject;

/** Coordinate-free observed and estimated timeline for one shared-home day. */
@AndroidEntryPoint
public final class TogetherTimeDayActivity extends InsetAwareActivity {
    @Inject OrbitRepository orbit;
    private ActivityTogetherTimeDayBinding binding;
    private List<TogetherTimeModels.HistoryDay> days = List.of();
    private int request;

    @Override protected void onCreate(Bundle state) {
        super.onCreate(state);
        binding = ActivityTogetherTimeDayBinding.inflate(getLayoutInflater());
        setContentView(binding.getRoot());
        binding.dayPicker.setOnItemSelectedListener(new AdapterView.OnItemSelectedListener() {
            @Override public void onItemSelected(
                    AdapterView<?> parent, View view, int position, long id) {
                if (position >= 0 && position < days.size()) loadDay(days.get(position));
            }
            @Override public void onNothingSelected(AdapterView<?> parent) {}
        });
        load();
    }

    private void load() {
        binding.statusText.setText(R.string.loading);
        orbit.togetherHistory().thenAccept(value -> runOnUiThread(() -> {
            days = List.copyOf(value);
            List<String> labels = new ArrayList<>();
            for (TogetherTimeModels.HistoryDay day : days) labels.add(day.day);
            binding.dayPicker.setAdapter(new ArrayAdapter<>(
                    this, android.R.layout.simple_spinner_dropdown_item, labels));
            if (days.isEmpty()) binding.statusText.setText(R.string.no_nearby_history);
        })).exceptionally(failure -> {
            runOnUiThread(() -> binding.statusText.setText(R.string.request_failed));
            return null;
        });
    }

    private void loadDay(TogetherTimeModels.HistoryDay day) {
        int wanted = ++request;
        binding.summaryText.setText(getString(R.string.day_evidence_summary,
                day.observedSeconds / 60, day.bridgedSeconds / 60,
                day.unverifiedSeconds / 60, day.apartSeconds / 60,
                day.poorAccuracySeconds / 60));
        orbit.togetherDayDetails(day.day).thenAccept(value -> runOnUiThread(() -> {
            if (wanted != request) return;
            binding.statusText.setText("");
            binding.timelineText.setText(timeline(value));
        })).exceptionally(failure -> {
            runOnUiThread(() -> binding.statusText.setText(R.string.request_failed));
            return null;
        });
    }

    private String timeline(TogetherTimeModels.DayDetails details) {
        if (details.segments.isEmpty()) return getString(R.string.no_timeline_evidence);
        ZoneId zone = ZoneId.of(details.timezone);
        DateTimeFormatter time = DateTimeFormatter.ofPattern("h:mm a").withZone(zone);
        StringBuilder result = new StringBuilder();
        String state = null;
        String start = null;
        String end = null;
        for (TogetherTimeModels.DaySegment segment : details.segments) {
            if (!segment.evidenceState.equals(state)) {
                appendSpan(result, start, end, state);
                state = segment.evidenceState;
                start = time.format(Instant.parse(segment.startsAt));
            }
            end = time.format(Instant.parse(segment.endsAt));
        }
        appendSpan(result, start, end, state);
        return result.toString();
    }

    private void appendSpan(StringBuilder target, String start, String end, String state) {
        if (state == null) return;
        if (target.length() > 0) target.append('\n');
        target.append(start).append("–").append(end).append(" · ")
                .append(state.replace('_', ' '));
    }
}
