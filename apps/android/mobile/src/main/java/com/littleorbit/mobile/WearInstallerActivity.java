package com.littleorbit.mobile;

import android.Manifest;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Bundle;
import android.os.SystemClock;
import android.view.View;
import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;
import com.google.android.material.dialog.MaterialAlertDialogBuilder;
import com.littleorbit.mobile.databinding.ActivityWearInstallerBinding;
import dagger.hilt.android.AndroidEntryPoint;
import java.io.File;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import javax.inject.Inject;

/** Phone-hosted wireless-ADB wizard for the verified self-hosted Wear APK. */
@AndroidEntryPoint
public final class WearInstallerActivity extends InsetAwareActivity {
    private static final long TLS_READY_TIMEOUT_MS = 30_000;
    private ActivityWearInstallerBinding binding;
    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private volatile WearEndpointRegistry.Snapshot endpoints = WearEndpointRegistry.Snapshot.empty();
    private NsdWatchDiscovery.Session discovery;
    private volatile WearReleaseMetadata release;
    private volatile File verifiedApk;
    private volatile boolean manualOverride;
    private volatile boolean artifactPreparing;
    @Inject WearReleaseClient releases;
    @Inject WearApkVerifier verifier;
    @Inject NsdWatchDiscovery nsd;
    @Inject KadbWatchClient adb;
    @Inject EncryptedKadbPrivateKeyStore keys;

    private final ActivityResultLauncher<String> nearbyPermission = registerForActivityResult(
            new ActivityResultContracts.RequestPermission(), granted -> {
                if (granted) startDiscovery(); else showManualDiscovery();
            });

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        binding = ActivityWearInstallerBinding.inflate(getLayoutInflater());
        setContentView(binding.getRoot());
        binding.showManualWear.setOnClickListener(view -> showManualFields());
        binding.restartWearDiscovery.setOnClickListener(view -> requestDiscoveryPermission());
        binding.retryWearArtifact.setOnClickListener(view -> prepareArtifact());
        binding.installWearNow.setOnClickListener(view -> beginInstall());
        binding.forgetWearKey.setOnClickListener(view -> forgetIdentity());
        syncIdentityButton();
        prepareArtifact();
        requestDiscoveryPermission();
    }

    @Override
    protected void onStop() {
        binding.wearPairingCode.setText("");
        super.onStop();
    }

    @Override
    protected void onDestroy() {
        if (discovery != null) discovery.close();
        executor.shutdownNow();
        super.onDestroy();
    }

    private void showManualFields() {
        manualOverride = true;
        binding.manualWearFields.setVisibility(View.VISIBLE);
        binding.showManualWear.setVisibility(View.GONE);
    }

    private void requestDiscoveryPermission() {
        if (Build.VERSION.SDK_INT >= 33
                && checkSelfPermission(Manifest.permission.NEARBY_WIFI_DEVICES)
                        != PackageManager.PERMISSION_GRANTED) {
            nearbyPermission.launch(Manifest.permission.NEARBY_WIFI_DEVICES);
        } else startDiscovery();
    }

    private void startDiscovery() {
        if (discovery != null) discovery.close();
        manualOverride = false;
        endpoints = WearEndpointRegistry.Snapshot.empty();
        binding.manualWearFields.setVisibility(View.GONE);
        binding.showManualWear.setVisibility(View.VISIBLE);
        binding.wearDiscoveryStatus.setText(R.string.wear_searching);
        try {
            discovery = nsd.discover(new NsdWatchDiscovery.Listener() {
                @Override public void onUpdate(WearEndpointRegistry.Snapshot value) {
                    runOnUiThread(() -> discovered(value));
                }
                @Override public void onFailure() {
                    runOnUiThread(() -> showManualDiscovery());
                }
            });
        } catch (SecurityException | IllegalArgumentException unavailable) {
            showManualDiscovery();
        }
    }

    private void discovered(WearEndpointRegistry.Snapshot value) {
        endpoints = value;
        WearEndpointRegistry.Endpoint pairing = value.pairing();
        if (!manualOverride && pairing != null) {
            binding.wearHost.setText(pairing.host());
            binding.wearPairPort.setText(String.format(Locale.getDefault(), "%d", pairing.port()));
        }
        if (!manualOverride && value.connect() != null) {
            binding.wearConnectPort.setText(String.format(
                    Locale.getDefault(), "%d", value.connect().port()));
        }
        int message = discoveryMessage(value);
        binding.wearDiscoveryStatus.setText(message);
    }

    private int discoveryMessage(WearEndpointRegistry.Snapshot value) {
        if (value.pairing() != null && value.connect() != null) return R.string.wear_found;
        if (keys.isRemembered() && !value.connectCandidates().isEmpty()) {
            return R.string.wear_remembered_found;
        }
        return R.string.wear_searching;
    }

    private void showManualDiscovery() {
        showManualFields();
        binding.wearDiscoveryStatus.setText(R.string.wear_discovery_failed);
    }

    private void prepareArtifact() {
        if (artifactPreparing) return;
        artifactPreparing = true;
        release = null;
        verifiedApk = null;
        binding.retryWearArtifact.setVisibility(View.GONE);
        status(R.string.wear_preparing, true, false);
        executor.execute(() -> {
            try {
                WearReleaseMetadata metadata = releases.metadata();
                File apk = releases.download(metadata);
                String failure = verifier.verify(metadata, apk);
                if (failure != null) throw new IllegalStateException(failure);
                release = metadata;
                verifiedApk = apk;
                artifactPreparing = false;
                status(R.string.wear_ready, false, true);
            } catch (Exception failure) {
                artifactPreparing = false;
                status(R.string.wear_prepare_failed, false, false);
                showArtifactRetry();
            }
        });
    }

    private void beginInstall() {
        if (release == null || verifiedApk == null) return;
        WearInstallRequest request = installRequest();
        if (!request.canStart(keys.isRemembered())) {
            showManualFields();
            binding.wearDiscoveryStatus.setText(R.string.wear_address_needed);
            return;
        }
        binding.wearPairingCode.setText("");
        setBusy(keys.isRemembered() ? R.string.wear_connecting : R.string.wear_pairing);
        executor.execute(() -> connectInspectAndInstall(request));
    }

    private WearInstallRequest installRequest() {
        String host = binding.wearHost.getText().toString().trim();
        int pairPort = number(binding.wearPairPort.getText().toString());
        int connectPort = number(binding.wearConnectPort.getText().toString());
        String code = binding.wearPairingCode.getText().toString().trim();
        return WearInstallRequest.create(
                endpoints, manualOverride, host, pairPort, connectPort, code);
    }

    private void connectInspectAndInstall(WearInstallRequest request) {
        try {
            Inspection inspection = keys.isRemembered()
                    ? inspect(request.connectCandidates()) : Inspection.empty();
            if (inspection.selected == null) inspection = pairAndInspect(request, inspection.failure);
            applyPolicy(inspection.selected);
        } catch (WatchAdbException failure) {
            showFailure(failure);
        }
    }

    private Inspection pairAndInspect(WearInstallRequest request, WatchAdbException previous)
            throws WatchAdbException {
        if (!request.canPair()) {
            throw previous != null ? previous : new WatchAdbException(
                    WatchAdbException.Operation.PAIR,
                    WatchAdbException.Reason.AUTHORIZATION_REJECTED);
        }
        status(R.string.wear_pairing, true, false);
        adb.pair(
                request.pairing().host(), request.pairing().port(), request.pairingCode());
        status(R.string.wear_waiting_for_tls, true, false);
        long deadline = SystemClock.elapsedRealtime() + TLS_READY_TIMEOUT_MS;
        WatchAdbException last = null;
        do {
            Inspection attempt = inspect(pairingCandidates(request));
            if (attempt.selected != null) return attempt;
            last = attempt.failure;
            pauseBeforeRetry();
        } while (SystemClock.elapsedRealtime() < deadline);
        if (last != null) throw last;
        throw new WatchAdbException(
                WatchAdbException.Operation.CONNECT, WatchAdbException.Reason.TIMED_OUT);
    }

    private Inspection inspect(List<WearEndpointRegistry.Endpoint> candidates) {
        WatchAdbException last = null;
        int attempts = 0;
        for (WearEndpointRegistry.Endpoint endpoint : candidates) {
            if (++attempts > 8) break;
            try {
                KadbWatchClient.Device device = adb.connectAndInspect(endpoint.host(), endpoint.port());
                if (device.isWatch()) return new Inspection(new Selected(endpoint, device), null);
            } catch (WatchAdbException failure) { last = failure; }
        }
        return new Inspection(null, last);
    }

    private List<WearEndpointRegistry.Endpoint> pairingCandidates(WearInstallRequest request) {
        List<WearEndpointRegistry.Endpoint> result = new ArrayList<>();
        for (WearEndpointRegistry.Endpoint endpoint : endpoints.connectCandidates()) {
            if (endpoint.matchesDevice(request.pairing())) result.add(endpoint);
        }
        for (WearEndpointRegistry.Endpoint endpoint : request.connectCandidates()) {
            if (endpoint.matchesDevice(request.pairing())) result.add(endpoint);
        }
        return WearInstallRequest.unique(result);
    }

    private void applyPolicy(Selected selected) {
        WearInstallPolicy.Decision decision = WearInstallPolicy.decide(release, selected.device);
        if (decision == WearInstallPolicy.Decision.WARN_OLD_PATCH) {
            warnOldPatch(selected);
        } else if (decision == WearInstallPolicy.Decision.INSTALL) {
            install(selected);
        } else if (decision == WearInstallPolicy.Decision.ALREADY_CURRENT) {
            status(R.string.wear_already_current, false, true);
        } else if (decision == WearInstallPolicy.Decision.REJECT_DOWNGRADE) {
            status(R.string.wear_downgrade_blocked, false, true);
        } else status(R.string.wear_not_compatible, false, true);
    }

    private void warnOldPatch(Selected selected) {
        runOnUiThread(() -> new MaterialAlertDialogBuilder(this)
                .setTitle(R.string.wear_patch_warning_title)
                .setMessage(getString(R.string.wear_patch_warning, selected.device.securityPatch()))
                .setNegativeButton(R.string.cancel, (dialog, which) -> setReady())
                .setPositiveButton(R.string.install_anyway, (dialog, which) -> {
                    setBusy(R.string.wear_installing);
                    executor.execute(() -> install(selected));
                }).show());
    }

    private void install(Selected selected) {
        try {
            status(R.string.wear_installing, true, false);
            adb.install(selected.endpoint.host(), selected.endpoint.port(), verifiedApk);
            status(R.string.wear_install_complete, false, true);
        } catch (WatchAdbException failure) { retryInstallAfterRotation(selected, failure); }
    }

    private void retryInstallAfterRotation(Selected selected, WatchAdbException failure) {
        if (!isEndpointFailure(failure)) {
            showFailure(failure);
            return;
        }
        List<WearEndpointRegistry.Endpoint> refreshed = new ArrayList<>();
        for (WearEndpointRegistry.Endpoint endpoint : endpoints.connectCandidates()) {
            if (endpoint.matchesDevice(selected.endpoint)
                    && endpoint.port() != selected.endpoint.port()) refreshed.add(endpoint);
        }
        Inspection inspection = inspect(WearInstallRequest.unique(refreshed));
        if (inspection.selected == null) {
            showFailure(failure);
            return;
        }
        try {
            adb.install(inspection.selected.endpoint.host(),
                    inspection.selected.endpoint.port(), verifiedApk);
            status(R.string.wear_install_complete, false, true);
        } catch (WatchAdbException retryFailure) { showFailure(retryFailure); }
    }

    private void showFailure(WatchAdbException failure) {
        int message = failureMessage(failure);
        status(getString(message, failure.diagnosticCode()), false, true);
        if (isEndpointFailure(failure)
                || failure.reason() == WatchAdbException.Reason.ADDRESS_INVALID) {
            runOnUiThread(() -> {
                showManualFields();
            });
        }
    }

    private int failureMessage(WatchAdbException failure) {
        if (failure.reason() == WatchAdbException.Reason.TLS_RUNTIME_UNAVAILABLE) {
            return R.string.wear_tls_runtime_failed;
        }
        if (failure.reason() == WatchAdbException.Reason.AUTHORIZATION_REJECTED) {
            return R.string.wear_authorization_failed;
        }
        return switch (failure.operation()) {
            case PAIR -> R.string.wear_pair_failed_diagnostic;
            case CONNECT -> R.string.wear_connect_failed_diagnostic;
            case INSPECT -> R.string.wear_inspect_failed_diagnostic;
            case INSTALL -> R.string.wear_install_failed_diagnostic;
        };
    }

    private static boolean isEndpointFailure(WatchAdbException failure) {
        return failure.reason() == WatchAdbException.Reason.ENDPOINT_UNREACHABLE
                || failure.reason() == WatchAdbException.Reason.TIMED_OUT;
    }

    private void forgetIdentity() {
        if (adb.forget()) {
            syncIdentityButton();
            binding.wearInstallStatus.setText(R.string.watch_authorization_forgotten);
        } else binding.wearInstallStatus.setText(R.string.request_failed);
    }

    private void syncIdentityButton() {
        binding.forgetWearKey.setVisibility(keys.isRemembered() ? View.VISIBLE : View.GONE);
    }

    private void showArtifactRetry() {
        runOnUiThread(() -> {
            if (!isFinishing() && !isDestroyed()) {
                binding.retryWearArtifact.setVisibility(View.VISIBLE);
            }
        });
    }

    private void setBusy(int message) { status(message, true, false); }

    private void setReady() { status(R.string.wear_ready, false, true); }

    private void status(int message, boolean busy, boolean enabled) {
        runOnUiThread(() -> status(getString(message), busy, enabled));
    }

    private void status(CharSequence message, boolean busy, boolean enabled) {
        runOnUiThread(() -> {
            if (isFinishing() || isDestroyed()) return;
            binding.wearInstallStatus.setText(message);
            binding.wearInstallProgress.setVisibility(busy ? View.VISIBLE : View.GONE);
            binding.installWearNow.setEnabled(enabled);
            binding.installWearNow.setAlpha(enabled ? 1f : 0.45f);
            syncIdentityButton();
        });
    }

    private static void pauseBeforeRetry() throws WatchAdbException {
        try { Thread.sleep(1_000); }
        catch (InterruptedException interrupted) {
            Thread.currentThread().interrupt();
            throw new WatchAdbException(
                    WatchAdbException.Operation.CONNECT, WatchAdbException.Reason.INTERRUPTED);
        }
    }

    private static int number(String value) {
        try { return Integer.parseInt(value.trim()); }
        catch (NumberFormatException invalid) { return 0; }
    }

    private record Selected(WearEndpointRegistry.Endpoint endpoint,
            KadbWatchClient.Device device) {}

    private record Inspection(Selected selected, WatchAdbException failure) {
        static Inspection empty() { return new Inspection(null, null); }
    }
}
