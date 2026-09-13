package com.littleorbit.mobile;

import android.os.Bundle;
import android.widget.Button;
import com.littleorbit.data.SmoochSendWorker;
import com.littleorbit.data.remote.ApiModels;
import com.littleorbit.data.remote.SmoochApiModels;
import com.littleorbit.data.repository.NetworkOrbitRepository;
import com.littleorbit.data.repository.OrbitRepository;
import com.littleorbit.data.repository.SmoochOutbox;
import com.littleorbit.mobile.databinding.ActivitySmoochBinding;
import dagger.hilt.android.AndroidEntryPoint;
import java.time.ZoneId;
import java.util.List;
import java.util.UUID;
import javax.inject.Inject;

/** Playful nine-emoji Smooch sender with durable weekly history. */
@AndroidEntryPoint
public final class SmoochActivity extends InsetAwareActivity {
    private static final List<String> EMOJIS = List.of(
            "😘", "😍", "🤭", "😈", "🔥", "👀", "💖", "🐻", "🍑");
    @Inject OrbitRepository orbit;
    @Inject SmoochOutbox outbox;
    private ActivitySmoochBinding binding;
    private String selected = EMOJIS.get(0);

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        binding = ActivitySmoochBinding.inflate(getLayoutInflater());
        setContentView(binding.getRoot());
        bindEmojiButtons();
        binding.sendSmoochButton.setOnClickListener(view -> send());
        android.content.SharedPreferences settings = getSharedPreferences(
                "smooch_settings", MODE_PRIVATE);
        binding.revealSmooches.setChecked(settings.getBoolean("full_lock_screen", false));
        binding.revealSmooches.setOnCheckedChangeListener((button, checked) ->
                settings.edit().putBoolean("full_lock_screen", checked).apply());
        binding.usePhoneTimezone.setOnClickListener(view -> usePhoneTimezone());
        loadTimezone();
        loadHistory();
    }

    private void bindEmojiButtons() {
        List<Button> buttons = List.of(binding.emoji0, binding.emoji1, binding.emoji2,
                binding.emoji3, binding.emoji4, binding.emoji5, binding.emoji6,
                binding.emoji7, binding.emoji8);
        for (int index = 0; index < buttons.size(); index++) {
            Button button = buttons.get(index);
            String emoji = EMOJIS.get(index);
            button.setText(emoji);
            button.setOnClickListener(view -> {
                selected = emoji;
                binding.selectedSmooch.setText(getString(R.string.smooch_selected, emoji));
            });
        }
        binding.selectedSmooch.setText(getString(R.string.smooch_selected, selected));
    }

    private void send() {
        String operationId = UUID.randomUUID().toString();
        binding.sendSmoochButton.setEnabled(false);
        orbit.sendSmooch(new SmoochApiModels.SendRequest(operationId, selected))
                .whenComplete((sent, failure) -> runOnUiThread(() -> {
                    binding.sendSmoochButton.setEnabled(true);
                    if (failure == null) {
                        binding.smoochStatus.setText(getString(
                                R.string.smooch_sent_status, sent.partnerName, sent.remaining));
                        loadHistory();
                    } else if (statusCode(failure) == -1) {
                        outbox.enqueue(operationId, selected, System.currentTimeMillis());
                        SmoochSendWorker.enqueue(this);
                        binding.smoochStatus.setText(R.string.smooch_queued);
                    } else if (statusCode(failure) == 429) {
                        binding.smoochStatus.setText(R.string.smooch_rate_limited);
                    } else {
                        binding.smoochStatus.setText(R.string.request_failed);
                    }
                }));
    }

    private void loadHistory() {
        orbit.smoochWeeks(12).thenAccept(weeks -> runOnUiThread(() -> showHistory(weeks)))
                .exceptionally(failure -> null);
    }

    private void loadTimezone() {
        orbit.preferences().thenAccept(preferences -> runOnUiThread(() -> {
            binding.smoochWeekZone.setText(getString(
                    R.string.smooch_week_timezone, preferences.homeTimezone));
            binding.usePhoneTimezone.setEnabled(
                    !ZoneId.systemDefault().getId().equals(preferences.homeTimezone));
        })).exceptionally(failure -> null);
    }

    private void usePhoneTimezone() {
        binding.usePhoneTimezone.setEnabled(false);
        ApiModels.PreferencesMutation mutation = new ApiModels.PreferencesMutation(
                null, null, null, ZoneId.systemDefault().getId());
        orbit.updatePreferences(mutation).whenComplete((preferences, failure) ->
                runOnUiThread(() -> {
                    if (failure == null) {
                        loadTimezone();
                        loadHistory();
                    } else {
                        binding.usePhoneTimezone.setEnabled(true);
                        binding.smoochStatus.setText(R.string.request_failed);
                    }
                }));
    }

    private void showHistory(List<SmoochApiModels.Week> weeks) {
        if (weeks.isEmpty()) {
            binding.weeklyHistory.setText(R.string.smooch_no_history);
            return;
        }
        StringBuilder text = new StringBuilder();
        for (int index = weeks.size() - 1; index >= 0; index--) {
            SmoochApiModels.Week week = weeks.get(index);
            if (week.combined == 0 && index < weeks.size() - 2) continue;
            text.append(getString(R.string.smooch_week_row, week.weekStart,
                    week.sent, week.received, week.combined));
            if (!week.emojiCounts.isEmpty()) text.append("\n").append(week.emojiCounts);
            text.append("\n\n");
        }
        binding.weeklyHistory.setText(text.toString().trim());
    }

    private static int statusCode(Throwable failure) {
        Throwable current = failure;
        while (current.getCause() != null && !(current
                instanceof NetworkOrbitRepository.OrbitServiceException)) {
            current = current.getCause();
        }
        return current instanceof NetworkOrbitRepository.OrbitServiceException service
                ? service.statusCode() : -1;
    }
}
