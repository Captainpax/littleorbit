package com.littleorbit.mobile;

import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import androidx.appcompat.app.AppCompatActivity;
import com.littleorbit.data.repository.OrbitRepository;
import com.littleorbit.mobile.databinding.ActivitySignInBinding;
import dagger.hilt.android.AndroidEntryPoint;
import javax.inject.Inject;

/** Verified-account sign-in and App Link destination. */
@AndroidEntryPoint
public final class SignInActivity extends AppCompatActivity {
    @Inject OrbitRepository orbit;
    private ActivitySignInBinding binding;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        binding = ActivitySignInBinding.inflate(getLayoutInflater());
        setContentView(binding.getRoot());
        binding.signInButton.setOnClickListener(view -> signIn());
        binding.signupButton.setOnClickListener(view -> startActivity(
                new Intent(Intent.ACTION_VIEW, Uri.parse("https://lil-orb.pax-kun.com/signup"))));
    }

    private void signIn() {
        String email = binding.emailInput.getText().toString().trim();
        String password = binding.passwordInput.getText().toString();
        if (email.isEmpty() || password.isEmpty()) {
            binding.statusText.setText(R.string.complete_required_fields);
            return;
        }
        binding.statusText.setText(R.string.signing_in);
        AsyncUi.observe(this, orbit.signIn(email, password), binding.statusText, session -> {
            setResult(RESULT_OK);
            finish();
        });
    }
}
