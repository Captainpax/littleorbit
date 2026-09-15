package com.littleorbit.mobile;

import com.littleorbit.data.remote.QuizApiModels;

/** Immutable presentation state for the focused daily quiz flow. */
public final class QuizScreenState {
    /** Mutually exclusive screen modes in render priority order. */
    public enum Mode { LOADING, EMPTY, REVEALED, WAITING, REVIEW, QUESTION }

    public final QuizApiModels.Day day;
    public final int questionIndex;
    public final boolean loading;
    public final boolean reviewing;
    public final String error;

    /** Creates one immutable state snapshot. */
    public QuizScreenState(
            QuizApiModels.Day day,
            int questionIndex,
            boolean loading,
            boolean reviewing,
            String error) {
        this.day = day;
        this.questionIndex = questionIndex;
        this.loading = loading;
        this.reviewing = reviewing;
        this.error = error;
    }

    /** Returns the initial loading state. */
    public static QuizScreenState loading() {
        return new QuizScreenState(null, 0, true, false, null);
    }

    /** Returns a copy with a different question index. */
    public QuizScreenState at(int index) {
        return new QuizScreenState(day, index, false, false, null);
    }

    /** Returns a copy showing or leaving the review page. */
    public QuizScreenState reviewing(boolean value) {
        return new QuizScreenState(day, questionIndex, false, value, null);
    }

    /** Returns whether all five private drafts are present. */
    public boolean allAnswered() {
        return day != null && day.questions.stream().allMatch(item -> item.myAnswer != null);
    }

    /** Resolves one deterministic presentation mode from the server and local edit state. */
    public Mode mode() {
        if (loading || day == null) return Mode.LOADING;
        if (day.questions.isEmpty()) return Mode.EMPTY;
        if (day.revealed) return Mode.REVEALED;
        if (day.myFinished) return Mode.WAITING;
        if (reviewing) return Mode.REVIEW;
        return Mode.QUESTION;
    }
}
