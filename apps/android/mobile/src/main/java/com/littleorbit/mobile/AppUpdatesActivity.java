package com.littleorbit.mobile;

import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;
import com.littleorbit.mobile.databinding.ActivityAppUpdatesBinding;
import dagger.hilt.android.AndroidEntryPoint;
import javax.inject.Inject;

/** Dedicated top-level destination for update discovery and verified installation. */
@AndroidEntryPoint
public final class AppUpdatesActivity extends OrbitShellActivity {
    /** Opens the update sheet after the latest release metadata is loaded. */
    public static final String EXTRA_SHOW_UPDATE = "show_update";
    @Inject AndroidUpdateCoordinator updates;
    private UpdateUiController updateUi;

    private final ActivityResultLauncher<Intent> installPermission = registerForActivityResult(
            new ActivityResultContracts.StartActivityForResult(),
            ignored -> updateUi.resumeInstallAfterPermission());

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        ActivityAppUpdatesBinding binding = ActivityAppUpdatesBinding.inflate(getLayoutInflater());
        setContentView(binding.getRoot());
        binding.installedVersion.setText(getString(
                R.string.update_version, BuildConfig.VERSION_NAME));
        binding.manualDownload.setOnClickListener(ignored -> openDownloadPage());
        updateUi = new UpdateUiController(this, updates, installPermission, false);
        updateUi.bindPreferences(
                binding.autoUpdateDetection,
                binding.lastUpdateCheck,
                binding.checkForUpdates);
        if (getIntent().getBooleanExtra(EXTRA_SHOW_UPDATE, false)) updateUi.requestSheet();
    }

    @Override
    protected void onResume() {
        super.onResume();
        updateUi.resume();
    }

    @Override
    protected void onPause() {
        updateUi.pause();
        super.onPause();
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        if (intent.getBooleanExtra(EXTRA_SHOW_UPDATE, false)) {
            updateUi.requestSheet();
            updateUi.resume();
        }
    }

    @Override
    protected OrbitDestination orbitDestination() {
        return OrbitDestination.UPDATES;
    }

    private void openDownloadPage() {
        startActivity(new Intent(
                Intent.ACTION_VIEW, Uri.parse("https://lil-orb.pax-kun.com/download")));
    }
}
