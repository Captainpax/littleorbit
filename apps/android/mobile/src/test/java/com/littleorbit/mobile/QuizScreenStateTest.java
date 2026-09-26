package com.littleorbit.mobile;

import static org.junit.Assert.assertEquals;

import com.littleorbit.data.remote.QuizApiModels;
import java.util.List;
import java.util.Map;
import org.junit.Test;

/** Locks the render priority used after both partners finish a quiz. */
public final class QuizScreenStateTest {
    @Test
    public void revealedDayAlwaysUsesCompletionMode() {
        QuizScreenState state = state(day(true, true), true);
        assertEquals(QuizScreenState.Mode.REVEALED, state.mode());
    }

    @Test
    public void finishedDayWaitsWhenRevealIsPending() {
        assertEquals(QuizScreenState.Mode.WAITING, state(day(true, false), true).mode());
    }

    @Test
    public void localReviewPrecedesQuestionEditing() {
        assertEquals(QuizScreenState.Mode.REVIEW, state(day(false, false), true).mode());
        assertEquals(QuizScreenState.Mode.QUESTION, state(day(false, false), false).mode());
    }

    @Test
    public void generatedDayWithoutQuestionsUsesRecoverableEmptyMode() {
        QuizApiModels.Day empty = new QuizApiModels.Day(
                "2026-09-12", "test", 1, false, false, false, false, List.of());

        assertEquals(QuizScreenState.Mode.EMPTY, state(empty, false).mode());
    }

    private static QuizScreenState state(QuizApiModels.Day day, boolean reviewing) {
        return new QuizScreenState(day, 0, false, reviewing, null);
    }

    private static QuizApiModels.Day day(boolean myFinished, boolean revealed) {
        return new QuizApiModels.Day(
                "2026-09-12", "test", 1, myFinished, revealed, revealed, !revealed,
                List.of(question()));
    }

    private static QuizApiModels.Question question() {
        return new QuizApiModels.Question(
                "question-id", 0, 1, "free_text", "Prompt", "everyday", false,
                List.of(), null, null, Map.of("text", "Answer"), 1, null);
    }
}
