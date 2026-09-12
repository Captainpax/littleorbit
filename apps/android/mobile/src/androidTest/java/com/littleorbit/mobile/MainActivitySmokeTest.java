package com.littleorbit.mobile;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNotNull;

import android.view.View;
import androidx.test.core.app.ActivityScenario;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import org.junit.Test;
import org.junit.runner.RunWith;
import java.util.List;

/** Device smoke test for the signed-out native entry point. */
@RunWith(AndroidJUnit4.class)
public final class MainActivitySmokeTest {
    @Test
    public void signedOutHomeRendersItsPrimaryState() {
        try (ActivityScenario<MainActivity> scenario = ActivityScenario.launch(MainActivity.class)) {
            scenario.onActivity(activity -> {
                assertNotNull(activity.findViewById(R.id.quizButton));
                assertEquals(View.GONE, activity.findViewById(R.id.signOutButton).getVisibility());
                assertEquals(View.VISIBLE, activity.findViewById(R.id.signInButton).getVisibility());
                assertEquals(
                        "Welcome to your orbit",
                        activity.<android.widget.TextView>findViewById(R.id.greetingText)
                                .getText()
                                .toString());
            });
        }
    }

    @Test
    public void featureActivitiesCreateTheirNativeViews() {
        List<Class<? extends android.app.Activity>> activities = List.of(
                SignInActivity.class,
                PairingActivity.class,
                QuizActivity.class,
                CountdownActivity.class,
                NotesActivity.class,
                PrivacyActivity.class,
                ArchivesActivity.class,
                TogetherTimeActivity.class,
                ProfileCropActivity.class);
        for (Class<? extends android.app.Activity> activityType : activities) {
            try (ActivityScenario<? extends android.app.Activity> scenario =
                    ActivityScenario.launch(activityType)) {
                scenario.onActivity(
                        activity -> assertNotNull(activity.getWindow().getDecorView()));
            }
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
