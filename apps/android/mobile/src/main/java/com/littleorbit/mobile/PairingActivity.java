package com.littleorbit.mobile;

import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.Intent;
import android.os.Bundle;
import android.os.CountDownTimer;
import android.os.Handler;
import android.os.Looper;
import android.view.View;
import android.view.inputmethod.EditorInfo;
import com.google.android.material.dialog.MaterialAlertDialogBuilder;
import com.littleorbit.data.remote.ApiModels;
import com.littleorbit.data.repository.OrbitRepository;
import com.littleorbit.mobile.databinding.ActivityPairingBinding;
import dagger.hilt.android.AndroidEntryPoint;
import java.time.Instant;
import javax.inject.Inject;

/** Guided two-person pair-code creation, redemption, and creator confirmation. */
@AndroidEntryPoint
public final class PairingActivity extends InsetAwareActivity {
    private static final String STATE_CODE = "pair_code";
    private static final String STATE_EXPIRY = "pair_expiry";
    private static final String STATE_REQUEST = "pair_request";
    private static final String STATE_PARTNER = "pair_partner";
    private static final long POLL_INTERVAL_MS = 5_000L;

    @Inject OrbitRepository orbit;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private ActivityPairingBinding binding;
    private String currentCode;
    private Instant expiresAt;
    private String pendingRequestId;
    private String pendingPartnerName;
    private CountDownTimer expiryTimer;
    private boolean pendingCheckInFlight;
    private boolean mutationBusy;

    private final Runnable pendingPoll = () -> checkPending(false);

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        binding = ActivityPairingBinding.inflate(getLayoutInflater());
        setContentView(binding.getRoot());
        restore(savedInstanceState);
        bindActions();
        renderRestoredState();
        refreshRelationshipState();
    }

    private void bindActions() {
        binding.pairingBackButton.setOnClickListener(view -> finish());
        binding.createCodeButton.setOnClickListener(view -> createCode());
        binding.copyCodeButton.setOnClickListener(view -> copyCode());
        binding.shareCodeButton.setOnClickListener(view -> shareCode());
        binding.redeemButton.setOnClickListener(view -> redeem());
        binding.checkPendingButton.setOnClickListener(view -> checkPending(true));
        binding.confirmButton.setOnClickListener(view -> askToConfirm());
        binding.unpairButton.setOnClickListener(view -> askToUnpair());
        binding.returnHomeButton.setOnClickListener(view -> returnHome());
        binding.codeInput.setOnEditorActionListener((view, actionId, event) -> {
            if (actionId != EditorInfo.IME_ACTION_DONE) return false;
            redeem();
            return true;
        });
    }

    private void refreshRelationshipState() {
        binding.createPairingCard.setVisibility(View.GONE);
        binding.joinPairingCard.setVisibility(View.GONE);
        binding.activePairingCard.setVisibility(View.GONE);
        binding.pairingProgress.setVisibility(View.VISIBLE);
        orbit.preferences().whenComplete((preferences, failure) -> runOnUiThread(() -> {
            if (isFinishing() || isDestroyed()) return;
            binding.pairingProgress.setVisibility(View.GONE);
            if (failure == null) {
                showConnectedState();
            } else if (!orbit.isSignedIn()) {
                returnHome();
            } else if (SafeRequestFailure.relationshipInactive(failure)) {
                showPairingState();
            } else {
                showFailure(failure);
                binding.returnHomeButton.setVisibility(View.VISIBLE);
            }
        }));
    }

    private void showConnectedState() {
        stopTimers();
        binding.createPairingCard.setVisibility(View.GONE);
        binding.joinPairingCard.setVisibility(View.GONE);
        binding.confirmationCard.setVisibility(View.GONE);
        binding.activePairingCard.setVisibility(View.VISIBLE);
        binding.statusText.setText("");
    }

    private void showPairingState() {
        binding.activePairingCard.setVisibility(View.GONE);
        binding.createPairingCard.setVisibility(View.VISIBLE);
        binding.joinPairingCard.setVisibility(View.VISIBLE);
        checkPending(false);
    }

    private void askToUnpair() {
        if (mutationBusy) return;
        new MaterialAlertDialogBuilder(this)
                .setTitle(R.string.unpair_from_partner)
                .setMessage(R.string.unpair_explanation)
                .setNegativeButton(R.string.cancel, null)
                .setPositiveButton(R.string.unpair, (dialog, which) -> unpair())
                .show();
    }

    private void unpair() {
        setMutationBusy(true);
        binding.unpairButton.setEnabled(false);
        binding.statusText.setText(R.string.unpairing);
        orbit.unpair().whenComplete((result, failure) -> runOnUiThread(() -> {
            if (isFinishing() || isDestroyed()) return;
            setMutationBusy(false);
            binding.unpairButton.setEnabled(true);
            if (failure != null) {
                showFailure(failure);
                return;
            }
            binding.statusText.setText(R.string.unpaired);
            returnHome();
        }));
    }

    private void createCode() {
        if (mutationBusy) return;
        setMutationBusy(true);
        binding.statusText.setText(R.string.loading);
        orbit.createPairCode().whenComplete((result, failure) -> runOnUiThread(() -> {
            if (isFinishing() || isDestroyed()) return;
            setMutationBusy(false);
            if (failure != null) {
                showFailure(failure);
                return;
            }
            currentCode = result.code;
            expiresAt = parseInstant(result.expiresAt);
            pendingRequestId = null;
            pendingPartnerName = null;
            binding.confirmationCard.setVisibility(View.GONE);
            binding.pairCodeValue.setText(currentCode);
            binding.pairCodeValue.setContentDescription(
                    getString(R.string.rc14_pair_code_accessibility, spacedCode(currentCode)));
            binding.copyCodeButton.setEnabled(true);
            binding.shareCodeButton.setEnabled(true);
            binding.pendingStatus.setText(R.string.rc14_pair_pending_none);
            binding.statusText.setText("");
            startExpiryTimer();
            schedulePendingPoll(0);
        }));
    }

    private void redeem() {
        if (mutationBusy) return;
        String code = PairingPresentation.normalizeCode(
                String.valueOf(binding.codeInput.getText()));
        binding.codeInput.setText(code);
        binding.codeLayout.setError(null);
        if (code.length() != 8) {
            binding.codeLayout.setError(getString(R.string.pair_code_length));
            return;
        }
        setMutationBusy(true);
        binding.statusText.setText(R.string.loading);
        orbit.redeemPairCode(code).whenComplete((result, failure) -> runOnUiThread(() -> {
            if (isFinishing() || isDestroyed()) return;
            setMutationBusy(false);
            if (failure != null) {
                showFailure(failure);
                return;
            }
            binding.statusText.setText(R.string.waiting_for_partner);
            binding.codeInput.setEnabled(false);
            binding.redeemButton.setEnabled(false);
            binding.returnHomeButton.setVisibility(View.VISIBLE);
        }));
    }

    private void checkPending(boolean announce) {
        if (pendingCheckInFlight || isFinishing()) return;
        pendingCheckInFlight = true;
        if (announce) binding.pendingStatus.setText(R.string.loading);
        orbit.pendingPairing().whenComplete((result, failure) -> runOnUiThread(() -> {
            pendingCheckInFlight = false;
            if (isFinishing() || isDestroyed()) return;
            if (failure == null) {
                showPending(result);
                return;
            }
            if (SafeRequestFailure.classify(failure) == SafeRequestFailure.INVALID_OR_EXPIRED) {
                if (announce) binding.pendingStatus.setText(R.string.rc14_pair_pending_none);
                schedulePendingPoll(POLL_INTERVAL_MS);
                return;
            }
            if (announce) showFailure(failure);
            schedulePendingPoll(POLL_INTERVAL_MS);
        }));
    }

    private void showPending(ApiModels.PendingPairing result) {
        handler.removeCallbacks(pendingPoll);
        pendingRequestId = result.requestId;
        pendingPartnerName = result.partnerDisplayName;
        expiresAt = parseInstant(result.expiresAt);
        binding.partnerName.setText(result.partnerDisplayName);
        binding.confirmButton.setText(getString(
                R.string.rc14_pair_confirm_action, result.partnerDisplayName));
        binding.confirmButton.setEnabled(true);
        binding.confirmationCard.setVisibility(View.VISIBLE);
        binding.pendingStatus.setText(getString(
                R.string.confirm_partner_name, result.partnerDisplayName));
        binding.confirmationCard.announceForAccessibility(
                getString(R.string.rc14_pair_confirm_question, result.partnerDisplayName));
        startExpiryTimer();
    }

    private void askToConfirm() {
        if (pendingRequestId == null || pendingPartnerName == null || mutationBusy) {
            binding.statusText.setText(R.string.check_pending_first);
            return;
        }
        new MaterialAlertDialogBuilder(this)
                .setTitle(getString(R.string.rc14_pair_confirm_question, pendingPartnerName))
                .setMessage(R.string.rc14_pair_confirm_detail)
                .setNegativeButton(R.string.cancel, null)
                .setPositiveButton(
                        getString(R.string.rc14_pair_confirm_action, pendingPartnerName),
                        (dialog, which) -> confirm())
                .show();
    }

    private void confirm() {
        String requestId = pendingRequestId;
        if (requestId == null) return;
        setMutationBusy(true);
        binding.statusText.setText(R.string.loading);
        orbit.confirmPairing(requestId).whenComplete((result, failure) -> runOnUiThread(() -> {
            if (isFinishing() || isDestroyed()) return;
            setMutationBusy(false);
            if (failure != null) {
                showFailure(failure);
                return;
            }
            stopTimers();
            binding.statusText.setText(R.string.rc14_pair_complete);
            binding.confirmButton.setEnabled(false);
            binding.createCodeButton.setEnabled(false);
            binding.returnHomeButton.setVisibility(View.VISIBLE);
        }));
    }

    private void copyCode() {
        if (currentCode == null) return;
        ClipboardManager clipboard = (ClipboardManager) getSystemService(Context.CLIPBOARD_SERVICE);
        clipboard.setPrimaryClip(ClipData.newPlainText(
                getString(R.string.rc14_pair_clipboard_label), currentCode));
        binding.statusText.setText(R.string.rc14_pair_code_copied);
    }

    private void shareCode() {
        if (currentCode == null) return;
        Intent share = new Intent(Intent.ACTION_SEND)
                .setType("text/plain")
                .putExtra(Intent.EXTRA_TEXT, getString(R.string.rc14_pair_share_text, currentCode));
        startActivity(Intent.createChooser(share, getString(R.string.rc14_share_code)));
    }

    private void startExpiryTimer() {
        if (expiryTimer != null) expiryTimer.cancel();
        if (expiresAt == null) {
            renderExpiry(0);
            return;
        }
        long seconds = PairingPresentation.secondsRemaining(expiresAt, Instant.now());
        renderExpiry(seconds);
        if (seconds == 0) return;
        expiryTimer = new CountDownTimer(seconds * 1_000L, 1_000L) {
            @Override public void onTick(long millisUntilFinished) {
                renderExpiry((millisUntilFinished + 999) / 1_000);
            }

            @Override public void onFinish() {
                renderExpiry(0);
                binding.pairCodeExpiry.announceForAccessibility(
                        getString(R.string.rc14_pair_expired));
            }
        }.start();
    }

    private void renderExpiry(long seconds) {
        boolean active = seconds > 0;
        binding.pairCodeExpiry.setText(active
                ? getString(R.string.rc14_pair_expires, PairingPresentation.clock(seconds))
                : getString(R.string.rc14_pair_expired));
        binding.copyCodeButton.setEnabled(active && currentCode != null);
        binding.shareCodeButton.setEnabled(active && currentCode != null);
        if (active) return;
        handler.removeCallbacks(pendingPoll);
        binding.confirmButton.setEnabled(false);
    }

    private void schedulePendingPoll(long delayMillis) {
        handler.removeCallbacks(pendingPoll);
        if (expiresAt == null
                || PairingPresentation.secondsRemaining(expiresAt, Instant.now()) == 0
                || pendingRequestId != null) return;
        handler.postDelayed(pendingPoll, delayMillis);
    }

    private void showFailure(Throwable failure) {
        int message = switch (SafeRequestFailure.classify(failure)) {
            case INVALID_OR_EXPIRED -> R.string.rc14_pair_invalid;
            case CONFLICT -> R.string.rc14_pair_conflict;
            case RATE_LIMITED -> R.string.rc14_rate_limited;
            case OFFLINE -> R.string.rc14_offline;
            case SERVICE_UNAVAILABLE -> R.string.rc14_service_unavailable;
            default -> R.string.request_failed;
        };
        binding.statusText.setText(message);
        binding.statusText.announceForAccessibility(binding.statusText.getText());
    }

    private void setMutationBusy(boolean busy) {
        mutationBusy = busy;
        binding.pairingProgress.setVisibility(busy ? View.VISIBLE : View.GONE);
        binding.createCodeButton.setEnabled(!busy);
        binding.redeemButton.setEnabled(!busy && binding.codeInput.isEnabled());
        binding.confirmButton.setEnabled(!busy && pendingRequestId != null && expiryIsActive());
    }

    private boolean expiryIsActive() {
        return expiresAt != null
                && PairingPresentation.secondsRemaining(expiresAt, Instant.now()) > 0;
    }

    private void restore(Bundle state) {
        if (state == null) return;
        currentCode = state.getString(STATE_CODE);
        expiresAt = parseInstant(state.getString(STATE_EXPIRY));
        pendingRequestId = state.getString(STATE_REQUEST);
        pendingPartnerName = state.getString(STATE_PARTNER);
    }

    private void renderRestoredState() {
        if (currentCode != null) {
            binding.pairCodeValue.setText(currentCode);
            binding.pairCodeValue.setContentDescription(
                    getString(R.string.rc14_pair_code_accessibility, spacedCode(currentCode)));
            startExpiryTimer();
            schedulePendingPoll(0);
        }
        if (pendingRequestId != null && pendingPartnerName != null) {
            showPending(new ApiModels.PendingPairing(
                    pendingRequestId,
                    pendingPartnerName,
                    expiresAt == null ? Instant.now().toString() : expiresAt.toString()));
        }
    }

    @Override
    protected void onSaveInstanceState(Bundle outState) {
        super.onSaveInstanceState(outState);
        outState.putString(STATE_CODE, currentCode);
        outState.putString(STATE_EXPIRY, expiresAt == null ? null : expiresAt.toString());
        outState.putString(STATE_REQUEST, pendingRequestId);
        outState.putString(STATE_PARTNER, pendingPartnerName);
    }

    @Override
    protected void onDestroy() {
        stopTimers();
        super.onDestroy();
    }

    private void stopTimers() {
        handler.removeCallbacks(pendingPoll);
        if (expiryTimer != null) expiryTimer.cancel();
    }

    private void returnHome() {
        startActivity(new Intent(this, MainActivity.class)
                .addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_SINGLE_TOP));
        finish();
    }

    private static Instant parseInstant(String value) {
        if (value == null) return null;
        try {
            return Instant.parse(value);
        } catch (RuntimeException invalid) {
            return null;
        }
    }

    private static String spacedCode(String code) {
        return String.join(" ", code.split(""));
    }
}
