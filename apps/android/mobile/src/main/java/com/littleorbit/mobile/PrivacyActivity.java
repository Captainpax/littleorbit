package com.littleorbit.mobile;

import android.Manifest;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.Bundle;
import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;
import androidx.appcompat.app.AlertDialog;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.content.ContextCompat;
import com.littleorbit.data.remote.ApiModels;
import com.littleorbit.data.repository.OrbitRepository;
import com.littleorbit.mobile.databinding.ActivityPrivacyBinding;
import dagger.hilt.android.AndroidEntryPoint;
import java.util.Map;
import javax.inject.Inject;
import org.json.JSONObject;

/** Revocable consent, export, unpair, and deletion controls. */
@AndroidEntryPoint
public final class PrivacyActivity extends AppCompatActivity {
    @Inject OrbitRepository orbit;
    private ActivityPrivacyBinding binding;
    private final ActivityResultLauncher<String[]> foregroundLocation =
            registerForActivityResult(
                    new ActivityResultContracts.RequestMultiplePermissions(),
                    result -> requestBackgroundOrSave());
    private final ActivityResultLauncher<String> backgroundLocation =
            registerForActivityResult(
                    new ActivityResultContracts.RequestPermission(),
                    granted -> {
                        if (granted) {
                            savePreferences();
                        } else {
                            binding.statusText.setText(R.string.background_location_needed);
                        }
                    });

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        binding = ActivityPrivacyBinding.inflate(getLayoutInflater());
        setContentView(binding.getRoot());
        binding.saveButton.setOnClickListener(view -> ensureLocationThenSave());
        binding.exportButton.setOnClickListener(view -> exportData());
        binding.unpairButton.setOnClickListener(view -> confirmUnpair());
        binding.deleteButton.setOnClickListener(view -> confirmDeletion());
        load();
    }

    private void load() {
        AsyncUi.observe(this, orbit.preferences(), binding.statusText, preferences -> {
            binding.intimacySwitch.setChecked(preferences.intimacyByMe);
            binding.locationSwitch.setChecked(preferences.locationByMe);
            binding.thresholdInput.setText(String.valueOf(preferences.thresholdM));
            binding.mutualState.setText(getString(
                    R.string.mutual_consent_state,
                    preferences.intimacyByBoth,
                    preferences.locationByBoth));
        });
    }

    private void ensureLocationThenSave() {
        if (!binding.locationSwitch.isChecked()) {
            savePreferences();
            return;
        }
        boolean fine = ContextCompat.checkSelfPermission(
                this, Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED;
        if (!fine) {
            foregroundLocation.launch(new String[] {
                    Manifest.permission.ACCESS_COARSE_LOCATION,
                    Manifest.permission.ACCESS_FINE_LOCATION
            });
            return;
        }
        requestBackgroundOrSave();
    }

    private void requestBackgroundOrSave() {
        boolean granted = ContextCompat.checkSelfPermission(
                this, Manifest.permission.ACCESS_BACKGROUND_LOCATION)
                == PackageManager.PERMISSION_GRANTED;
        if (binding.locationSwitch.isChecked() && !granted) {
            backgroundLocation.launch(Manifest.permission.ACCESS_BACKGROUND_LOCATION);
        } else {
            savePreferences();
        }
    }

    private void savePreferences() {
        Double threshold;
        try {
            threshold = Double.valueOf(binding.thresholdInput.getText().toString());
        } catch (NumberFormatException invalid) {
            binding.statusText.setText(R.string.invalid_threshold);
            return;
        }
        ApiModels.PreferencesMutation mutation = new ApiModels.PreferencesMutation(
                binding.intimacySwitch.isChecked(),
                binding.locationSwitch.isChecked(),
                threshold,
                null);
        AsyncUi.observe(this, orbit.updatePreferences(mutation), binding.statusText, result -> {
            binding.statusText.setText(R.string.preferences_saved);
            load();
        });
    }

    private void exportData() {
        AsyncUi.observe(this, orbit.exportAccount(), binding.statusText, this::shareExport);
    }

    private void shareExport(Map<String, Object> export) {
        Intent share = new Intent(Intent.ACTION_SEND)
                .setType("application/json")
                .putExtra(Intent.EXTRA_TEXT, new JSONObject(export).toString());
        startActivity(Intent.createChooser(share, getString(R.string.export_data)));
    }

    private void confirmUnpair() {
        new AlertDialog.Builder(this)
                .setTitle(R.string.unpair)
                .setMessage(R.string.unpair_explanation)
                .setNegativeButton(android.R.string.cancel, null)
                .setPositiveButton(R.string.unpair, (dialog, which) ->
                        AsyncUi.observe(this, orbit.unpair(), binding.statusText, result -> {
                            binding.statusText.setText(R.string.unpaired);
                            finish();
                        }))
                .show();
    }

    private void confirmDeletion() {
        String password = binding.passwordInput.getText().toString();
        if (password.isEmpty()) {
            binding.statusText.setText(R.string.password_required_deletion);
            return;
        }
        new AlertDialog.Builder(this)
                .setTitle(R.string.delete_account)
                .setMessage(R.string.delete_account_explanation)
                .setNegativeButton(android.R.string.cancel, null)
                .setPositiveButton(R.string.delete_account, (dialog, which) ->
                        AsyncUi.observe(this, orbit.deleteAccount(password), binding.statusText, result -> {
                            startActivity(new Intent(this, SignInActivity.class)
                                    .addFlags(Intent.FLAG_ACTIVITY_CLEAR_TASK | Intent.FLAG_ACTIVITY_NEW_TASK));
                        }))
                .show();
    }
}
