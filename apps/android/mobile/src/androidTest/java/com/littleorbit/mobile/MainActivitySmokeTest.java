package com.littleorbit.mobile;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertTrue;

import android.os.SystemClock;
import android.view.View;
import androidx.core.view.GravityCompat;
import androidx.core.view.ViewCompat;
import androidx.drawerlayout.widget.DrawerLayout;
import androidx.lifecycle.Lifecycle;
import androidx.test.core.app.ActivityScenario;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import androidx.test.uiautomator.By;
import androidx.test.uiautomator.UiDevice;
import androidx.test.uiautomator.Until;
import org.junit.Test;
import org.junit.runner.RunWith;
import java.util.List;
import java.util.concurrent.atomic.AtomicReference;

/** Device smoke test for the signed-out native entry point. */
@RunWith(AndroidJUnit4.class)
public final class MainActivitySmokeTest {
    @Test
    public void signedOutHomeRendersItsPrimaryState() {
        try (ActivityScenario<MainActivity> scenario = ActivityScenario.launch(MainActivity.class)) {
            scenario.onActivity(activity -> {
                assertNotNull(activity.findViewById(R.id.quizButton));
                assertEquals(View.VISIBLE, activity.findViewById(R.id.signInButton).getVisibility());
                assertEquals(View.GONE, activity.findViewById(R.id.navPrivacy).getVisibility());
                assertEquals(View.GONE, activity.findViewById(R.id.navSettings).getVisibility());
                assertEquals(View.VISIBLE, activity.findViewById(R.id.navUpdates).getVisibility());
                assertEquals(View.GONE, activity.findViewById(R.id.openRightDrawer).getVisibility());
                assertTrue(activity.findViewById(R.id.navHome).isSelected());
                assertEquals(
                        "Current destination",
                        ViewCompat.getStateDescription(activity.findViewById(R.id.navHome)));
                assertEquals(
                        "Welcome to your orbit",
                        activity.<android.widget.TextView>findViewById(R.id.greetingText)
                                .getText()
                                .toString());
            });
        }
    }

    @Test
    public void publicFeatureActivitiesCreateTheirNativeViews() {
        List<Class<? extends android.app.Activity>> activities = List.of(
                SignInActivity.class,
                PrivacyActivity.class,
                SettingsActivity.class,
                AppUpdatesActivity.class,
                ProfileCropActivity.class);
        for (Class<? extends android.app.Activity> activityType : activities) {
            try (ActivityScenario<? extends android.app.Activity> scenario =
                    ActivityScenario.launch(activityType)) {
                assertTrue(
                        activityType.getSimpleName() + " was destroyed during launch",
                        scenario.getState() != Lifecycle.State.DESTROYED);
                scenario.onActivity(
                        activity -> assertNotNull(activity.getWindow().getDecorView()));
            }
        }
    }

    @Test
    public void signedOutProtectedActivityClosesBeforeShowingRelationshipContent() {
        try (ActivityScenario<PairingActivity> scenario =
                ActivityScenario.launch(PairingActivity.class)) {
            assertEquals(Lifecycle.State.DESTROYED, scenario.getState());
        }
    }

    @Test
    public void appUpdatesOwnsItsDestinationAndControls() {
        try (ActivityScenario<AppUpdatesActivity> scenario =
                ActivityScenario.launch(AppUpdatesActivity.class)) {
            scenario.onActivity(activity -> {
                assertNotNull(activity.findViewById(R.id.installedVersion));
                assertTrue(activity.findViewById(R.id.navUpdates).isSelected());
                assertFalse(activity.findViewById(R.id.navHome).isSelected());
            });
        }
    }

    @Test
    public void shellUsesOneResponsiveNavigationMode() {
        try (ActivityScenario<MainActivity> scenario = ActivityScenario.launch(MainActivity.class)) {
            InstrumentationRegistry.getInstrumentation().waitForIdleSync();
            scenario.onActivity(activity -> {
                View drawer = activity.findViewById(R.id.orbitDrawer);
                View leftNavigation = activity.findViewById(R.id.leftDrawer);
                View hamburger = activity.findViewById(R.id.openLeftDrawer);
                boolean persistent = activity.getResources().getBoolean(
                        R.bool.orbit_persistent_navigation);
                if (persistent) {
                    assertEquals(View.GONE, hamburger.getVisibility());
                    assertFalse(leftNavigation.getParent() instanceof DrawerLayout);
                    assertTrue(drawer.getSystemGestureExclusionRects().isEmpty());
                    int maximum = activity.getResources().getDimensionPixelSize(
                            R.dimen.orbit_content_max_width);
                    assertTrue(activity.findViewById(R.id.shellMain).getWidth() <= maximum);
                } else {
                    assertEquals(View.VISIBLE, hamburger.getVisibility());
                    assertTrue(leftNavigation.getParent() instanceof DrawerLayout);
                    assertFalse(drawer.getSystemGestureExclusionRects().isEmpty());
                }
            });
        }
    }

    @Test
    public void deliberateLeftEdgeSwipeOpensPhoneDrawer() throws Exception {
        try (ActivityScenario<MainActivity> scenario = ActivityScenario.launch(MainActivity.class)) {
            InstrumentationRegistry.getInstrumentation().waitForIdleSync();
            dismissAutoUpdatePrompt();
            SystemClock.sleep(500L);
            AtomicReference<int[]> size = new AtomicReference<>();
            scenario.onActivity(activity -> {
                if (activity.getResources().getBoolean(R.bool.orbit_persistent_navigation)) return;
                View drawer = activity.findViewById(R.id.orbitDrawer);
                int[] location = new int[2];
                drawer.getLocationOnScreen(location);
                size.set(new int[] {
                    location[0], location[1], drawer.getWidth(), drawer.getHeight()
                });
            });
            if (size.get() == null) return;
            swipeFromLeftEdge(size.get());
            SystemClock.sleep(500L);
            InstrumentationRegistry.getInstrumentation().waitForIdleSync();
            scenario.onActivity(activity -> {
                DrawerLayout drawer = activity.findViewById(R.id.orbitDrawer);
                String failure = "bounds=" + java.util.Arrays.toString(size.get())
                        + ", package=" + UiDevice.getInstance(
                                InstrumentationRegistry.getInstrumentation())
                                .getCurrentPackageName()
                        + ", visible=" + drawer.isDrawerVisible(GravityCompat.START)
                        + ", lock=" + drawer.getDrawerLockMode(GravityCompat.START);
                assertTrue(failure, drawer.isDrawerOpen(GravityCompat.START));
            });
        }
    }

    private static void swipeFromLeftEdge(int[] bounds) throws Exception {
        int startX = bounds[0] + 1;
        int y = bounds[1] + bounds[3] / 2;
        int endX = bounds[0] + Math.round(bounds[2] * 0.7f);
        UiDevice.getInstance(InstrumentationRegistry.getInstrumentation())
                .executeShellCommand("input swipe " + startX + " " + y + " "
                        + endX + " " + y + " 500");
    }

    private static void dismissAutoUpdatePrompt() {
        UiDevice device = UiDevice.getInstance(InstrumentationRegistry.getInstrumentation());
        String label = InstrumentationRegistry.getInstrumentation()
                .getTargetContext().getString(R.string.not_now);
        if (device.wait(Until.hasObject(By.text(label)), 1_000L)) {
            device.findObject(By.text(label)).click();
            device.waitForIdle();
        }
    }

    @Test
    public void cropScreenAlwaysExposesCancelAndApprovalActions() {
        try (ActivityScenario<ProfileCropActivity> scenario =
                ActivityScenario.launch(ProfileCropActivity.class)) {
            scenario.onActivity(activity -> {
                assertEquals(View.VISIBLE, activity.findViewById(R.id.cancelCrop).getVisibility());
                assertEquals(View.VISIBLE, activity.findViewById(R.id.usePhoto).getVisibility());
            });
        }
    }
}
