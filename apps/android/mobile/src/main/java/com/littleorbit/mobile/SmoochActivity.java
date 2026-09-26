package com.littleorbit.mobile;

import android.animation.ValueAnimator;
import android.content.res.ColorStateList;
import android.os.Bundle;
import android.widget.LinearLayout;
import android.widget.TextView;
import androidx.annotation.StringRes;
import androidx.core.view.ViewCompat;
import com.google.android.material.button.MaterialButton;
import com.google.android.material.card.MaterialCardView;
import com.littleorbit.data.SmoochSendWorker;
import com.littleorbit.data.remote.ApiModels;
import com.littleorbit.data.remote.SmoochApiModels;
import com.littleorbit.data.repository.OrbitRepository;
import com.littleorbit.data.repository.SmoochOutbox;
import com.littleorbit.mobile.databinding.ActivitySmoochBinding;
import dagger.hilt.android.AndroidEntryPoint;
import java.time.ZoneId;
import java.util.List;
import java.util.Locale;
import java.util.UUID;
import javax.inject.Inject;

/** Playful nine-emoji Smooch sender with durable weekly history. */
@AndroidEntryPoint
public final class SmoochActivity extends OrbitShellActivity {
    private static final List<String> EMOJIS = List.of(
            "😘", "😍", "🤭", "😈", "🔥", "👀", "💖", "🐻", "🍑");
    private static final List<Integer> EMOJI_LABELS = List.of(
            R.string.rc14_smooch_kiss,
            R.string.rc14_smooch_love_eyes,
            R.string.rc14_smooch_shy,
            R.string.rc14_smooch_mischief,
            R.string.rc14_smooch_fire,
            R.string.rc14_smooch_eyes,
            R.string.rc14_smooch_heart,
            R.string.rc14_smooch_bear,
            R.string.rc14_smooch_peach);
    private static final String STATE_SELECTED = "selected_smooch";
    @Inject OrbitRepository orbit;
    @Inject SmoochOutbox outbox;
    private ActivitySmoochBinding binding;
    private String selected = EMOJIS.get(0);
    private String partnerName = "Partner";
    private List<MaterialButton> emojiButtons = List.of();

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        binding = ActivitySmoochBinding.inflate(getLayoutInflater());
        setContentView(binding.getRoot());
        if (savedInstanceState != null) {
            String restored = savedInstanceState.getString(STATE_SELECTED);
            if (EMOJIS.contains(restored)) selected = restored;
        }
        bindEmojiButtons();
        binding.sendSmoochButton.setOnClickListener(view -> send());
        setOrbitContextActions(List.of(
                new ContextAction(getString(R.string.smooch_history), this::loadHistory),
                new ContextAction(getString(R.string.this_week), this::loadStatus)));
        binding.usePhoneTimezone.setOnClickListener(view -> usePhoneTimezone());
        loadTimezone();
        loadStatus();
        loadHistory();
    }

    @Override
    protected OrbitDestination orbitDestination() {
        return OrbitDestination.SMOOCH;
    }

    private void bindEmojiButtons() {
        emojiButtons = List.of(binding.emoji0, binding.emoji1, binding.emoji2,
                binding.emoji3, binding.emoji4, binding.emoji5, binding.emoji6,
                binding.emoji7, binding.emoji8);
        for (int index = 0; index < emojiButtons.size(); index++) {
            MaterialButton button = emojiButtons.get(index);
            String emoji = EMOJIS.get(index);
            @StringRes int label = EMOJI_LABELS.get(index);
            button.setText(emoji);
            button.setContentDescription(getString(
                    R.string.rc14_smooch_choice_description, getString(label), emoji));
            button.setOnClickListener(view -> {
                selected = emoji;
                binding.selectedSmooch.setText(emoji);
                updateEmojiSelection();
            });
        }
        binding.selectedSmooch.setText(selected);
        updateEmojiSelection();
    }

    private void updateEmojiSelection() {
        for (int index = 0; index < emojiButtons.size(); index++) {
            MaterialButton button = emojiButtons.get(index);
            boolean chosen = EMOJIS.get(index).equals(selected);
            button.setChecked(chosen);
            button.setSelected(chosen);
            button.setStrokeWidth(dp(chosen ? 2 : 1));
            button.setStrokeColor(ColorStateList.valueOf(getColor(
                    chosen ? R.color.lavender : R.color.orbit_border)));
            button.setBackgroundTintList(ColorStateList.valueOf(getColor(
                    chosen ? R.color.navy_surface_high : R.color.navy_surface_muted)));
            ViewCompat.setStateDescription(button, getString(
                    chosen ? R.string.rc14_selected : R.string.rc14_not_selected));
        }
    }

    private void send() {
        String operationId = UUID.randomUUID().toString();
        binding.sendSmoochButton.setEnabled(false);
        orbit.sendSmooch(new SmoochApiModels.SendRequest(operationId, selected))
                .whenComplete((sent, failure) -> runOnUiThread(() -> {
                    if (isFinishing() || isDestroyed()) return;
                    binding.sendSmoochButton.setEnabled(true);
                    if (failure == null) {
                        partnerName = sent.partnerName;
                        binding.smoochStatus.setText(getString(
                                R.string.smooch_sent_warm, sent.partnerName));
                        showRemaining(sent.remaining);
                        animatePulse();
                        loadStatus();
                        loadHistory();
                    } else if (SafeRequestFailure.classify(failure)
                            == SafeRequestFailure.OFFLINE) {
                        outbox.enqueue(operationId, selected, System.currentTimeMillis());
                        SmoochSendWorker.enqueue(this);
                        binding.smoochStatus.setText(R.string.smooch_queued);
                    } else if (SafeRequestFailure.classify(failure)
                            == SafeRequestFailure.RATE_LIMITED) {
                        binding.smoochStatus.setText(R.string.smooch_rate_limited);
                    } else {
                        binding.smoochStatus.setText(R.string.request_failed);
                    }
                }));
    }

    private void animatePulse() {
        binding.orbitPulse.animate().cancel();
        if (!ValueAnimator.areAnimatorsEnabled()) {
            binding.orbitPulse.setScaleX(1f);
            binding.orbitPulse.setScaleY(1f);
            binding.orbitPulse.setAlpha(1f);
            return;
        }
        binding.orbitPulse.setScaleX(0.88f);
        binding.orbitPulse.setScaleY(0.88f);
        binding.orbitPulse.setAlpha(0.65f);
        binding.orbitPulse.animate()
                .scaleX(1f)
                .scaleY(1f)
                .alpha(1f)
                .setDuration(500)
                .start();
    }

    private void loadStatus() {
        orbit.smoochStatus().thenAccept(status -> runOnUiThread(() -> {
            if (!isFinishing() && !isDestroyed()) showStatus(status);
        }))
                .exceptionally(failure -> null);
    }

    private void showStatus(SmoochApiModels.Status status) {
        partnerName = status.partnerName;
        binding.partnerPlanet.setText(initial(partnerName));
        binding.partnerPlanet.setContentDescription(getString(
                R.string.rc14_partner_planet_description, partnerName));
        showRemaining(status.remaining);
        binding.sendSmoochButton.setEnabled(status.remaining > 0);
        showCurrentWeek(status.currentWeek);
    }

    private void showCurrentWeek(SmoochApiModels.Week week) {
        binding.weekSent.setText(getString(R.string.smooch_week_sent, week.sent));
        binding.weekReceived.setText(getString(
                R.string.smooch_week_received, partnerName, week.received));
        binding.weekTogether.setText(getString(R.string.smooch_week_together, week.combined));
        binding.weekEmojiDistribution.setText(distribution(week));
    }

    private void loadHistory() {
        orbit.smoochWeeks(12).thenAccept(weeks -> runOnUiThread(() -> {
            if (!isFinishing() && !isDestroyed()) showHistory(weeks);
        }))
                .exceptionally(failure -> null);
    }

    private void loadTimezone() {
        orbit.preferences().thenAccept(preferences -> runOnUiThread(() -> {
            if (isFinishing() || isDestroyed()) return;
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
                    if (isFinishing() || isDestroyed()) return;
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
        binding.weeklyHistory.removeAllViews();
        if (weeks.isEmpty()) {
            binding.weeklyHistory.addView(historyText(getString(R.string.smooch_no_history), 15));
            return;
        }
        int shown = 0;
        for (int index = weeks.size() - 1; index >= 0; index--) {
            SmoochApiModels.Week week = weeks.get(index);
            if (week.combined == 0 && index < weeks.size() - 2) continue;
            binding.weeklyHistory.addView(historyCard(week));
            shown++;
        }
        if (shown == 0) {
            binding.weeklyHistory.addView(historyText(getString(R.string.smooch_no_history), 15));
        }
    }

    private MaterialCardView historyCard(SmoochApiModels.Week week) {
        MaterialCardView card = new MaterialCardView(this);
        card.setCardBackgroundColor(getColor(R.color.navy_surface_muted));
        card.setStrokeColor(getColor(R.color.orbit_border));
        card.setStrokeWidth(1);
        card.setRadius(dp(20));
        LinearLayout content = new LinearLayout(this);
        content.setOrientation(LinearLayout.VERTICAL);
        content.setPadding(dp(16), dp(14), dp(16), dp(14));
        content.addView(historyText(week.weekStart + " – " + week.weekEnd, 17));
        content.addView(historyText(getString(
                R.string.smooch_week_row, week.weekStart,
                week.sent, week.received, week.combined), 14));
        if (!week.emojiCounts.isEmpty()) content.addView(historyText(distribution(week), 19));
        card.addView(content);
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        params.bottomMargin = dp(9);
        card.setLayoutParams(params);
        return card;
    }

    private TextView historyText(String value, int size) {
        TextView text = new TextView(this);
        text.setText(value);
        text.setTextSize(size);
        text.setTextColor(getColor(size >= 17 ? R.color.cloud : R.color.muted));
        text.setPadding(0, 0, 0, dp(5));
        return text;
    }

    private static String distribution(SmoochApiModels.Week week) {
        StringBuilder result = new StringBuilder();
        for (String emoji : EMOJIS) {
            Integer count = week.emojiCounts.get(emoji);
            if (count != null && count > 0) {
                if (result.length() > 0) result.append(" · ");
                result.append(emoji).append(" ").append(count);
            }
        }
        return result.toString();
    }

    private static String initial(String value) {
        return value == null || value.isBlank()
                ? "P" : value.substring(0, value.offsetByCodePoints(0, 1))
                        .toUpperCase(Locale.ROOT);
    }

    private void showRemaining(int remaining) {
        binding.remainingText.setText(getResources().getQuantityString(
                R.plurals.rc14_smooches_remaining, remaining, remaining));
    }

    @Override
    protected void onSaveInstanceState(Bundle outState) {
        super.onSaveInstanceState(outState);
        outState.putString(STATE_SELECTED, selected);
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

}
