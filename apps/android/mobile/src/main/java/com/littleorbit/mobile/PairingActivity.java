package com.littleorbit.mobile;

import android.os.Bundle;
import androidx.appcompat.app.AppCompatActivity;
import com.littleorbit.data.remote.ApiModels;
import com.littleorbit.data.repository.OrbitRepository;
import com.littleorbit.mobile.databinding.ActivityPairingBinding;
import dagger.hilt.android.AndroidEntryPoint;
import javax.inject.Inject;

/** Two-person pair-code creation, redemption, and creator confirmation. */
@AndroidEntryPoint
public final class PairingActivity extends InsetAwareActivity {
    @Inject OrbitRepository orbit;
    private ActivityPairingBinding binding;
    private String pendingRequestId;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        binding = ActivityPairingBinding.inflate(getLayoutInflater());
        setContentView(binding.getRoot());
        binding.createCodeButton.setOnClickListener(view -> createCode());
        binding.redeemButton.setOnClickListener(view -> redeem());
        binding.checkPendingButton.setOnClickListener(view -> checkPending());
        binding.confirmButton.setOnClickListener(view -> confirm());
    }

    private void createCode() {
        binding.statusText.setText(R.string.loading);
        AsyncUi.observe(this, orbit.createPairCode(), binding.statusText, result ->
                binding.statusText.setText(getString(R.string.pair_code_result, result.code)));
    }

    private void redeem() {
        String code = binding.codeInput.getText().toString().trim().toUpperCase();
        if (code.length() != 8) {
            binding.statusText.setText(R.string.pair_code_length);
            return;
        }
        AsyncUi.observe(this, orbit.redeemPairCode(code), binding.statusText, result ->
                binding.statusText.setText(R.string.waiting_for_partner));
    }

    private void checkPending() {
        AsyncUi.observe(this, orbit.pendingPairing(), binding.statusText, this::showPending);
    }

    private void showPending(ApiModels.PendingPairing result) {
        pendingRequestId = result.requestId;
        binding.statusText.setText(
                getString(R.string.confirm_partner_name, result.partnerDisplayName));
        binding.confirmButton.setEnabled(true);
    }

    private void confirm() {
        if (pendingRequestId == null) {
            binding.statusText.setText(R.string.check_pending_first);
            return;
        }
        AsyncUi.observe(
                this,
                orbit.confirmPairing(pendingRequestId),
                binding.statusText,
                result -> {
                    binding.statusText.setText(R.string.pairing_complete);
                    binding.confirmButton.setEnabled(false);
                });
    }
}
