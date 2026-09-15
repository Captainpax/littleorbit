package com.littleorbit.mobile;

import android.content.Intent;
import android.graphics.Rect;
import android.net.Uri;
import android.view.Gravity;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.LinearLayout;
import android.widget.FrameLayout;
import androidx.annotation.LayoutRes;
import androidx.activity.OnBackPressedCallback;
import androidx.core.view.GravityCompat;
import androidx.core.view.ViewCompat;
import androidx.drawerlayout.widget.DrawerLayout;
import com.google.android.material.button.MaterialButton;
import com.littleorbit.data.repository.OrbitRepository;
import com.littleorbit.mobile.databinding.ActivityOrbitShellBinding;
import java.util.List;
import javax.inject.Inject;

/** Shared two-drawer shell for Little Orbit's top-level phone destinations. */
public abstract class OrbitShellActivity extends InsetAwareActivity {
    @Inject OrbitRepository shellOrbit;
    private ActivityOrbitShellBinding shell;
    private boolean installingShell;

    /** One concise action rendered in the current destination's right panel. */
    protected record ContextAction(String label, Runnable action) {}

    /** Identifies this screen for app-bar and contextual navigation state. */
    protected abstract OrbitDestination orbitDestination();

    /** Called immediately before the current destination's right panel becomes visible. */
    protected void onOrbitContextOpened() {}

    @Override
    protected void onResume() {
        super.onResume();
        // Sign-in returns to the already-created Home activity, so refresh access-sensitive
        // destinations every time the shell becomes visible.
        if (shell != null) renderSignedInNavigation();
    }

    @Override
    public final void setContentView(@LayoutRes int layoutResId) {
        setContentView(getLayoutInflater().inflate(layoutResId, null, false));
    }

    @Override
    public void setContentView(View view) {
        if (installingShell) {
            super.setContentView(view);
            return;
        }
        installShell(view, null);
    }

    @Override
    public final void setContentView(View view, ViewGroup.LayoutParams params) {
        installShell(view, params);
    }

    /** Replaces the right panel's action list while retaining destination guidance. */
    protected final void setOrbitContextActions(List<ContextAction> actions) {
        if (shell == null) return;
        shell.contextActions.removeAllViews();
        boolean available = actions != null && !actions.isEmpty();
        shell.openRightDrawer.setVisibility(available ? View.VISIBLE : View.GONE);
        if (!available) {
            shell.orbitDrawer.closeDrawer(GravityCompat.END);
            return;
        }
        for (ContextAction action : actions) {
            MaterialButton button = (MaterialButton) LayoutInflater.from(this)
                    .inflate(R.layout.item_orbit_context_action, shell.contextActions, false);
            button.setText(action.label());
            button.setOnClickListener(ignored -> {
                shell.orbitDrawer.closeDrawer(GravityCompat.END);
                action.action().run();
            });
            shell.contextActions.addView(button);
        }
    }

    private void installShell(View content, ViewGroup.LayoutParams contentParams) {
        installingShell = true;
        shell = ActivityOrbitShellBinding.inflate(getLayoutInflater());
        if (contentParams == null) shell.orbitContent.addView(content);
        else shell.orbitContent.addView(content, contentParams);
        super.setContentView(shell.getRoot());
        installingShell = false;
        configureChrome();
        OrbitMotion.reveal(content);
    }

    private void configureChrome() {
        OrbitDestination destination = orbitDestination();
        shell.shellTitle.setText(destination.title);
        shell.contextTitle.setText(destination.contextTitle);
        shell.contextDescription.setText(destination.contextDescription);
        ViewCompat.setAccessibilityPaneTitle(
                shell.leftDrawer, getString(R.string.navigation_pane_title));
        ViewCompat.setAccessibilityPaneTitle(
                shell.rightDrawer,
                getString(R.string.context_pane_title, getString(destination.title)));
        shell.openLeftDrawer.setOnClickListener(
                ignored -> shell.orbitDrawer.openDrawer(GravityCompat.START));
        shell.openRightDrawer.setOnClickListener(
                ignored -> {
                    onOrbitContextOpened();
                    shell.orbitDrawer.openDrawer(GravityCompat.END);
                });
        bindNavigation();
        renderSignedInNavigation();
        configureDrawerBehavior();
        bindBackNavigation();
    }

    private void configureDrawerBehavior() {
        // The context panel has a dedicated button so it cannot steal the system back edge.
        shell.orbitDrawer.setDrawerLockMode(
                DrawerLayout.LOCK_MODE_LOCKED_CLOSED, GravityCompat.END);
        if (hasPersistentNavigation()) {
            installPersistentNavigation();
        } else {
            shell.orbitDrawer.setDrawerLockMode(
                    DrawerLayout.LOCK_MODE_UNLOCKED, GravityCompat.START);
            installStartGestureExclusion();
        }
    }

    private void bindNavigation() {
        shell.navHome.setOnClickListener(ignored -> open(MainActivity.class));
        shell.navQuiz.setOnClickListener(ignored -> open(QuizActivity.class));
        shell.navSmooch.setOnClickListener(ignored -> open(SmoochActivity.class));
        shell.navSpace.setOnClickListener(ignored -> open(NotesActivity.class));
        shell.navCountdowns.setOnClickListener(ignored -> open(CountdownActivity.class));
        shell.navTogether.setOnClickListener(ignored -> open(TogetherTimeActivity.class));
        shell.navProfile.setOnClickListener(ignored -> open(ProfilePhotoActivity.class));
        shell.navSettings.setOnClickListener(ignored -> open(SettingsActivity.class));
        shell.navPrivacy.setOnClickListener(ignored -> open(PrivacyActivity.class));
        shell.navUpdates.setOnClickListener(ignored -> open(AppUpdatesActivity.class));
        shell.navSignIn.setOnClickListener(ignored -> open(SignInActivity.class));
        shell.navCreateAccount.setOnClickListener(ignored -> openWeb("/signup"));
        shell.navAbout.setOnClickListener(ignored -> openWeb("/"));
    }

    private void renderSignedInNavigation() {
        boolean signedIn = shellOrbit != null && shellOrbit.isSignedIn();
        OrbitNavigationState state = new OrbitNavigationState(orbitDestination(), signedIn);
        renderNavigationItem(shell.navHome, OrbitDestination.HOME, state);
        renderNavigationItem(shell.navQuiz, OrbitDestination.QUIZ, state);
        renderNavigationItem(shell.navSmooch, OrbitDestination.SMOOCH, state);
        renderNavigationItem(shell.navSpace, OrbitDestination.SPACE, state);
        renderNavigationItem(shell.navCountdowns, OrbitDestination.COUNTDOWNS, state);
        renderNavigationItem(shell.navTogether, OrbitDestination.TOGETHER, state);
        renderNavigationItem(shell.navProfile, OrbitDestination.PROFILE, state);
        renderNavigationItem(shell.navSettings, OrbitDestination.SETTINGS, state);
        renderNavigationItem(shell.navPrivacy, OrbitDestination.PRIVACY, state);
        renderNavigationItem(shell.navUpdates, OrbitDestination.UPDATES, state);
        shell.navSignIn.setVisibility(signedIn ? View.GONE : View.VISIBLE);
        shell.navCreateAccount.setVisibility(signedIn ? View.GONE : View.VISIBLE);
    }

    private void renderNavigationItem(
            MaterialButton button,
            OrbitDestination destination,
            OrbitNavigationState state) {
        button.setVisibility(state.isVisible(destination) ? View.VISIBLE : View.GONE);
        boolean selected = state.isSelected(destination);
        button.setSelected(selected);
        ViewCompat.setStateDescription(
                button, selected ? getString(R.string.current_destination) : null);
    }

    private void open(Class<?> activity) {
        if (activity == getClass()) {
            closeDrawers();
            return;
        }
        OrbitMotion.start(this, destinationIntent(activity));
        closeDrawers();
    }

    private Intent destinationIntent(Class<?> activity) {
        return new Intent(this, activity)
                .addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_SINGLE_TOP);
    }

    private void openWeb(String path) {
        OrbitMotion.start(this, new Intent(
                Intent.ACTION_VIEW, Uri.parse("https://lil-orb.pax-kun.com" + path)));
        closeDrawers();
    }

    private void closeDrawers() {
        shell.orbitDrawer.closeDrawer(GravityCompat.END);
        if (!hasPersistentNavigation()) shell.orbitDrawer.closeDrawer(GravityCompat.START);
    }

    private void bindBackNavigation() {
        getOnBackPressedDispatcher().addCallback(this, new OnBackPressedCallback(true) {
            @Override
            public void handleOnBackPressed() {
                if (!hasPersistentNavigation()
                        && shell.orbitDrawer.isDrawerOpen(GravityCompat.START)) {
                    shell.orbitDrawer.closeDrawer(GravityCompat.START);
                } else if (shell.orbitDrawer.isDrawerOpen(GravityCompat.END)) {
                    shell.orbitDrawer.closeDrawer(GravityCompat.END);
                } else {
                    setEnabled(false);
                    getOnBackPressedDispatcher().onBackPressed();
                }
            }
        });
    }

    private void installPersistentNavigation() {
        shell.orbitDrawer.removeView(shell.shellMain);
        shell.orbitDrawer.removeView(shell.leftDrawer);
        LinearLayout content = new LinearLayout(this);
        content.setOrientation(LinearLayout.HORIZONTAL);
        content.addView(shell.leftDrawer, new LinearLayout.LayoutParams(
                getResources().getDimensionPixelSize(R.dimen.orbit_navigation_rail_width),
                ViewGroup.LayoutParams.MATCH_PARENT));
        FrameLayout mainHost = new FrameLayout(this);
        mainHost.addView(shell.shellMain, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT,
                Gravity.CENTER));
        content.addView(mainHost, new LinearLayout.LayoutParams(
                0, ViewGroup.LayoutParams.MATCH_PARENT, 1));
        shell.orbitDrawer.addView(content, 0, new DrawerLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        mainHost.addOnLayoutChangeListener((view, left, top, right, bottom,
                oldLeft, oldTop, oldRight, oldBottom) -> boundMainContent(mainHost));
        ViewCompat.setSystemGestureExclusionRects(shell.orbitDrawer, List.of());
        shell.openLeftDrawer.setVisibility(View.GONE);
    }

    private void boundMainContent(FrameLayout host) {
        if (host.getWidth() <= 0) return;
        ViewGroup.LayoutParams current = shell.shellMain.getLayoutParams();
        int maximum = getResources().getDimensionPixelSize(R.dimen.orbit_content_max_width);
        int target = Math.min(host.getWidth(), maximum);
        if (current.width == target) return;
        FrameLayout.LayoutParams bounded = new FrameLayout.LayoutParams(
                target, ViewGroup.LayoutParams.MATCH_PARENT, Gravity.CENTER);
        shell.shellMain.setLayoutParams(bounded);
    }

    private void installStartGestureExclusion() {
        shell.orbitDrawer.addOnLayoutChangeListener((view, left, top, right, bottom,
                oldLeft, oldTop, oldRight, oldBottom) -> updateStartGestureExclusion());
        shell.orbitDrawer.post(this::updateStartGestureExclusion);
    }

    private void updateStartGestureExclusion() {
        int height = shell.orbitDrawer.getHeight();
        if (height <= 0) return;
        int edge = getResources().getDimensionPixelSize(R.dimen.orbit_drawer_edge_width);
        int exclusionHeight = Math.min(height, getResources().getDimensionPixelSize(
                R.dimen.orbit_gesture_exclusion_height));
        int top = Math.max(0, (height - exclusionHeight) / 2);
        boolean rtl = ViewCompat.getLayoutDirection(shell.orbitDrawer)
                == ViewCompat.LAYOUT_DIRECTION_RTL;
        Rect area = rtl
                ? new Rect(shell.orbitDrawer.getWidth() - edge, top,
                        shell.orbitDrawer.getWidth(), top + exclusionHeight)
                : new Rect(0, top, edge, top + exclusionHeight);
        ViewCompat.setSystemGestureExclusionRects(shell.orbitDrawer, List.of(area));
    }

    private boolean hasPersistentNavigation() {
        return getResources().getBoolean(R.bool.orbit_persistent_navigation);
    }

}
