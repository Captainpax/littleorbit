package com.littleorbit.mobile;

import android.app.Activity;
import android.content.Intent;
import android.view.View;

/** Shared five-destination phone navigation used by focused feature screens. */
public final class OrbitTabNavigation {
    private OrbitTabNavigation() {}

    /** Binds Home, Quiz, Smooch, Space, and More destinations in stable order. */
    public static void bind(
            Activity activity,
            View home,
            View quiz,
            View smooch,
            View space,
            View more) {
        home.setOnClickListener(view -> open(activity, MainActivity.class, false));
        quiz.setOnClickListener(view -> open(activity, QuizActivity.class, false));
        smooch.setOnClickListener(view -> open(activity, SmoochActivity.class, false));
        space.setOnClickListener(view -> open(activity, NotesActivity.class, false));
        more.setOnClickListener(view -> open(activity, MainActivity.class, true));
    }

    private static void open(
            Activity activity, Class<? extends Activity> destination, boolean showMore) {
        if (activity.getClass().equals(destination) && !showMore) return;
        Intent intent = new Intent(activity, destination);
        if (destination.equals(MainActivity.class)) {
            intent.addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_SINGLE_TOP);
            intent.putExtra(MainActivity.EXTRA_SHOW_MORE, showMore);
        }
        activity.startActivity(intent);
        if (!destination.equals(MainActivity.class)) activity.finish();
    }
}
