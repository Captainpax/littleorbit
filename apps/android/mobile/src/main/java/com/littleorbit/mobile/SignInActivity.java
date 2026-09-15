package com.littleorbit.mobile;

import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.util.Patterns;
import android.view.inputmethod.EditorInfo;
import com.littleorbit.data.repository.OrbitRepository;
import com.littleorbit.mobile.databinding.ActivitySignInBinding;
import dagger.hilt.android.AndroidEntryPoint;
import javax.inject.Inject;

/** Verified-account sign-in and App Link destination. */
@AndroidEntryPoint
public final class SignInActivity extends InsetAwareActivity {
    @Inject OrbitRepository orbit;
    private ActivitySignInBinding binding;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        binding = ActivitySignInBinding.inflate(getLayoutInflater());
        setContentView(binding.getRoot());
        binding.signInButton.setOnClickListener(view -> signIn());
        binding.passwordInput.setOnEditorActionListener((view, actionId, event) -> {
            if (actionId != EditorInfo.IME_ACTION_DONE) return false;
            signIn();
            return true;
        });
        binding.signupButton.setOnClickListener(view -> openWeb("/signup"));
        binding.forgotPasswordButton.setOnClickListener(view -> openWeb("/forgot-password"));
        binding.resendVerificationButton.setOnClickListener(view -> openWeb("/verify-email"));
    }

    private void signIn() {
        String email = binding.emailInput.getText().toString().trim();
        String password = binding.passwordInput.getText().toString();
        binding.emailLayout.setError(null);
        binding.passwordLayout.setError(null);
        if (email.isEmpty()) binding.emailLayout.setError(getString(R.string.rc14_email_required));
        if (!email.isEmpty() && !Patterns.EMAIL_ADDRESS.matcher(email).matches()) {
            binding.emailLayout.setError(getString(R.string.rc14_email_invalid));
        }
        if (password.isEmpty()) {
            binding.passwordLayout.setError(getString(R.string.rc14_password_required));
        }
        if (binding.emailLayout.getError() != null || password.isEmpty()) {
            binding.statusText.setText(R.string.complete_required_fields);
            return;
        }
        setBusy(true);
        binding.statusText.setText(R.string.signing_in);
        orbit.signIn(email, password).whenComplete((session, failure) -> runOnUiThread(() -> {
            if (isDestroyed()) return;
            setBusy(false);
            if (failure != null) {
                binding.statusText.setText(messageFor(SafeRequestFailure.classify(failure)));
                binding.statusText.announceForAccessibility(binding.statusText.getText());
                return;
            }
            setResult(RESULT_OK);
            finish();
        }));
    }

    private void setBusy(boolean busy) {
        binding.signInProgress.setVisibility(busy ? android.view.View.VISIBLE : android.view.View.GONE);
        binding.signInButton.setEnabled(!busy);
        binding.emailInput.setEnabled(!busy);
        binding.passwordInput.setEnabled(!busy);
    }

    private int messageFor(SafeRequestFailure failure) {
        return switch (failure) {
            case INVALID_CREDENTIALS -> R.string.rc14_sign_in_incorrect;
            case RATE_LIMITED -> R.string.rc14_rate_limited;
            case OFFLINE -> R.string.rc14_offline;
            case SERVICE_UNAVAILABLE -> R.string.rc14_service_unavailable;
            default -> R.string.request_failed;
        };
    }

    private void openWeb(String path) {
        startActivity(new Intent(
                Intent.ACTION_VIEW, Uri.parse("https://lil-orb.pax-kun.com" + path)));
    }
}
