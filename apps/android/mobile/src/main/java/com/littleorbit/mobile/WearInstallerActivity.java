package com.littleorbit.mobile;

import android.Manifest;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Bundle;
import android.view.View;
import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;
import androidx.appcompat.app.AlertDialog;
import com.littleorbit.mobile.databinding.ActivityWearInstallerBinding;
import dagger.hilt.android.AndroidEntryPoint;
import java.io.File;
import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import javax.inject.Inject;

/** Phone-hosted wireless-ADB wizard for the verified self-hosted Wear APK. */
@AndroidEntryPoint
public final class WearInstallerActivity extends InsetAwareActivity {
    private ActivityWearInstallerBinding binding;
    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private NsdWatchDiscovery.Session discovery;
    private volatile NsdWatchDiscovery.Endpoint pairing;
    private volatile NsdWatchDiscovery.Endpoint connect;
    private final Map<String, NsdWatchDiscovery.Endpoint> connectCandidates = new HashMap<>();
    private volatile WearReleaseMetadata release;
    private volatile File verifiedApk;
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
        binding.showManualWear.setOnClickListener(view -> binding.manualWearFields.setVisibility(
                binding.manualWearFields.getVisibility() == View.VISIBLE ? View.GONE : View.VISIBLE));
        binding.installWearNow.setOnClickListener(view -> beginInstall());
        binding.forgetWearKey.setOnClickListener(view -> forgetIdentity());
        binding.forgetWearKey.setVisibility(keys.isRemembered() ? View.VISIBLE : View.GONE);
        prepareArtifact();
        requestDiscoveryPermission();
    }

    @Override
    protected void onDestroy() {
        if (discovery != null) discovery.close();
        executor.shutdownNow();
        super.onDestroy();
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
        try {
            discovery = nsd.discover(new NsdWatchDiscovery.Listener() {
                @Override public void onPairing(NsdWatchDiscovery.Endpoint value) {
                    runOnUiThread(() -> discovered(value, true));
                }
                @Override public void onConnect(NsdWatchDiscovery.Endpoint value) {
                    runOnUiThread(() -> discovered(value, false));
                }
                @Override public void onFailure() { runOnUiThread(() -> showManualDiscovery()); }
            });
        } catch (SecurityException unavailable) { showManualDiscovery(); }
    }

    private void discovered(NsdWatchDiscovery.Endpoint value, boolean pairEndpoint) {
        if (!pairEndpoint) {
            connectCandidates.put(value.host(), value);
            if (pairing == null || !pairing.host().equals(value.host())) return;
            connect = value;
            binding.wearConnectPort.setText(Integer.toString(value.port()));
        } else {
            pairing = value;
            connect = connectCandidates.get(value.host());
            binding.wearHost.setText(value.host());
            binding.wearPairPort.setText(Integer.toString(value.port()));
            if (connect != null) {
                binding.wearConnectPort.setText(Integer.toString(connect.port()));
            }
        }
        binding.wearDiscoveryStatus.setText(
                pairing != null && connect != null ? R.string.wear_found : R.string.wear_searching);
    }

    private void showManualDiscovery() {
        binding.manualWearFields.setVisibility(View.VISIBLE);
        binding.wearDiscoveryStatus.setText(R.string.wear_discovery_failed);
    }

    private void prepareArtifact() {
        executor.execute(() -> {
            try {
                WearReleaseMetadata metadata = releases.metadata();
                File apk = releases.download(metadata);
                String failure = verifier.verify(metadata, apk);
                if (failure != null) throw new IllegalStateException(failure);
                release = metadata;
                verifiedApk = apk;
                status(R.string.wear_ready, false, true);
            } catch (Exception failure) { status(R.string.wear_prepare_failed, false, false); }
        });
    }

    private void beginInstall() {
        if (release == null || verifiedApk == null) return;
        EndpointInput input = endpointInput();
        if (input == null) {
            binding.manualWearFields.setVisibility(View.VISIBLE);
            binding.wearDiscoveryStatus.setText(R.string.wear_address_needed);
            return;
        }
        setBusy(R.string.wear_pairing);
        executor.execute(() -> connectInspectAndInstall(input));
    }

    private void connectInspectAndInstall(EndpointInput input) {
        String stage = "connect";
        try {
            KadbWatchClient.Device device;
            if (keys.isRemembered()) {
                try { device = adb.connectAndInspect(input.host, input.connectPort); }
                catch (Exception expired) {
                    stage = "pair";
                    device = pairAndInspect(input);
                }
            } else {
                stage = "pair";
                device = pairAndInspect(input);
            }
            stage = "inspect";
            WearInstallPolicy.Decision decision = WearInstallPolicy.decide(release, device);
            if (decision == WearInstallPolicy.Decision.WARN_OLD_PATCH) {
                warnOldPatch(input, device);
            } else if (decision == WearInstallPolicy.Decision.INSTALL) {
                install(input);
            } else if (decision == WearInstallPolicy.Decision.ALREADY_CURRENT) {
                status(R.string.wear_already_current, false, true);
            } else if (decision == WearInstallPolicy.Decision.REJECT_DOWNGRADE) {
                status(R.string.wear_downgrade_blocked, false, true);
            } else status(R.string.wear_not_compatible, false, true);
        } catch (Exception failure) { failure(stage); }
    }

    private KadbWatchClient.Device pairAndInspect(EndpointInput input) throws Exception {
        if (input.code.length() != 6 || input.pairPort <= 0) throw new Exception("Pairing code required");
        adb.pair(input.host, input.pairPort, input.code);
        Exception last = null;
        for (int attempt = 0; attempt < 8; attempt++) {
            try {
                return adb.connectAndInspect(input.host, activeConnectPort(input));
            } catch (Exception unavailable) {
                last = unavailable;
                Thread.sleep(1_500);
            }
        }
        throw new Exception("Paired, but the watch TLS service did not become ready", last);
    }

    private void warnOldPatch(EndpointInput input, KadbWatchClient.Device device) {
        runOnUiThread(() -> new AlertDialog.Builder(this)
                .setTitle(R.string.wear_patch_warning_title)
                .setMessage(getString(R.string.wear_patch_warning, device.securityPatch()))
                .setNegativeButton(R.string.cancel, (dialog, which) -> setReady())
                .setPositiveButton(R.string.install_anyway, (dialog, which) -> {
                    setBusy(R.string.wear_installing);
                    executor.execute(() -> install(input));
                }).show());
    }

    private void install(EndpointInput input) {
        try {
            status(R.string.wear_installing, true, false);
            adb.install(input.host, activeConnectPort(input), verifiedApk);
            status(R.string.wear_install_complete, false, false);
        } catch (Exception failure) { status(R.string.wear_install_failed, false, true); }
    }

    private EndpointInput endpointInput() {
        String manualHost = binding.wearHost.getText().toString().trim();
        String host = manualHost;
        int pairPort = number(binding.wearPairPort.getText().toString());
        int connectPort = number(binding.wearConnectPort.getText().toString());
        String code = binding.wearPairingCode.getText().toString().trim();
        return host.isBlank() || connectPort <= 0
                ? null : new EndpointInput(host, pairPort, connectPort, code);
    }

    private void forgetIdentity() {
        if (adb.forget()) {
            binding.forgetWearKey.setVisibility(View.GONE);
            binding.wearInstallStatus.setText(R.string.watch_authorization_forgotten);
        } else binding.wearInstallStatus.setText(R.string.request_failed);
    }

    private void setBusy(int message) { status(message, true, false); }
    private void setReady() { status(R.string.wear_ready, false, true); }

    private int activeConnectPort(EndpointInput input) {
        NsdWatchDiscovery.Endpoint latest = connect;
        return latest != null && latest.host().equals(input.host)
                ? latest.port() : input.connectPort;
    }

    private void failure(String stage) {
        int message = switch (stage) {
            case "pair" -> R.string.wear_pair_failed;
            case "inspect" -> R.string.wear_inspect_failed;
            default -> R.string.wear_connect_failed;
        };
        status(message, false, true);
        runOnUiThread(() -> binding.manualWearFields.setVisibility(View.VISIBLE));
    }

    private void status(int message, boolean busy, boolean enabled) {
        runOnUiThread(() -> {
            if (isFinishing() || isDestroyed()) return;
            binding.wearInstallStatus.setText(message);
            binding.wearInstallProgress.setVisibility(busy ? View.VISIBLE : View.GONE);
            binding.installWearNow.setEnabled(enabled);
            binding.forgetWearKey.setVisibility(keys.isRemembered() ? View.VISIBLE : View.GONE);
        });
    }

    private static int number(String value) {
        try { return Integer.parseInt(value.trim()); }
        catch (NumberFormatException invalid) { return 0; }
    }

    private record EndpointInput(String host, int pairPort, int connectPort, String code) {}
}
