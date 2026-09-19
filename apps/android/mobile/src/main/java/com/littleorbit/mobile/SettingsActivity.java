package com.littleorbit.mobile;

import android.content.Intent;
import android.os.Bundle;
import android.view.View;
import android.widget.Toast;
import androidx.appcompat.app.AppCompatActivity;
import com.littleorbit.data.repository.OrbitRepository;
import com.littleorbit.mobile.databinding.ActivitySettingsBinding;
import dagger.hilt.android.AndroidEntryPoint;
import javax.inject.Inject;

/** Dedicated account, device, privacy, and watch settings destination. */
@AndroidEntryPoint
public final class SettingsActivity extends OrbitShellActivity {
    @Inject OrbitRepository orbit;
    @Inject WearStatusChecker wearStatus;
    @Inject NotificationDeviceStore notificationDevice;
    @Inject CrashDiagnosticStore crashDiagnostics;
    private ActivitySettingsBinding binding;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        binding = ActivitySettingsBinding.inflate(getLayoutInflater());
        setContentView(binding.getRoot());
        bindActions();
    }

    @Override
    protected void onResume() {
        super.onResume();
        renderAccess();
        if (orbit.isSignedIn()) refreshSetupStatus();
    }

    @Override
    protected OrbitDestination orbitDestination() {
        return OrbitDestination.SETTINGS;
    }

    private void bindActions() {
        binding.signedOutSignIn.setOnClickListener(ignored -> open(SignInActivity.class));
        binding.profilePhotoButton.setOnClickListener(ignored -> open(ProfilePhotoActivity.class));
        binding.pairingButton.setOnClickListener(ignored -> open(PairingActivity.class));
        binding.countdownsButton.setOnClickListener(ignored -> open(CountdownActivity.class));
        binding.smoochButton.setOnClickListener(ignored -> open(SmoochActivity.class));
        binding.togetherButton.setOnClickListener(ignored -> open(TogetherTimeActivity.class));
        binding.privacyButton.setOnClickListener(ignored -> open(PrivacyActivity.class));
        binding.archivesButton.setOnClickListener(ignored -> open(ArchivesActivity.class));
        binding.appUpdatesButton.setOnClickListener(ignored -> open(AppUpdatesActivity.class));
        binding.notificationSetupButton.setOnClickListener(
                ignored -> open(DeviceSetupActivity.class));
        binding.locationSetupButton.setOnClickListener(ignored -> open(DeviceSetupActivity.class));
        binding.pauseNearbyButton.setOnClickListener(ignored -> pauseNearbyTracking());
        binding.wearInstallButton.setOnClickListener(ignored -> open(WatchSettingsActivity.class));
        binding.signOutButton.setOnClickListener(ignored -> signOut());
        binding.crashDiagnosticsSwitch.setChecked(crashDiagnostics.enabled());
        binding.crashDiagnosticsSwitch.setOnCheckedChangeListener((button, enabled) -> {
            crashDiagnostics.setEnabled(enabled);
            if (enabled && orbit.isSignedIn()) CrashDiagnosticWorker.enqueue(this);
        });
    }

    private void renderAccess() {
        boolean signedIn = orbit.isSignedIn();
        binding.memberSettings.setVisibility(signedIn ? View.VISIBLE : View.GONE);
        binding.signedOutSettings.setVisibility(signedIn ? View.GONE : View.VISIBLE);
    }

    private void refreshSetupStatus() {
        binding.notificationStatus.setText(
                PermissionChecks.notificationsGranted(this)
                        ? R.string.notifications_ready
                        : R.string.notifications_off);
        boolean locationReady = PermissionChecks.fineLocationGranted(this)
                && PermissionChecks.backgroundLocationGranted(this);
        binding.locationStatus.setText(
                locationReady ? R.string.location_permission_ready : R.string.location_permission_off);
        if (locationReady) {
            orbit.preferences().thenAccept(preferences -> runOnUiThread(() ->
                    reconcileLocation(preferences))).exceptionally(failure -> null);
        }
        wearStatus.check().thenAccept(state -> runOnUiThread(() -> renderWearStatus(state)));
    }

    private void reconcileLocation(com.littleorbit.data.remote.ApiModels.Preferences preferences) {
        if (isFinishing()) return;
        binding.locationStatus.setText(
                preferences.locationByBoth
                        ? R.string.location_ready_both
                        : preferences.locationByMe
                                ? R.string.location_waiting_partner
                                : R.string.location_server_off);
        binding.pauseNearbyButton.setVisibility(
                preferences.locationByMe ? View.VISIBLE : View.GONE);
        NearbyTrackingReconciler.apply(this, preferences);
    }

    private void pauseNearbyTracking() {
        binding.pauseNearbyButton.setEnabled(false);
        orbit.updatePreferences(new com.littleorbit.data.remote.ApiModels.PreferencesMutation(
                        null, false, null))
                .whenComplete((value, failure) -> runOnUiThread(() -> {
                    binding.pauseNearbyButton.setEnabled(true);
                    if (failure == null) {
                        ForegroundLocationService.stop(this);
                        com.littleorbit.data.LocationCollectionWorker.schedule(this, false);
                        reconcileLocation(value);
                    } else {
                        Toast.makeText(this, R.string.request_failed, Toast.LENGTH_LONG).show();
                    }
                }));
    }

    private void renderWearStatus(WearStatusChecker.State state) {
        if (isFinishing()) return;
        int text = switch (state) {
            case APP_CONNECTED -> R.string.wear_connected;
            case APP_MISSING -> R.string.wear_missing;
            case NO_WATCH -> R.string.wear_no_watch;
            case UNAVAILABLE -> R.string.wear_status_unavailable;
        };
        binding.wearStatus.setText(text);
        binding.wearInstallButton.setEnabled(true);
    }

    private void signOut() {
        binding.signOutButton.setEnabled(false);
        orbit.deleteTogetherDeviceHealth(notificationDevice.id())
                .handle((ignored, failure) -> null)
                .thenCompose(ignored -> orbit.disableNotificationDevice(notificationDevice.id()))
                .handle((ignored, failure) -> null)
                .thenCompose(ignored -> orbit.signOut())
                .thenRun(() -> runOnUiThread(this::finishSignedOut));
    }

    private void finishSignedOut() {
        PartnerNotificationWorker.schedule(this, false);
        CrashDiagnosticWorker.cancel(this);
        crashDiagnostics.clearForAccountChange();
        ForegroundLocationService.stop(this);
        Intent home = new Intent(this, MainActivity.class)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TASK);
        startActivity(home);
        finish();
    }

    private void open(Class<? extends AppCompatActivity> activity) {
        startActivity(new Intent(this, activity));
    }
}
