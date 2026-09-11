package com.littleorbit.mobile;

import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.view.View;
import androidx.appcompat.app.AppCompatActivity;
import androidx.lifecycle.ViewModelProvider;
import com.littleorbit.data.repository.OrbitRepository;
import com.littleorbit.mobile.databinding.ActivityMainBinding;
import dagger.hilt.android.AndroidEntryPoint;
import javax.inject.Inject;

/** Phone entry point that renders state and forwards actions to platform boundaries. */
@AndroidEntryPoint
public final class MainActivity extends AppCompatActivity {
    private ActivityMainBinding binding;
    private HomeViewModel model;
    @Inject OrbitRepository orbit;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        binding = ActivityMainBinding.inflate(getLayoutInflater());
        setContentView(binding.getRoot());
        model = new ViewModelProvider(this).get(HomeViewModel.class);
        model.state().observe(this, this::render);
        binding.createAccountButton.setOnClickListener(view -> openSignup());
        binding.signInButton.setOnClickListener(view -> open(SignInActivity.class));
        binding.pairingButton.setOnClickListener(view -> open(PairingActivity.class));
        binding.quizButton.setOnClickListener(view -> open(QuizActivity.class));
        binding.countdownsButton.setOnClickListener(view -> open(CountdownActivity.class));
        binding.notesButton.setOnClickListener(view -> open(NotesActivity.class));
        binding.privacyButton.setOnClickListener(view -> open(PrivacyActivity.class));
        binding.archivesButton.setOnClickListener(view -> open(ArchivesActivity.class));
        binding.togetherButton.setOnClickListener(view -> open(TogetherTimeActivity.class));
        binding.signOutButton.setOnClickListener(
                view -> orbit.signOut().thenRun(() -> runOnUiThread(this::finish)));
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (model != null) {
            model.refresh();
        }
    }

    private void render(HomeScreenState state) {
        binding.greetingText.setText(state.greeting());
        binding.togetherText.setText(state.togetherTime());
        binding.countdownText.setText(state.countdown());
        binding.statusText.setText(state.freshness());
        int memberVisibility = state.signedIn() ? View.VISIBLE : View.GONE;
        binding.quizButton.setVisibility(memberVisibility);
        binding.pairingButton.setVisibility(memberVisibility);
        binding.countdownsButton.setVisibility(memberVisibility);
        binding.notesButton.setVisibility(memberVisibility);
        binding.privacyButton.setVisibility(memberVisibility);
        binding.archivesButton.setVisibility(memberVisibility);
        binding.togetherButton.setVisibility(memberVisibility);
        binding.signOutButton.setVisibility(memberVisibility);
        int guestVisibility = state.signedIn() ? View.GONE : View.VISIBLE;
        binding.signInButton.setVisibility(guestVisibility);
        binding.createAccountButton.setVisibility(guestVisibility);
    }

    private void openSignup() {
        startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse("https://lil-orb.pax-kun.com/signup")));
    }

    private void open(Class<? extends AppCompatActivity> activity) {
        startActivity(new Intent(this, activity));
    }
}
