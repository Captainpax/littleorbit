package com.littleorbit.mobile;

import android.content.Intent;
import android.os.Bundle;
import android.view.View;
import android.widget.ArrayAdapter;
import android.widget.AdapterView;
import com.google.android.gms.wearable.Node;
import com.google.android.gms.wearable.Wearable;
import com.google.android.material.dialog.MaterialAlertDialogBuilder;
import com.littleorbit.data.ManagedWatchCoordinator;
import com.littleorbit.data.ManagedWatchStore;
import com.littleorbit.domain.WatchProtocol;
import com.littleorbit.mobile.databinding.ActivityWatchSettingsBinding;
import dagger.hilt.android.AndroidEntryPoint;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import javax.inject.Inject;
import org.json.JSONObject;

/** One phone-owned control surface for selection, privacy, updates, repair, and removal. */
@AndroidEntryPoint
public final class WatchSettingsActivity extends InsetAwareActivity {
    @Inject ManagedWatchStore watches;
    @Inject ManagedWatchCoordinator coordinator;
    @Inject WearReleaseClient releases;
    private ActivityWatchSettingsBinding binding;
    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private List<Node> connected = List.of();
    private boolean rendering;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        binding = ActivityWatchSettingsBinding.inflate(getLayoutInflater());
        setContentView(binding.getRoot());
        bindDestination();
        bindActions();
    }

    @Override
    protected void onResume() {
        super.onResume();
        render();
        discover();
        requestStatus();
        checkRelease();
    }

    @Override
    protected void onDestroy() {
        executor.shutdownNow();
        super.onDestroy();
    }

    private void bindDestination() {
        ArrayAdapter<CharSequence> adapter = ArrayAdapter.createFromResource(
                this, R.array.watch_destinations, android.R.layout.simple_spinner_item);
        adapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
        binding.watchDestination.setAdapter(adapter);
        binding.watchDestination.setOnItemSelectedListener(new AdapterView.OnItemSelectedListener() {
            @Override public void onItemSelected(AdapterView<?> parent, View view, int position, long id) {
                if (!rendering) savePreferences();
            }
            @Override public void onNothingSelected(AdapterView<?> parent) { }
        });
    }

    private void bindActions() {
        binding.watchBack.setOnClickListener(view -> finish());
        binding.selectWatch.setOnClickListener(view -> chooseWatch());
        binding.watchPhotos.setOnCheckedChangeListener((button, checked) -> savePreferences());
        binding.watchCountdownTitles.setOnCheckedChangeListener((button, checked) -> savePreferences());
        binding.watchSmooches.setOnCheckedChangeListener((button, checked) -> savePreferences());
        binding.watchUpdateAlerts.setOnCheckedChangeListener((button, checked) -> savePreferences());
        binding.installOrUpdateWatch.setOnClickListener(view -> openInstaller("install"));
        binding.repairWatch.setOnClickListener(view -> openInstaller("repair"));
        binding.watchDiagnostics.setOnClickListener(view -> showDiagnostics());
        binding.removeWatch.setOnClickListener(view -> confirmRemoval());
    }

    private void render() {
        ManagedWatchStore.Snapshot watch = watches.read();
        rendering = true;
        binding.watchName.setText(watch.enabled()
                ? displayName(watch) : getString(R.string.no_managed_watch));
        binding.watchPreferences.setVisibility(watch.enabled() ? View.VISIBLE : View.GONE);
        binding.watchPhotos.setChecked(watch.showPhotos());
        binding.watchCountdownTitles.setChecked(watch.showCountdownTitles());
        binding.watchSmooches.setChecked(watch.smoochEnabled());
        binding.watchUpdateAlerts.setChecked(watch.updateAlerts());
        binding.watchDestination.setSelection(destinationIndex(watch.defaultDestination()));
        binding.watchVersionStatus.setText(versionText(watch));
        rendering = false;
    }

    private void discover() {
        binding.watchConnectionStatus.setText(R.string.wear_searching);
        Wearable.getNodeClient(this).getConnectedNodes()
                .addOnFailureListener(failure -> binding.watchConnectionStatus.setText(
                        R.string.wear_status_unavailable))
                .addOnSuccessListener(nodes -> {
                    connected = List.copyOf(nodes);
                    renderConnection();
                });
    }

    private void renderConnection() {
        ManagedWatchStore.Snapshot watch = watches.read();
        boolean selectedConnected = connected.stream()
                .anyMatch(node -> node.getId().equals(watch.nodeId()));
        int text = selectedConnected ? R.string.watch_connected_now
                : connected.isEmpty() ? R.string.wear_no_watch : R.string.watch_choose_connected;
        binding.watchConnectionStatus.setText(text);
        binding.selectWatch.setText(watch.enabled()
                ? R.string.switch_managed_watch : R.string.choose_managed_watch);
    }

    private void chooseWatch() {
        if (connected.isEmpty()) {
            binding.watchConnectionStatus.setText(R.string.wear_no_watch);
            return;
        }
        String[] labels = connected.stream().map(Node::getDisplayName).toArray(String[]::new);
        new MaterialAlertDialogBuilder(this)
                .setTitle(R.string.choose_managed_watch)
                .setItems(labels, (dialog, which) -> confirmSelection(connected.get(which)))
                .show();
    }

    private void confirmSelection(Node node) {
        new MaterialAlertDialogBuilder(this)
                .setTitle(R.string.confirm_managed_watch)
                .setMessage(getString(R.string.confirm_managed_watch_message, node.getDisplayName()))
                .setNegativeButton(R.string.cancel, null)
                .setPositiveButton(R.string.use_this_watch, (dialog, which) -> {
                    coordinator.select(node.getId(), node.getDisplayName());
                    render();
                    requestStatus();
                }).show();
    }

    private void savePreferences() {
        if (rendering || !watches.read().enabled()) return;
        coordinator.updatePreferences(
                binding.watchPhotos.isChecked(), binding.watchCountdownTitles.isChecked(),
                binding.watchSmooches.isChecked(), binding.watchUpdateAlerts.isChecked(),
                destination(binding.watchDestination.getSelectedItemPosition()));
    }

    private void requestStatus() {
        ManagedWatchStore.Snapshot watch = watches.read();
        if (!watch.enabled()) return;
        try {
            byte[] data = new JSONObject().put("protocol", WatchProtocol.VERSION)
                    .put("watch_generation", watch.generation()).toString()
                    .getBytes(StandardCharsets.UTF_8);
            Wearable.getMessageClient(this).sendMessage(
                    watch.nodeId(), WatchProtocol.STATUS_REQUEST, data)
                    .addOnSuccessListener(ignored -> binding.getRoot().postDelayed(this::render, 800));
        } catch (Exception ignored) {
            // The connection label remains sufficient when live status is unavailable.
        }
    }

    private void checkRelease() {
        executor.execute(() -> {
            try {
                WearReleaseMetadata release = releases.metadata();
                runOnUiThread(() -> renderRelease(release));
            } catch (Exception ignored) {
                // Installed status remains useful offline; no APK is downloaded here.
            }
        });
    }

    private void renderRelease(WearReleaseMetadata release) {
        ManagedWatchStore.Snapshot watch = watches.read();
        boolean update = watch.versionCode() > 0 && watch.versionCode() < release.versionCode();
        binding.installOrUpdateWatch.setText(update
                ? R.string.update_watch_app : R.string.install_or_update_watch);
        if (update) binding.watchVersionStatus.setText(
                getString(R.string.watch_update_available, release.version()));
    }

    private void showDiagnostics() {
        ManagedWatchStore.Snapshot watch = watches.read();
        String message = getString(R.string.watch_diagnostics_value,
                watch.versionName().isBlank() ? getString(R.string.unavailable) : watch.versionName(),
                watch.protocolVersion(), watch.queuedActions(),
                watch.lastSeenAt() > 0 ? getString(R.string.watch_recently_seen)
                        : getString(R.string.watch_not_seen));
        new MaterialAlertDialogBuilder(this).setTitle(R.string.watch_diagnostics)
                .setMessage(message).setPositiveButton(android.R.string.ok, null).show();
    }

    private void confirmRemoval() {
        new MaterialAlertDialogBuilder(this).setTitle(R.string.remove_watch_privately)
                .setMessage(R.string.remove_watch_warning)
                .setNegativeButton(R.string.cancel, null)
                .setPositiveButton(R.string.continue_label,
                        (dialog, which) -> openInstaller("remove")).show();
    }

    private void openInstaller(String mode) {
        startActivity(new Intent(this, WearInstallerActivity.class)
                .putExtra(WearInstallerActivity.EXTRA_MODE, mode));
    }

    private String displayName(ManagedWatchStore.Snapshot watch) {
        return watch.displayName().isBlank() ? getString(R.string.managed_watch) : watch.displayName();
    }

    private String versionText(ManagedWatchStore.Snapshot watch) {
        if (watch.versionName().isBlank()) return getString(R.string.watch_version_unknown);
        return getString(R.string.watch_version_value, watch.versionName(), watch.versionCode());
    }

    private static int destinationIndex(String value) {
        if (ManagedWatchStore.DESTINATION_COUNTDOWN.equals(value)) return 1;
        if (ManagedWatchStore.DESTINATION_SMOOCH.equals(value)) return 2;
        return 0;
    }

    private static String destination(int index) {
        if (index == 1) return ManagedWatchStore.DESTINATION_COUNTDOWN;
        if (index == 2) return ManagedWatchStore.DESTINATION_SMOOCH;
        return ManagedWatchStore.DESTINATION_TOGETHER;
    }
}
