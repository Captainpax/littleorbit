package com.littleorbit.mobile;

import android.content.Intent;
import android.net.Uri;
import android.provider.Settings;
import android.view.View;
import android.widget.TextView;
import android.widget.Toast;
import androidx.activity.result.ActivityResultLauncher;
import com.google.android.material.bottomsheet.BottomSheetDialog;
import com.google.android.material.dialog.MaterialAlertDialogBuilder;
import com.google.android.material.materialswitch.MaterialSwitch;
import com.littleorbit.domain.UpdatePolicy;
import com.littleorbit.domain.UpdaterStateMachine;
import com.littleorbit.mobile.databinding.DialogUpdateBinding;
import java.time.Instant;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;

/** Renders the shared, verified update flow without owning a top-level destination. */
final class UpdateUiController implements AndroidUpdateCoordinator.Listener {
    private final OrbitShellActivity activity;
    private final AndroidUpdateCoordinator updates;
    private final ActivityResultLauncher<Intent> installPermission;
    private final boolean allowAutomaticPrompt;
    private BottomSheetDialog sheet;
    private DialogUpdateBinding sheetBinding;
    private UpdatePresentation activeUpdate;
    private View banner;
    private TextView bannerText;
    private MaterialSwitch automaticDetection;
    private TextView lastCheck;
    private boolean manualCheck;
    private boolean requestedSheet;

    UpdateUiController(
            OrbitShellActivity activity,
            AndroidUpdateCoordinator updates,
            ActivityResultLauncher<Intent> installPermission,
            boolean allowAutomaticPrompt) {
        this.activity = activity;
        this.updates = updates;
        this.installPermission = installPermission;
        this.allowAutomaticPrompt = allowAutomaticPrompt;
    }

    void bindBanner(View banner, TextView bannerText) {
        this.banner = banner;
        this.bannerText = bannerText;
        banner.setOnClickListener(ignored -> showSheet());
    }

    void bindPreferences(
            MaterialSwitch automaticDetection,
            TextView lastCheck,
            View checkButton) {
        this.automaticDetection = automaticDetection;
        this.lastCheck = lastCheck;
        automaticDetection.setChecked(updates.autoDetectionEnabled());
        automaticDetection.setOnCheckedChangeListener((button, checked) -> {
            if (button.isPressed()) updates.setAutoDetectionEnabled(checked);
        });
        checkButton.setOnClickListener(ignored -> checkManually());
        renderLastCheck();
    }

    void promptForAutomaticDetection() {
        if (!allowAutomaticPrompt || updates.hasAutoDetectionChoice()) return;
        new MaterialAlertDialogBuilder(activity)
                .setTitle(R.string.auto_update_prompt_title)
                .setMessage(R.string.auto_update_prompt_message)
                .setNegativeButton(R.string.not_now, (dialog, which) -> setAutomatic(false))
                .setPositiveButton(R.string.enable_auto_updates, (dialog, which) -> {
                    setAutomatic(true);
                    updates.check(true, this);
                })
                .show();
    }

    void requestSheet() {
        requestedSheet = true;
    }

    void resume() {
        updates.check(false, this);
    }

    void pause() {
        updates.stopObserving(this);
    }

    void resumeInstallAfterPermission() {
        updates.resumeInstallAfterPermission();
    }

    void checkManually() {
        manualCheck = true;
        updates.check(true, this);
        Toast.makeText(activity, R.string.loading, Toast.LENGTH_SHORT).show();
    }

    @Override
    public void onUpdateState(UpdatePresentation presentation) {
        activeUpdate = presentation;
        String phase = presentation.progress().phase();
        boolean offer = presentation.decision() == UpdatePolicy.Decision.OPTIONAL
                || presentation.decision() == UpdatePolicy.Decision.REQUIRED;
        boolean hidden = UpdaterStateMachine.DEFERRED.equals(phase)
                || UpdaterStateMachine.INSTALLED.equals(phase);
        renderBanner(offer && !hidden, presentation.release().version());
        maybeShowSheet(presentation, phase, offer, hidden);
        renderSheet();
        renderLastCheck();
    }

    private void maybeShowSheet(
            UpdatePresentation presentation,
            String phase,
            boolean offer,
            boolean hidden) {
        boolean automatic = offer && !hidden && allowAutomaticPrompt
                && updates.claimAutomaticPrompt();
        if (presentation.required() || isActivePhase(phase) || requestedSheet || automatic) {
            requestedSheet = false;
            showSheet();
        }
        if (!manualCheck) return;
        manualCheck = false;
        if (presentation.decision() == UpdatePolicy.Decision.CURRENT || hidden) {
            Toast.makeText(activity, R.string.up_to_date, Toast.LENGTH_LONG).show();
        } else if (UpdaterStateMachine.FAILED.equals(phase)) {
            Toast.makeText(activity, statusText(phase), Toast.LENGTH_LONG).show();
        } else {
            showSheet();
        }
    }

    private void renderBanner(boolean visible, String version) {
        if (banner == null || bannerText == null) return;
        banner.setVisibility(visible ? View.VISIBLE : View.GONE);
        bannerText.setText(activity.getString(R.string.update_version, version));
    }

    private void setAutomatic(boolean enabled) {
        updates.setAutoDetectionEnabled(enabled);
        if (automaticDetection != null) automaticDetection.setChecked(enabled);
    }

    private void renderLastCheck() {
        if (lastCheck == null) return;
        long checked = updates.lastCheckedAtMillis();
        String value = checked <= 0 ? activity.getString(R.string.never)
                : DateTimeFormatter.ofPattern("MMM d · h:mm a")
                        .withZone(ZoneId.systemDefault())
                        .format(Instant.ofEpochMilli(checked));
        lastCheck.setText(activity.getString(R.string.last_update_check, value));
    }

    private void showSheet() {
        if (activeUpdate == null || activity.isFinishing()) return;
        if (sheet == null) createSheet();
        sheet.setCancelable(!activeUpdate.required());
        renderSheet();
        if (!sheet.isShowing()) sheet.show();
    }

    private void createSheet() {
        sheetBinding = DialogUpdateBinding.inflate(activity.getLayoutInflater());
        sheet = new BottomSheetDialog(activity);
        sheet.setContentView(sheetBinding.getRoot());
        sheetBinding.updatePrimary.setOnClickListener(ignored -> performPrimary());
        sheetBinding.updateLater.setOnClickListener(ignored -> performSecondary());
        sheetBinding.updateManual.setOnClickListener(ignored -> openDownloadPage());
        sheet.setOnDismissListener(ignored -> {
            sheet = null;
            sheetBinding = null;
        });
    }

    private void renderSheet() {
        if (sheetBinding == null || activeUpdate == null) return;
        String phase = activeUpdate.progress().phase();
        sheetBinding.updateVersion.setText(activity.getString(
                R.string.update_version, activeUpdate.release().version()));
        sheetBinding.updateMessage.setText(activity.getString(
                activeUpdate.required()
                        ? R.string.update_required_message
                        : R.string.update_optional_message,
                activeUpdate.release().releaseNotes()));
        boolean active = isActivePhase(phase);
        sheetBinding.updateProgress.setVisibility(active ? View.VISIBLE : View.GONE);
        sheetBinding.updateProgress.setProgress(activeUpdate.percent());
        sheetBinding.updateStatus.setVisibility(active ? View.VISIBLE : View.GONE);
        sheetBinding.updateStatus.setText(statusMessage(phase));
        renderSheetActions(phase);
    }

    private void renderSheetActions(String phase) {
        boolean cancelable = isDownloadPhase(phase);
        sheetBinding.updatePrimary.setText(primaryText(phase));
        sheetBinding.updatePrimary.setEnabled(!UpdaterStateMachine.DOWNLOADING.equals(phase)
                && !UpdaterStateMachine.VERIFYING.equals(phase)
                && !UpdaterStateMachine.INSTALLING.equals(phase)
                && !UpdaterStateMachine.AWAITING_CONFIRMATION.equals(phase));
        boolean installing = UpdaterStateMachine.INSTALLING.equals(phase)
                || UpdaterStateMachine.AWAITING_CONFIRMATION.equals(phase);
        sheetBinding.updateLater.setVisibility(
                UpdaterStateMachine.INSTALLED.equals(phase) || installing
                        ? View.GONE : View.VISIBLE);
        sheetBinding.updateLater.setText(
                cancelable
                        ? R.string.cancel
                        : activeUpdate.required() ? R.string.exit_app : R.string.later);
    }

    private void performPrimary() {
        if (activeUpdate == null) return;
        if (UpdaterStateMachine.PERMISSION_REQUIRED.equals(activeUpdate.progress().phase())) {
            Intent settings = new Intent(
                    Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                    Uri.parse("package:" + activity.getPackageName()));
            installPermission.launch(settings);
        } else {
            updates.startUpdate();
        }
    }

    private void performSecondary() {
        if (activeUpdate == null) return;
        if (isDownloadPhase(activeUpdate.progress().phase())) {
            updates.cancelDownload();
        } else if (activeUpdate.required()) {
            activity.finishAndRemoveTask();
        } else {
            updates.deferOptional();
            if (sheet != null) sheet.dismiss();
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
            return activity.getString(R.string.update_downloading, activeUpdate.percent());
        }
        return activity.getString(statusText(phase));
    }

    private void openDownloadPage() {
        activity.startActivity(new Intent(
                Intent.ACTION_VIEW, Uri.parse("https://lil-orb.pax-kun.com/download")));
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
}
