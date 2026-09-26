package com.littleorbit.mobile;

import androidx.annotation.StringRes;

/** Stable top-level destinations shared by the two app drawers. */
public enum OrbitDestination {
    HOME(R.string.home, R.string.context_home_title, R.string.context_home_description),
    QUIZ(R.string.quiz, R.string.context_quiz_title, R.string.context_quiz_description),
    SMOOCH(R.string.smooches, R.string.context_smooch_title, R.string.context_smooch_description),
    SPACE(R.string.our_space, R.string.context_space_title, R.string.context_space_description),
    COUNTDOWNS(
            R.string.countdowns,
            R.string.context_countdowns_title,
            R.string.context_countdowns_description),
    TOGETHER(
            R.string.together_details,
            R.string.context_together_title,
            R.string.context_together_description),
    PROFILE(
            R.string.profile_photo,
            R.string.context_profile_title,
            R.string.context_profile_description),
    SETTINGS(
            R.string.settings,
            R.string.context_settings_title,
            R.string.context_settings_description),
    PRIVACY(
            R.string.privacy_controls,
            R.string.context_privacy_title,
            R.string.context_privacy_description),
    ARCHIVES(
            R.string.archive_title,
            R.string.archive_context_title,
            R.string.archive_context_description),
    UPDATES(
            R.string.app_updates,
            R.string.app_updates,
            R.string.context_settings_description);

    @StringRes public final int title;
    @StringRes public final int contextTitle;
    @StringRes public final int contextDescription;

    OrbitDestination(
            @StringRes int title,
            @StringRes int contextTitle,
            @StringRes int contextDescription) {
        this.title = title;
        this.contextTitle = contextTitle;
        this.contextDescription = contextDescription;
    }
}
