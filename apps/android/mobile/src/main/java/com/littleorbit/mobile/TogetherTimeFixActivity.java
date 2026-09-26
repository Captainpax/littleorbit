package com.littleorbit.mobile;

import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.provider.Settings;
import com.littleorbit.data.remote.TogetherTimeModels;
import com.littleorbit.data.repository.OrbitRepository;
import com.littleorbit.mobile.databinding.ActivityTogetherTimeFixBinding;
import dagger.hilt.android.AndroidEntryPoint;
import javax.inject.Inject;

/** Collection-health diagnostics that remain private until explicit opt-in. */
@AndroidEntryPoint
public final class TogetherTimeFixActivity extends InsetAwareActivity {
    @Inject OrbitRepository orbit;
    @Inject TogetherHealthReporter reporter;
    private ActivityTogetherTimeFixBinding binding;
    private boolean rendering;
    private int loadGeneration;

    @Override protected void onCreate(Bundle state) {
        super.onCreate(state);
        binding = ActivityTogetherTimeFixBinding.inflate(getLayoutInflater());
        setContentView(binding.getRoot());
        binding.shareDiagnostics.setChecked(reporter.enabled());
        binding.shareDiagnostics.setOnCheckedChangeListener((button, checked) -> {
            if (rendering) return;
            reporter.setEnabled(checked);
            binding.statusText.setText(checked
                    ? R.string.collection_health_shared
                    : R.string.collection_health_private);
            binding.getRoot().postDelayed(this::load, 500);
        });
        binding.locationSettings.setOnClickListener(view -> appSettings());
        binding.notificationSettings.setOnClickListener(view -> notificationSettings());
        binding.batterySettings.setOnClickListener(view ->
                startActivity(new Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS)));
    }

    @Override protected void onResume() {
        super.onResume();
        if (reporter.enabled()) reporter.publish();
        load();
    }

    @Override protected void onStop() {
        loadGeneration++;
        super.onStop();
    }

    private void load() {
        int generation = ++loadGeneration;
        reporter.snapshotAsync().thenAccept(local -> runOnUiThread(() -> {
            if (!canRender(generation)) return;
            binding.thisPhoneHealth.setText(format(getString(R.string.this_phone), local));
            loadPartner(generation);
        })).exceptionally(failure -> {
            runOnUiThread(() -> showFailure(generation));
            return null;
        });
    }

    private void loadPartner(int generation) {
        orbit.togetherDeviceHealth().thenAccept(value -> runOnUiThread(() -> {
            if (!canRender(generation)) return;
            if (value.partner.isEmpty()) {
                binding.partnerHealth.setText(R.string.partner_diagnostics_private);
            } else {
                binding.partnerHealth.setText(format(
                        getString(R.string.partner_phone), value.partner.get(0)));
            }
        })).exceptionally(failure -> {
            runOnUiThread(() -> showFailure(generation));
            return null;
        });
    }

    private boolean canRender(int generation) {
        return generation == loadGeneration && !isFinishing() && !isDestroyed();
    }

    private void showFailure(int generation) {
        if (canRender(generation)) binding.statusText.setText(R.string.request_failed);
    }

    private String format(String heading, TogetherTimeModels.DeviceHealthUpdate value) {
        return getString(R.string.device_health_detail,
                heading, value.deviceModel, value.batteryPercent,
                value.charging ? getString(R.string.charging) : getString(R.string.not_charging),
                value.networkTransport, value.backgroundLocation
                        ? getString(R.string.on) : getString(R.string.off),
                value.batteryUnrestricted ? getString(R.string.on) : getString(R.string.off),
                value.trackingNotification ? getString(R.string.on) : getString(R.string.off),
                value instanceof TogetherTimeModels.DeviceHealthView view
                        && view.lastLocationAt != null
                        ? view.lastLocationAt : getString(R.string.no_recent_check_in),
                value.uploadState, value.queueSize);
    }

    private void appSettings() {
        startActivity(new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
                Uri.parse("package:" + getPackageName())));
    }

    private void notificationSettings() {
        startActivity(new Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS)
                .putExtra(Settings.EXTRA_APP_PACKAGE, getPackageName()));
    }
}
