package com.littleorbit.mobile;

import android.content.Intent;
import android.graphics.BitmapFactory;
import android.net.Uri;
import android.os.Bundle;
import android.provider.Settings;
import android.view.View;
import android.widget.Toast;
import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;
import androidx.appcompat.app.AppCompatActivity;
import androidx.appcompat.app.AlertDialog;
import androidx.lifecycle.ViewModelProvider;
import com.google.android.material.bottomsheet.BottomSheetDialog;
import com.littleorbit.data.repository.OrbitRepository;
import com.littleorbit.data.repository.ProfileRepository;
import com.littleorbit.domain.UpdatePolicy;
import com.littleorbit.domain.UpdaterStateMachine;
import com.littleorbit.mobile.databinding.ActivityMainBinding;
import com.littleorbit.mobile.databinding.DialogUpdateBinding;
import dagger.hilt.android.AndroidEntryPoint;
import javax.inject.Inject;
import java.time.Instant;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;

/** Cosmic phone shell that renders home, More, and the persistent verified updater. */
@AndroidEntryPoint
public final class MainActivity extends OrbitShellActivity
        implements AndroidUpdateCoordinator.Listener {
    /** Intent flag used by focused tabs to open the More destination. */
    public static final String EXTRA_SHOW_MORE = "show_more";
    private ActivityMainBinding binding;
    private HomeViewModel model;
    private BottomSheetDialog updateSheet;
    private DialogUpdateBinding updateBinding;
    private UpdatePresentation activeUpdate;
    private boolean manualUpdateCheck;
    private boolean setupLookupStarted;
    private boolean notificationRequestedUpdate;
    private HomeActivityPanel activityPanel;
    @Inject OrbitRepository orbit;
    @Inject ProfileRepository profiles;
    @Inject AndroidUpdateCoordinator updates;
    @Inject WearStatusChecker wearStatus;
    @Inject NotificationDeviceStore notificationDevice;

    private final ActivityResultLauncher<Intent> installPermission = registerForActivityResult(
            new ActivityResultContracts.StartActivityForResult(),
            ignored -> updates.resumeInstallAfterPermission());

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        binding = ActivityMainBinding.inflate(getLayoutInflater());
        setContentView(binding.getRoot());
        model = new ViewModelProvider(this).get(HomeViewModel.class);
        activityPanel = new HomeActivityPanel(
                this, orbit, this::setOrbitContextActions, this::open);
        model.state().observe(this, this::renderHome);
        bindFeatureActions();
        if (getIntent().getBooleanExtra(EXTRA_SHOW_MORE, false)) showMore();
        else showHome();
        if (getIntent().getBooleanExtra(EXTRA_SHOW_MORE, false)) {
            setOrbitContextActions(java.util.List.of(
                    new ContextAction(getString(R.string.profile_photo),
                            () -> open(ProfilePhotoActivity.class)),
                    new ContextAction(getString(R.string.location_setup),
                            () -> open(DeviceSetupActivity.class)),
                    new ContextAction(getString(R.string.install_watch_app),
                            () -> open(WearInstallerActivity.class)),
                    new ContextAction(getString(R.string.pairing),
                            () -> open(PairingActivity.class)),
                    new ContextAction(getString(R.string.past_archives),
                            () -> open(ArchivesActivity.class))));
        }
        bindUpdateActions();
        notificationRequestedUpdate = getIntent().getBooleanExtra("show_update", false);
        configureAutomaticUpdates();
        binding.versionText.setText(getString(
                R.string.update_version, BuildConfig.VERSION_NAME));
    }

    @Override
    protected void onResume() {
        super.onResume();
        reconcileQuizNotifications();
        refreshSetupStatus();
        model.refresh();
        if (orbit.isSignedIn()) {
            refreshProfile();
            activityPanel.refresh();
        }
        updates.check(false, this);
    }

    @Override
    protected void onPause() {
        updates.stopObserving(this);
        super.onPause();
    }

    private void bindFeatureActions() {
        binding.createAccountButton.setOnClickListener(view -> openWeb("/signup"));
        binding.signInButton.setOnClickListener(view -> open(SignInActivity.class));
        binding.pairingButton.setOnClickListener(view -> open(PairingActivity.class));
        binding.morePairingButton.setOnClickListener(view -> open(PairingActivity.class));
        binding.quizButton.setOnClickListener(view -> open(QuizActivity.class));
        binding.countdownsButton.setOnClickListener(view -> open(CountdownActivity.class));
        binding.moreCountdownsButton.setOnClickListener(view -> open(CountdownActivity.class));
        binding.moreSmoochButton.setOnClickListener(view -> open(SmoochActivity.class));
        binding.smoochSpark.setOnClickListener(view -> open(SmoochActivity.class));
        binding.notesButton.setOnClickListener(view -> open(NotesActivity.class));
        binding.privacyButton.setOnClickListener(view -> open(PrivacyActivity.class));
        binding.archivesButton.setOnClickListener(view -> open(ArchivesActivity.class));
        binding.togetherButton.setOnClickListener(view -> open(TogetherTimeActivity.class));
        binding.moreTogetherButton.setOnClickListener(view -> open(TogetherTimeActivity.class));
        binding.notificationSetupButton.setOnClickListener(view -> open(DeviceSetupActivity.class));
        binding.locationSetupButton.setOnClickListener(view -> open(DeviceSetupActivity.class));
        binding.pauseNearbyButton.setOnClickListener(view -> pauseNearbyTracking());
        binding.wearInstallButton.setOnClickListener(view -> open(WearInstallerActivity.class));
        binding.profilePhotoButton.setOnClickListener(view -> open(ProfilePhotoActivity.class));
        binding.myPlanet.setOnClickListener(view -> {
            if (orbit.isSignedIn()) open(ProfilePhotoActivity.class);
            else open(SignInActivity.class);
        });
        binding.signOutButton.setOnClickListener(
                view -> orbit.disableNotificationDevice(notificationDevice.id())
                        .handle((ignored, failure) -> null)
                        .thenCompose(ignored -> orbit.signOut())
                        .thenRun(() -> runOnUiThread(() -> {
                    PartnerNotificationWorker.schedule(this, false);
                    ForegroundLocationService.stop(this);
                    finish();
                })));
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        if (intent.getBooleanExtra(EXTRA_SHOW_MORE, false)) showMore();
        else showHome();
    }

    private void bindUpdateActions() {
        binding.updateBanner.setOnClickListener(view -> showUpdateSheet());
        binding.appUpdatesButton.setOnClickListener(view -> {
            manualUpdateCheck = true;
            updates.check(true, this);
            Toast.makeText(this, R.string.loading, Toast.LENGTH_SHORT).show();
        });
        binding.autoUpdateDetection.setOnCheckedChangeListener((button, checked) -> {
            if (button.isPressed()) updates.setAutoDetectionEnabled(checked);
        });
    }

    private void configureAutomaticUpdates() {
        binding.autoUpdateDetection.setChecked(updates.autoDetectionEnabled());
        renderLastUpdateCheck();
        if (updates.hasAutoDetectionChoice()) return;
        new AlertDialog.Builder(this)
                .setTitle(R.string.auto_update_prompt_title)
                .setMessage(R.string.auto_update_prompt_message)
                .setNegativeButton(R.string.not_now, (dialog, which) -> {
                    updates.setAutoDetectionEnabled(false);
                    binding.autoUpdateDetection.setChecked(false);
                })
                .setPositiveButton(R.string.enable_auto_updates, (dialog, which) -> {
                    updates.setAutoDetectionEnabled(true);
                    binding.autoUpdateDetection.setChecked(true);
                    updates.check(true, this);
                })
                .show();
    }

    private void renderLastUpdateCheck() {
        long checked = updates.lastCheckedAtMillis();
        String value = checked <= 0 ? getString(R.string.never)
                : DateTimeFormatter.ofPattern("MMM d · h:mm a")
                        .withZone(ZoneId.systemDefault())
                        .format(Instant.ofEpochMilli(checked));
        binding.lastUpdateCheck.setText(getString(R.string.last_update_check, value));
    }

    private void renderHome(HomeScreenState state) {
        binding.greetingText.setText(state.greeting());
        binding.togetherText.setText(state.togetherTime());
        binding.nearbyText.setText(state.nearbyTime());
        binding.countdownText.setText(state.countdown());
        binding.quizPromptText.setText(state.quizPrompt());
        binding.statusText.setText(state.freshness());
        binding.partnerPlanet.setText(state.connected() ? "P" : "?");
        binding.sharedContent.setVisibility(state.connected() ? View.VISIBLE : View.GONE);
        binding.memberActions.setVisibility(
                state.signedIn() && !state.connected() ? View.VISIBLE : View.GONE);
        binding.guestActions.setVisibility(state.signedIn() ? View.GONE : View.VISIBLE);
        binding.signOutButton.setVisibility(state.signedIn() ? View.VISIBLE : View.GONE);
        binding.morePairingButton.setVisibility(state.signedIn() ? View.VISIBLE : View.GONE);
        binding.profilePhotoButton.setVisibility(state.signedIn() ? View.VISIBLE : View.GONE);
        binding.moreCountdownsButton.setVisibility(state.connected() ? View.VISIBLE : View.GONE);
        binding.moreSmoochButton.setVisibility(state.connected() ? View.VISIBLE : View.GONE);
        binding.smoochSpark.setVisibility(state.connected() ? View.VISIBLE : View.GONE);
        binding.moreTogetherButton.setVisibility(state.connected() ? View.VISIBLE : View.GONE);
        binding.privacyButton.setVisibility(state.signedIn() ? View.VISIBLE : View.GONE);
        binding.archivesButton.setVisibility(state.signedIn() ? View.VISIBLE : View.GONE);
        binding.locationStatus.setVisibility(state.signedIn() ? View.VISIBLE : View.GONE);
        binding.locationSetupButton.setVisibility(state.signedIn() ? View.VISIBLE : View.GONE);
        binding.myPlanet.setContentDescription(getString(
                state.signedIn() ? R.string.edit_profile_photo : R.string.sign_in));
        maybeOfferSetup(state);
        if (state.signedIn()) renderProfile(profiles.cached());
        else renderProfile(new ProfileRepository.State("You", null, null, null));
    }

    private void refreshProfile() {
        renderProfile(profiles.cached());
        profiles.refresh().thenAccept(value -> runOnUiThread(() -> {
            if (!isFinishing()) renderProfile(value);
        })).exceptionally(failure -> null);
    }

    private void renderProfile(ProfileRepository.State profile) {
        renderPlanet(
                binding.myPlanetImage, binding.myPlanetInitial,
                profile.myName(), profile.myPhoto(), "Y");
        renderPlanet(
                binding.partnerPlanetImage, binding.partnerPlanet,
                profile.partnerName(), profile.partnerPhoto(), "?");
        binding.partnerPlanetImage.setContentDescription(
                profile.partnerName() == null ? getString(R.string.partner_planet) : profile.partnerName());
    }

    private static void renderPlanet(
            android.widget.ImageView image,
            android.widget.TextView fallback,
            String name,
            byte[] bytes,
            String defaultInitial) {
        if (bytes == null || bytes.length == 0) {
            image.setVisibility(View.GONE);
            fallback.setVisibility(View.VISIBLE);
            fallback.setText(name == null || name.isBlank()
                    ? defaultInitial : name.substring(0, 1).toUpperCase());
            return;
        }
        image.setImageBitmap(BitmapFactory.decodeByteArray(bytes, 0, bytes.length));
        image.setVisibility(View.VISIBLE);
        fallback.setVisibility(View.GONE);
    }

    private void reconcileQuizNotifications() {
        if (orbit.isSignedIn() && PermissionChecks.notificationsGranted(this)) {
            PartnerNotificationWorker.schedule(this, true);
            PartnerNotificationWorker.enqueue(this);
        } else {
            PartnerNotificationWorker.schedule(this, false);
        }
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
        if (orbit.isSignedIn() && locationReady) {
            orbit.preferences().thenAccept(preferences -> runOnUiThread(() ->
                    reconcileLocation(preferences))).exceptionally(failure -> null);
        }
        wearStatus.check().thenAccept(state -> runOnUiThread(() -> renderWearStatus(state)));
    }

    private void renderLocationStatus(com.littleorbit.data.remote.ApiModels.Preferences preferences) {
        if (isFinishing()) return;
        binding.locationStatus.setText(
                preferences.locationByBoth
                        ? R.string.location_ready_both
                        : preferences.locationByMe
                                ? R.string.location_waiting_partner
                                : R.string.location_server_off);
    }

    private void reconcileLocation(com.littleorbit.data.remote.ApiModels.Preferences preferences) {
        renderLocationStatus(preferences);
        binding.pauseNearbyButton.setVisibility(
                preferences.locationByMe ? View.VISIBLE : View.GONE);
        com.littleorbit.data.LocationCollectionWorker.schedule(this, preferences.locationByMe);
        if (preferences.locationByBoth) ForegroundLocationService.start(this);
        else ForegroundLocationService.stop(this);
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
        int text = switch (state) {
            case APP_CONNECTED -> R.string.wear_connected;
            case APP_MISSING -> R.string.wear_missing;
            case NO_WATCH -> R.string.wear_no_watch;
            case UNAVAILABLE -> R.string.wear_status_unavailable;
        };
        binding.wearStatus.setText(text);
        binding.wearInstallButton.setEnabled(state != WearStatusChecker.State.APP_CONNECTED);
    }

    private void maybeOfferSetup(HomeScreenState state) {
        if (!state.connected() || setupLookupStarted) return;
        setupLookupStarted = true;
        orbit.preferences().thenAccept(preferences -> runOnUiThread(() -> {
            if (isFinishing()) return;
            String key = "setup_prompted_" + preferences.coupleId;
            android.content.SharedPreferences values =
                    getSharedPreferences("device_setup", MODE_PRIVATE);
            if (values.getBoolean(key, false)) return;
            values.edit().putBoolean(key, true).apply();
            new AlertDialog.Builder(this)
                    .setTitle(R.string.finish_setup)
                    .setMessage(R.string.setup_prompt)
                    .setNegativeButton(R.string.later, null)
                    .setPositiveButton(
                            R.string.start_setup,
                            (dialog, which) -> open(DeviceSetupActivity.class))
                    .show();
        })).exceptionally(failure -> null);
    }

    private void showHome() {
        binding.homeScroll.setVisibility(View.VISIBLE);
        binding.moreScroll.setVisibility(View.GONE);
    }

    private void showMore() {
        binding.homeScroll.setVisibility(View.GONE);
        binding.moreScroll.setVisibility(View.VISIBLE);
    }

    @Override
    protected OrbitDestination orbitDestination() {
        return getIntent().getBooleanExtra(EXTRA_SHOW_MORE, false)
                ? OrbitDestination.SETTINGS
                : OrbitDestination.HOME;
    }

    @Override
    protected void onOrbitContextOpened() {
        if (activityPanel != null) activityPanel.markVisibleSeen();
    }

    @Override
    public void onUpdateState(UpdatePresentation presentation) {
        activeUpdate = presentation;
        String phase = presentation.progress().phase();
        boolean offer = presentation.decision() == UpdatePolicy.Decision.OPTIONAL
                || presentation.decision() == UpdatePolicy.Decision.REQUIRED;
        boolean hidden = UpdaterStateMachine.DEFERRED.equals(phase)
                || UpdaterStateMachine.INSTALLED.equals(phase);
        binding.updateBanner.setVisibility(offer && !hidden ? View.VISIBLE : View.GONE);
        binding.updateBannerText.setText(getString(
                R.string.update_version, presentation.release().version()));
        boolean automatic = offer && !hidden && updates.claimAutomaticPrompt();
        if (presentation.required() || isActivePhase(phase)
                || notificationRequestedUpdate || automatic) {
            notificationRequestedUpdate = false;
            showUpdateSheet();
        }
        if (manualUpdateCheck) {
            manualUpdateCheck = false;
            handleManualCheck(presentation, hidden);
        }
        renderUpdateSheet();
        renderLastUpdateCheck();
    }

    private void handleManualCheck(UpdatePresentation presentation, boolean hidden) {
        if (presentation.decision() == UpdatePolicy.Decision.CURRENT || hidden) {
            Toast.makeText(this, R.string.up_to_date, Toast.LENGTH_LONG).show();
        } else if (UpdaterStateMachine.FAILED.equals(presentation.progress().phase())) {
            Toast.makeText(this, statusText(presentation.progress().phase()), Toast.LENGTH_LONG).show();
        } else {
            showUpdateSheet();
        }
    }

    private void showUpdateSheet() {
        if (activeUpdate == null || isFinishing()) return;
        if (updateSheet == null) {
            updateBinding = DialogUpdateBinding.inflate(getLayoutInflater());
            updateSheet = new BottomSheetDialog(this);
            updateSheet.setContentView(updateBinding.getRoot());
            updateBinding.updatePrimary.setOnClickListener(view -> performUpdatePrimary());
            updateBinding.updateLater.setOnClickListener(view -> performUpdateSecondary());
            updateBinding.updateManual.setOnClickListener(view -> openWeb("/download"));
            updateSheet.setOnDismissListener(ignored -> {
                updateSheet = null;
                updateBinding = null;
            });
        }
        updateSheet.setCancelable(!activeUpdate.required());
        renderUpdateSheet();
        if (!updateSheet.isShowing()) updateSheet.show();
    }

    private void renderUpdateSheet() {
        if (updateBinding == null || activeUpdate == null) return;
        String phase = activeUpdate.progress().phase();
        updateBinding.updateVersion.setText(getString(
                R.string.update_version, activeUpdate.release().version()));
        updateBinding.updateMessage.setText(getString(
                activeUpdate.required()
                        ? R.string.update_required_message
                        : R.string.update_optional_message,
                activeUpdate.release().releaseNotes()));
        boolean active = isActivePhase(phase);
        boolean cancelable = isDownloadPhase(phase);
        updateBinding.updateProgress.setVisibility(active ? View.VISIBLE : View.GONE);
        updateBinding.updateProgress.setProgress(activeUpdate.percent());
        updateBinding.updateStatus.setVisibility(active ? View.VISIBLE : View.GONE);
        updateBinding.updateStatus.setText(statusMessage(phase));
        updateBinding.updatePrimary.setText(primaryText(phase));
        updateBinding.updatePrimary.setEnabled(!UpdaterStateMachine.DOWNLOADING.equals(phase)
                && !UpdaterStateMachine.VERIFYING.equals(phase)
                && !UpdaterStateMachine.INSTALLING.equals(phase)
                && !UpdaterStateMachine.AWAITING_CONFIRMATION.equals(phase));
        boolean installing = UpdaterStateMachine.INSTALLING.equals(phase)
                || UpdaterStateMachine.AWAITING_CONFIRMATION.equals(phase);
        updateBinding.updateLater.setVisibility(
                UpdaterStateMachine.INSTALLED.equals(phase) || installing
                        ? View.GONE : View.VISIBLE);
        updateBinding.updateLater.setText(
                cancelable
                        ? R.string.cancel
                        : activeUpdate.required() ? R.string.exit_app : R.string.later);
    }

    private void performUpdatePrimary() {
        if (activeUpdate == null) return;
        String phase = activeUpdate.progress().phase();
        if (UpdaterStateMachine.PERMISSION_REQUIRED.equals(phase)) {
            Intent settings = new Intent(
                    Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                    Uri.parse("package:" + getPackageName()));
            installPermission.launch(settings);
        } else {
            updates.startUpdate();
        }
    }

    private void performUpdateSecondary() {
        if (activeUpdate == null) return;
        if (isDownloadPhase(activeUpdate.progress().phase())) {
            updates.cancelDownload();
        } else if (activeUpdate.required()) {
            finishAndRemoveTask();
        } else {
            updates.deferOptional();
            if (updateSheet != null) updateSheet.dismiss();
        }
    }

    private int primaryText(String phase) {
        if (UpdaterStateMachine.PERMISSION_REQUIRED.equals(phase)) return R.string.open_settings;
        if (UpdaterStateMachine.RETRY_DOWNLOAD.equals(phase)
                || UpdaterStateMachine.RETRY_INSTALL.equals(phase)
                || UpdaterStateMachine.FAILED.equals(phase)) return R.string.retry;
        return R.string.update_now;
    }

    private int statusText(String phase) {
        if (UpdaterStateMachine.DOWNLOADING.equals(phase)
                || UpdaterStateMachine.PAUSED.equals(phase)) return R.string.update_downloading;
        if (UpdaterStateMachine.VERIFYING.equals(phase)) return R.string.update_verifying;
        if (UpdaterStateMachine.PERMISSION_REQUIRED.equals(phase)) return R.string.update_permission;
        if (UpdaterStateMachine.INSTALLING.equals(phase)) return R.string.update_installing;
        if (UpdaterStateMachine.AWAITING_CONFIRMATION.equals(phase)) return R.string.update_confirm;
        if (UpdaterStateMachine.RETRY_DOWNLOAD.equals(phase)) return R.string.update_retry_download;
        if (UpdaterStateMachine.RETRY_INSTALL.equals(phase)) return R.string.update_retry_install;
        if (activeUpdate != null
                && activeUpdate.decision() == UpdatePolicy.Decision.DEVICE_INCOMPATIBLE) {
            return R.string.update_device_incompatible;
        }
        return R.string.update_check_failed;
    }

    private String statusMessage(String phase) {
        if (UpdaterStateMachine.DOWNLOADING.equals(phase)
                || UpdaterStateMachine.PAUSED.equals(phase)) {
            return getString(R.string.update_downloading, activeUpdate.percent());
        }
        return getString(statusText(phase));
    }

    private static boolean isActivePhase(String phase) {
        return UpdaterStateMachine.DOWNLOADING.equals(phase)
                || UpdaterStateMachine.PAUSED.equals(phase)
                || UpdaterStateMachine.VERIFYING.equals(phase)
                || UpdaterStateMachine.PERMISSION_REQUIRED.equals(phase)
                || UpdaterStateMachine.INSTALLING.equals(phase)
                || UpdaterStateMachine.AWAITING_CONFIRMATION.equals(phase)
                || UpdaterStateMachine.RETRY_DOWNLOAD.equals(phase)
                || UpdaterStateMachine.RETRY_INSTALL.equals(phase);
    }

    private static boolean isDownloadPhase(String phase) {
        return UpdaterStateMachine.DOWNLOADING.equals(phase)
                || UpdaterStateMachine.PAUSED.equals(phase)
                || UpdaterStateMachine.VERIFYING.equals(phase);
    }

    private void openWeb(String path) {
        startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse("https://lil-orb.pax-kun.com" + path)));
    }

    private void open(Class<? extends AppCompatActivity> activity) {
        startActivity(new Intent(this, activity));
    }
}
