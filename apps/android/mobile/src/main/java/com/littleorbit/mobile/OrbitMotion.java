package com.littleorbit.mobile;

import android.animation.ValueAnimator;
import android.app.Activity;
import android.content.Intent;
import android.view.View;

/** Small, reduced-motion-aware transitions shared by the cosmic phone UI. */
final class OrbitMotion {
    private static final long REVEAL_MILLIS = 180L;

    private OrbitMotion() {}

    /** Reveals changed content without hiding it when system animation is disabled. */
    static void reveal(View view) {
        if (!ValueAnimator.areAnimatorsEnabled()) {
            view.setAlpha(1f);
            view.setTranslationY(0f);
            return;
        }
        view.animate().cancel();
        view.setAlpha(0f);
        view.setTranslationY(dp(view, 8));
        view.animate().alpha(1f).translationY(0f).setDuration(REVEAL_MILLIS).start();
    }

    /** Starts a destination with the same short fade used throughout the app shell. */
    static void start(Activity activity, Intent intent) {
        activity.startActivity(intent);
        if (ValueAnimator.areAnimatorsEnabled()) {
            activity.overridePendingTransition(R.anim.orbit_fade_in, R.anim.orbit_fade_out);
        }
    }

    private static float dp(View view, int value) {
        return value * view.getResources().getDisplayMetrics().density;
    }
}
