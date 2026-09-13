package com.littleorbit.mobile;

import android.content.Intent;
import android.net.Uri;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.LinearLayout;
import androidx.annotation.LayoutRes;
import androidx.activity.OnBackPressedCallback;
import androidx.core.view.GravityCompat;
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
        for (ContextAction action : actions) {
            MaterialButton button = new MaterialButton(this, null);
            button.setText(action.label());
            button.setGravity(Gravity.START | Gravity.CENTER_VERTICAL);
            button.setOnClickListener(ignored -> {
                shell.orbitDrawer.closeDrawer(GravityCompat.END);
                action.action().run();
            });
            shell.contextActions.addView(button, new ViewGroup.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT, dp(52)));
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
    }

    private void configureChrome() {
        OrbitDestination destination = orbitDestination();
        shell.shellTitle.setText(destination.title);
        shell.contextTitle.setText(destination.contextTitle);
        shell.contextDescription.setText(destination.contextDescription);
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
        if (!hasPersistentNavigation()) return;
        installPersistentNavigation();
    }

    private void bindNavigation() {
        shell.navHome.setOnClickListener(ignored -> open(MainActivity.class));
        shell.navQuiz.setOnClickListener(ignored -> open(QuizActivity.class));
        shell.navSmooch.setOnClickListener(ignored -> open(SmoochActivity.class));
        shell.navSpace.setOnClickListener(ignored -> open(NotesActivity.class));
        shell.navCountdowns.setOnClickListener(ignored -> open(CountdownActivity.class));
        shell.navTogether.setOnClickListener(ignored -> open(TogetherTimeActivity.class));
        shell.navProfile.setOnClickListener(ignored -> open(ProfilePhotoActivity.class));
        shell.navSettings.setOnClickListener(ignored -> openMainSection(false));
        shell.navPrivacy.setOnClickListener(ignored -> open(PrivacyActivity.class));
        shell.navUpdates.setOnClickListener(ignored -> openMainSection(true));
        shell.navSignIn.setOnClickListener(ignored -> open(SignInActivity.class));
        shell.navCreateAccount.setOnClickListener(ignored -> openWeb("/signup"));
        shell.navAbout.setOnClickListener(ignored -> openWeb("/"));
    }

    private void renderSignedInNavigation() {
        boolean signedIn = shellOrbit != null && shellOrbit.isSignedIn();
        int memberVisibility = signedIn ? View.VISIBLE : View.GONE;
        shell.navQuiz.setVisibility(memberVisibility);
        shell.navSmooch.setVisibility(memberVisibility);
        shell.navSpace.setVisibility(memberVisibility);
        shell.navCountdowns.setVisibility(memberVisibility);
        shell.navTogether.setVisibility(memberVisibility);
        shell.navProfile.setVisibility(memberVisibility);
        shell.navSettings.setVisibility(memberVisibility);
        shell.navSignIn.setVisibility(signedIn ? View.GONE : View.VISIBLE);
        shell.navCreateAccount.setVisibility(signedIn ? View.GONE : View.VISIBLE);
    }

    private void openMainSection(boolean updates) {
        Intent intent = destinationIntent(MainActivity.class)
                .putExtra(MainActivity.EXTRA_SHOW_MORE, true);
        if (updates) intent.putExtra("show_updates", true);
        startActivity(intent);
        closeDrawers();
    }

    private void open(Class<?> activity) {
        if (activity == getClass()) {
            closeDrawers();
            return;
        }
        startActivity(destinationIntent(activity));
        closeDrawers();
    }

    private Intent destinationIntent(Class<?> activity) {
        return new Intent(this, activity)
                .addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_SINGLE_TOP);
    }

    private void openWeb(String path) {
        startActivity(new Intent(
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
                dp(216), ViewGroup.LayoutParams.MATCH_PARENT));
        content.addView(shell.shellMain, new LinearLayout.LayoutParams(
                0, ViewGroup.LayoutParams.MATCH_PARENT, 1));
        shell.orbitDrawer.addView(content, 0, new DrawerLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        shell.openLeftDrawer.setVisibility(View.GONE);
    }

    private boolean hasPersistentNavigation() {
        return getResources().getBoolean(R.bool.orbit_persistent_navigation);
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }
}
