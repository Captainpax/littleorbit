package com.littleorbit.mobile;

import android.Manifest;
import android.content.Intent;
import android.os.Build;
import android.os.Bundle;
import android.provider.Settings;
import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;
import androidx.appcompat.app.AlertDialog;
import com.littleorbit.data.remote.ApiModels;
import com.littleorbit.data.remote.NotificationApiModels;
import com.littleorbit.data.repository.OrbitRepository;
import com.littleorbit.mobile.databinding.ActivityDeviceSetupBinding;
import dagger.hilt.android.AndroidEntryPoint;
import javax.inject.Inject;

/** Skippable permission and self-hosted Wear setup with live status checks. */
@AndroidEntryPoint
public final class DeviceSetupActivity extends InsetAwareActivity {
    @Inject OrbitRepository orbit;
    @Inject WearStatusChecker wearStatus;
    @Inject NotificationDeviceStore notificationDevice;
    private ActivityDeviceSetupBinding binding;
    private boolean waitingForBackground;
    private final ActivityResultLauncher<String[]> foregroundLocation =
            registerForActivityResult(
                    new ActivityResultContracts.RequestMultiplePermissions(),
                    ignored -> continueLocationSetup());
    private final ActivityResultLauncher<String> backgroundLocation =
            registerForActivityResult(
                    new ActivityResultContracts.RequestPermission(),
                    ignored -> finishLocationSetup());
    private final ActivityResultLauncher<String> notifications =
            registerForActivityResult(
                    new ActivityResultContracts.RequestPermission(),
                    ignored -> reconcileNotifications());

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        binding = ActivityDeviceSetupBinding.inflate(getLayoutInflater());
        setContentView(binding.getRoot());
        binding.notificationButton.setOnClickListener(view -> requestNotifications());
        binding.saveNotificationPreferences.setOnClickListener(view -> saveNotificationChoices());
        binding.checkNotifications.setOnClickListener(view -> {
            PartnerNotificationWorker.enqueue(this);
            binding.notificationDiagnostics.setText(R.string.loading);
            binding.notificationDiagnostics.postDelayed(
                    () -> binding.notificationDiagnostics.setText(notificationDevice.diagnostics()),
                    1500);
        });
        binding.openNotificationSettings.setOnClickListener(view -> openNotificationSettings());
        binding.notificationMaster.setOnCheckedChangeListener(
                (button, checked) -> enableNotificationChoices(checked));
        binding.locationButton.setOnClickListener(view -> requestLocation());
        binding.wearButton.setOnClickListener(view -> openWearGuide());
        binding.doneButton.setOnClickListener(view -> finish());
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (waitingForBackground && PermissionChecks.backgroundLocationGranted(this)) {
            waitingForBackground = false;
            enableLocationConsent();
        }
        refreshStatus();
    }

    private void requestNotifications() {
        if (Build.VERSION.SDK_INT >= 33 && !PermissionChecks.notificationsGranted(this)) {
            notifications.launch(Manifest.permission.POST_NOTIFICATIONS);
        } else if (!PermissionChecks.notificationsGranted(this)) {
            openNotificationSettings();
        }
    }

    private void reconcileNotifications() {
        if (PermissionChecks.notificationsGranted(this)) {
            PartnerNotificationWorker.schedule(this, orbit.isSignedIn());
            PartnerNotificationWorker.enqueue(this);
        }
        refreshStatus();
    }

    private void requestLocation() {
        if (!PermissionChecks.fineLocationGranted(this)) {
            foregroundLocation.launch(new String[] {
                    Manifest.permission.ACCESS_COARSE_LOCATION,
                    Manifest.permission.ACCESS_FINE_LOCATION
            });
            return;
        }
        continueLocationSetup();
    }

    private void continueLocationSetup() {
        if (!PermissionChecks.fineLocationGranted(this)) {
            binding.locationStatus.setText(R.string.location_exact_needed);
            return;
        }
        if (PermissionChecks.backgroundLocationGranted(this)) {
            enableLocationConsent();
            return;
        }
        String label = Build.VERSION.SDK_INT >= 30
                ? getPackageManager().getBackgroundPermissionOptionLabel().toString()
                : getString(R.string.allow_all_time);
        new AlertDialog.Builder(this)
                .setTitle(R.string.background_location_title)
                .setMessage(getString(R.string.background_location_explanation, label))
                .setNegativeButton(R.string.later, null)
                .setPositiveButton(R.string.continue_label, (dialog, which) -> {
                    waitingForBackground = true;
                    backgroundLocation.launch(Manifest.permission.ACCESS_BACKGROUND_LOCATION);
                })
                .show();
    }

    private void finishLocationSetup() {
        waitingForBackground = false;
        if (PermissionChecks.backgroundLocationGranted(this)) {
            enableLocationConsent();
        } else {
            binding.locationStatus.setText(R.string.background_location_needed);
        }
    }

    private void enableLocationConsent() {
        binding.locationStatus.setText(R.string.loading);
        ApiModels.PreferencesMutation mutation =
                new ApiModels.PreferencesMutation(null, true, null);
        AsyncUi.observe(this, orbit.updatePreferences(mutation), binding.locationStatus, result -> {
            NearbyTrackingReconciler.apply(this, result);
            binding.locationStatus.setText(
                    result.locationByBoth
                            ? R.string.location_ready_both
                            : R.string.location_waiting_partner);
        });
    }

    private void refreshStatus() {
        binding.notificationStatus.setText(
                PermissionChecks.notificationsGranted(this)
                        ? R.string.notifications_ready
                        : R.string.notifications_off);
        boolean locationReady = PermissionChecks.fineLocationGranted(this)
                && PermissionChecks.backgroundLocationGranted(this);
        binding.locationStatus.setText(
                locationReady ? R.string.location_permission_ready : R.string.location_permission_off);
        if (orbit.isSignedIn() && locationReady) {
            orbit.preferences().thenAccept(preferences -> runOnUiThread(() ->
                    renderLocation(preferences))).exceptionally(failure -> null);
        }
        binding.notificationDiagnostics.setText(notificationDevice.diagnostics());
        if (orbit.isSignedIn()) loadNotificationChoices();
        wearStatus.check().thenAccept(state -> runOnUiThread(() -> renderWear(state)));
    }

    private void loadNotificationChoices() {
        orbit.notificationPreferences().thenAccept(preferences -> runOnUiThread(() -> {
            if (isFinishing()) return;
            renderNotificationChoices(preferences);
        })).exceptionally(failure -> null);
    }

    private void renderNotificationChoices(NotificationApiModels.Preferences preferences) {
        binding.notificationMaster.setChecked(preferences.master);
        binding.notificationSmooches.setChecked(preferences.smooches);
        binding.notificationNotes.setChecked(preferences.noteEditing);
        binding.notificationQuiz.setChecked(preferences.dailyQuiz);
        binding.notificationCountdowns.setChecked(preferences.countdowns);
        binding.notificationTogetherTime.setChecked(preferences.togetherTime);
        binding.notificationWeekly.setChecked(preferences.weeklySummary);
        enableNotificationChoices(preferences.master);
        new NotificationSettingsStore(this).save(preferences);
    }

    private void saveNotificationChoices() {
        NotificationApiModels.PreferencesUpdate update = new NotificationApiModels.PreferencesUpdate(
                binding.notificationMaster.isChecked(),
                binding.notificationSmooches.isChecked(),
                binding.notificationNotes.isChecked(),
                binding.notificationQuiz.isChecked(),
                binding.notificationCountdowns.isChecked(),
                binding.notificationTogetherTime.isChecked(),
                binding.notificationWeekly.isChecked());
        binding.notificationDiagnostics.setText(R.string.loading);
        AsyncUi.observe(this, orbit.updateNotificationPreferences(update),
                binding.notificationDiagnostics, preferences -> {
                    renderNotificationChoices(preferences);
                    binding.notificationDiagnostics.setText(R.string.notification_choices_saved);
                    PartnerNotificationWorker.schedule(this, preferences.master);
                    PartnerNotificationWorker.enqueue(this);
                });
    }

    private void enableNotificationChoices(boolean enabled) {
        binding.notificationSmooches.setEnabled(enabled);
        binding.notificationNotes.setEnabled(enabled);
        binding.notificationQuiz.setEnabled(enabled);
        binding.notificationCountdowns.setEnabled(enabled);
        binding.notificationTogetherTime.setEnabled(enabled);
        binding.notificationWeekly.setEnabled(enabled);
    }

    private void renderLocation(ApiModels.Preferences preferences) {
        if (isFinishing()) return;
        NearbyTrackingReconciler.apply(this, preferences);
        binding.locationStatus.setText(
                preferences.locationByBoth
                        ? R.string.location_ready_both
                        : preferences.locationByMe
                                ? R.string.location_waiting_partner
                                : R.string.location_server_off);
    }

    private void renderWear(WearStatusChecker.State state) {
        int text = switch (state) {
            case APP_CONNECTED -> R.string.wear_connected;
            case APP_MISSING -> R.string.wear_missing;
            case NO_WATCH -> R.string.wear_no_watch;
            case UNAVAILABLE -> R.string.wear_status_unavailable;
        };
        binding.wearStatus.setText(text);
        binding.wearButton.setEnabled(state != WearStatusChecker.State.APP_CONNECTED);
    }

    private void openWearGuide() {
        startActivity(new Intent(this, WearInstallerActivity.class));
    }

    private void openNotificationSettings() {
        Intent intent = new Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS)
                .putExtra(Settings.EXTRA_APP_PACKAGE, getPackageName());
        startActivity(intent);
    }
}
