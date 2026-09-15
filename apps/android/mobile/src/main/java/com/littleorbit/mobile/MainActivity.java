package com.littleorbit.mobile;

import android.appwidget.AppWidgetManager;
import android.content.ComponentName;
import android.content.Intent;
import android.graphics.BitmapFactory;
import android.net.Uri;
import android.os.Bundle;
import android.view.View;
import android.widget.Toast;
import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;
import androidx.appcompat.app.AppCompatActivity;
import androidx.lifecycle.ViewModelProvider;
import com.littleorbit.data.repository.OrbitRepository;
import com.littleorbit.data.repository.ProfileRepository;
import com.littleorbit.mobile.databinding.ActivityMainBinding;
import com.littleorbit.widget.LittleOrbitWidgetProvider;
import dagger.hilt.android.AndroidEntryPoint;
import java.util.Locale;
import javax.inject.Inject;

/** Home destination for the signed-out welcome and current relationship summary. */
@AndroidEntryPoint
public final class MainActivity extends OrbitShellActivity {
    private ActivityMainBinding binding;
    private HomeViewModel model;
    private UpdateUiController updateUi;
    private SetupChecklistController setupChecklist;
    private String setupHomeKey;
    private String setupCoupleId = "unpaired";
    private boolean setupPairingReady;
    private boolean setupNotificationsReady;
    private boolean setupNearbyReady;
    private boolean setupWidgetReady;
    private boolean setupWatchReady;
    private int setupGeneration;
    private HomeActivityPanel activityPanel;
    @Inject OrbitRepository orbit;
    @Inject ProfileRepository profiles;
    @Inject AndroidUpdateCoordinator updates;
    @Inject WearStatusChecker wearStatus;

    private final ActivityResultLauncher<Intent> installPermission = registerForActivityResult(
            new ActivityResultContracts.StartActivityForResult(),
            ignored -> updateUi.resumeInstallAfterPermission());

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        binding = ActivityMainBinding.inflate(getLayoutInflater());
        setContentView(binding.getRoot());
        model = new ViewModelProvider(this).get(HomeViewModel.class);
        setupChecklist = new SetupChecklistController(this);
        activityPanel = new HomeActivityPanel(
                this, orbit, this::setOrbitContextActions, this::open);
        model.state().observe(this, this::renderHome);
        bindHomeActions();
        updateUi = new UpdateUiController(this, updates, installPermission, true);
        updateUi.bindBanner(binding.updateBanner, binding.updateBannerText);
        updateUi.promptForAutomaticDetection();
    }

    @Override
    protected void onResume() {
        super.onResume();
        setupHomeKey = null;
        HomeScreenState current = model.state().getValue();
        if (current != null) refreshSetupIfNeeded(current);
        reconcileQuizNotifications();
        model.refresh();
        if (orbit.isSignedIn()) {
            refreshProfile();
            activityPanel.refresh();
        } else {
            setOrbitContextActions(java.util.List.of());
        }
        updateUi.resume();
    }

    @Override
    protected void onPause() {
        updateUi.pause();
        super.onPause();
    }

    @Override
    protected OrbitDestination orbitDestination() {
        return OrbitDestination.HOME;
    }

    @Override
    protected void onOrbitContextOpened() {
        activityPanel.markVisibleSeen();
    }

    private void bindHomeActions() {
        binding.createAccountButton.setOnClickListener(ignored -> openWeb("/signup"));
        binding.signInButton.setOnClickListener(ignored -> open(SignInActivity.class));
        binding.pairingButton.setOnClickListener(ignored -> open(PairingActivity.class));
        binding.quizButton.setOnClickListener(ignored -> open(QuizActivity.class));
        binding.countdownsButton.setOnClickListener(ignored -> open(CountdownActivity.class));
        binding.smoochSpark.setOnClickListener(ignored -> open(SmoochActivity.class));
        binding.notesButton.setOnClickListener(ignored -> open(NotesActivity.class));
        binding.togetherButton.setOnClickListener(ignored -> open(TogetherTimeActivity.class));
        binding.myPlanet.setOnClickListener(ignored -> {
            if (orbit.isSignedIn()) open(ProfilePhotoActivity.class);
            else open(SignInActivity.class);
        });
    }

    private void renderHome(HomeScreenState state) {
        binding.greetingText.setText(state.greeting());
        binding.togetherText.setText(state.togetherTime());
        binding.nearbyText.setText(state.nearbyTime());
        binding.countdownText.setText(state.countdown());
        binding.quizPromptText.setText(state.quizPrompt());
        binding.statusText.setText(state.freshness());
        binding.partnerPlanet.setText(
                state.connected() ? R.string.rc14_partner_initial : R.string.rc14_unknown_initial);
        binding.sharedContent.setVisibility(state.connected() ? View.VISIBLE : View.GONE);
        binding.memberActions.setVisibility(
                state.signedIn() && !state.connected() ? View.VISIBLE : View.GONE);
        binding.guestActions.setVisibility(state.signedIn() ? View.GONE : View.VISIBLE);
        binding.smoochSpark.setVisibility(state.connected() ? View.VISIBLE : View.GONE);
        binding.myPlanet.setContentDescription(getString(
                state.signedIn() ? R.string.edit_profile_photo : R.string.sign_in));
        refreshSetupIfNeeded(state);
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
                profile.myName(), profile.myPhoto(), getString(R.string.rc14_your_initial));
        renderPlanet(
                binding.partnerPlanetImage, binding.partnerPlanet,
                profile.partnerName(), profile.partnerPhoto(),
                getString(R.string.rc14_unknown_initial));
        binding.partnerPlanetImage.setContentDescription(
                profile.partnerName() == null
                        ? getString(R.string.partner_planet)
                        : profile.partnerName());
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
                    ? defaultInitial : name.substring(0, 1).toUpperCase(Locale.getDefault()));
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

    private void refreshSetupIfNeeded(HomeScreenState home) {
        String homeKey = home.signedIn() + ":" + home.connected();
        if (homeKey.equals(setupHomeKey)) return;
        setupHomeKey = homeKey;
        int generation = ++setupGeneration;
        if (!home.signedIn()) {
            binding.setupChecklist.setVisibility(View.GONE);
            return;
        }
        setupCoupleId = home.connected() ? "paired" : "unpaired";
        setupPairingReady = home.connected();
        setupNotificationsReady = PermissionChecks.notificationsGranted(this);
        setupNearbyReady = false;
        setupWidgetReady = hasHomeWidget();
        setupWatchReady = false;
        renderSetupChecklist();
        refreshWatchSetup(generation);
        if (home.connected()) refreshCoupleSetup(generation);
    }

    private void refreshCoupleSetup(int generation) {
        orbit.preferences().thenAccept(preferences -> runOnUiThread(() -> {
            if (!isCurrentSetup(generation)) return;
            setupCoupleId = preferences.coupleId;
            setupNearbyReady = PermissionChecks.fineLocationGranted(this)
                    && PermissionChecks.backgroundLocationGranted(this)
                    && preferences.locationByBoth;
            renderSetupChecklist();
        })).exceptionally(failure -> null);
    }

    private void refreshWatchSetup(int generation) {
        wearStatus.check().thenAccept(state -> runOnUiThread(() -> {
            if (!isCurrentSetup(generation)) return;
            setupWatchReady = state == WearStatusChecker.State.APP_CONNECTED;
            renderSetupChecklist();
        }));
    }

    private boolean isCurrentSetup(int generation) {
        return generation == setupGeneration && !isFinishing() && !isDestroyed();
    }

    private void renderSetupChecklist() {
        binding.setupChecklist.setVisibility(View.VISIBLE);
        SetupChecklistState state = setupChecklist.state(
                setupCoupleId,
                setupPairingReady,
                setupNotificationsReady,
                setupNearbyReady,
                setupWidgetReady,
                setupWatchReady);
        binding.setupChecklist.bind(state, new SetupChecklistView.Listener() {
            @Override public void onPairing() { open(PairingActivity.class); }
            @Override public void onNotifications() { open(DeviceSetupActivity.class); }
            @Override public void onNearbyTime() { open(DeviceSetupActivity.class); }
            @Override public void onWidget() { requestHomeWidget(); }
            @Override public void onWatch() { open(WearInstallerActivity.class); }
            @Override public void onCollapsedChanged(boolean collapsed) {
                setupChecklist.setCollapsed(setupCoupleId, collapsed);
                renderSetupChecklist();
            }
        });
    }

    private boolean hasHomeWidget() {
        AppWidgetManager manager = AppWidgetManager.getInstance(this);
        ComponentName provider = new ComponentName(this, LittleOrbitWidgetProvider.class);
        return manager.getAppWidgetIds(provider).length > 0;
    }

    private void requestHomeWidget() {
        AppWidgetManager manager = AppWidgetManager.getInstance(this);
        ComponentName provider = new ComponentName(this, LittleOrbitWidgetProvider.class);
        boolean opened = manager.isRequestPinAppWidgetSupported()
                && manager.requestPinAppWidget(provider, null, null);
        Toast.makeText(
                this,
                opened ? R.string.rc14_widget_pin_opened : R.string.rc14_widget_pin_unavailable,
                Toast.LENGTH_LONG).show();
    }

    private void openWeb(String path) {
        startActivity(new Intent(
                Intent.ACTION_VIEW, Uri.parse("https://lil-orb.pax-kun.com" + path)));
    }

    private void open(Class<? extends AppCompatActivity> activity) {
        startActivity(new Intent(this, activity));
    }
}
