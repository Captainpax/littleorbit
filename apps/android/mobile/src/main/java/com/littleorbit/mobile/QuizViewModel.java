package com.littleorbit.mobile;

import androidx.lifecycle.LiveData;
import androidx.lifecycle.MutableLiveData;
import androidx.lifecycle.ViewModel;
import com.littleorbit.data.remote.QuizApiModels;
import com.littleorbit.data.repository.OrbitRepository;
import dagger.hilt.android.lifecycle.HiltViewModel;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import javax.inject.Inject;

/** Owns daily quiz navigation and all asynchronous mutations. */
@HiltViewModel
public final class QuizViewModel extends ViewModel {
    private final OrbitRepository orbit;
    private final MutableLiveData<QuizScreenState> state =
            new MutableLiveData<>(QuizScreenState.loading());

    /** Creates an injected quiz state owner. */
    @Inject
    public QuizViewModel(OrbitRepository orbit) {
        this.orbit = orbit;
    }

    /** Exposes immutable screen state. */
    public LiveData<QuizScreenState> state() {
        return state;
    }

    /** Loads today or one explicit history date. */
    public void load(String quizDate) {
        state.setValue(QuizScreenState.loading());
        CompletableFuture<QuizApiModels.Day> request =
                quizDate == null ? orbit.quizToday() : orbit.quizDay(quizDate);
        observe(request, 0, false);
    }

    /** Moves to the previous question. */
    public void previous() {
        QuizScreenState current = state.getValue();
        if (current != null && current.day != null) {
            state.setValue(current.at(Math.max(0, current.questionIndex - 1)));
        }
    }

    /** Moves to the next question or review screen. */
    public void next() {
        QuizScreenState current = state.getValue();
        if (current == null || current.day == null) {
            return;
        }
        if (current.questionIndex < current.day.questions.size() - 1) {
            state.setValue(current.at(current.questionIndex + 1));
        } else if (current.allAnswered()) {
            state.setValue(current.reviewing(true));
        }
    }

    /** Opens the final review after all five drafts exist. */
    public void review() {
        QuizScreenState current = state.getValue();
        if (current != null && current.allAnswered()) {
            state.setValue(current.reviewing(true));
        }
    }

    /** Leaves review and returns to an answer. */
    public void editQuestion(int index) {
        QuizScreenState current = state.getValue();
        if (current != null && current.day != null) {
            state.setValue(current.at(index));
        }
    }

    /** Saves the current answer as a revisioned private draft. */
    public void save(Map<String, Object> answer) {
        QuizScreenState current = state.getValue();
        if (current == null || current.day == null) {
            return;
        }
        QuizApiModels.Question question = current.day.questions.get(current.questionIndex);
        QuizApiModels.DraftMutation mutation = new QuizApiModels.DraftMutation(
                UUID.randomUUID().toString(), question.myAnswerRevision, answer);
        state.setValue(new QuizScreenState(
                current.day, current.questionIndex, true, false, null));
        orbit.saveQuizDraft(current.day.quizDate, question.id, mutation)
                .whenComplete((day, failure) -> {
                    if (failure != null) {
                        state.postValue(error(current, failure));
                    } else {
                        int next = Math.min(current.questionIndex + 1, day.questions.size() - 1);
                        boolean review = next == current.questionIndex
                                && day.questions.stream().allMatch(item -> item.myAnswer != null);
                        state.postValue(new QuizScreenState(day, next, false, review, null));
                    }
                });
    }

    /** Finishes the reviewed set. */
    public void finish() {
        mutateDay(false);
    }

    /** Reopens the caller's set while reveal is still pending. */
    public void reopen() {
        mutateDay(true);
    }

    /** Hides the current question and reloads its safe replacement. */
    public void report(String reasonCode, String details) {
        QuizScreenState current = state.getValue();
        if (current == null || current.day == null) {
            return;
        }
        String questionId = current.day.questions.get(current.questionIndex).id;
        state.setValue(new QuizScreenState(
                current.day, current.questionIndex, true, false, null));
        orbit.reportQuizQuestion(questionId, new QuizApiModels.ReportMutation(reasonCode, details))
                .thenCompose(ignored -> orbit.quizDay(current.day.quizDate))
                .whenComplete((day, failure) -> state.postValue(
                        failure == null
                                ? new QuizScreenState(day, current.questionIndex, false, false, null)
                                : error(current, failure)));
    }

    private void mutateDay(boolean reopen) {
        QuizScreenState current = state.getValue();
        if (current == null || current.day == null) {
            return;
        }
        QuizApiModels.DayMutation mutation = new QuizApiModels.DayMutation(
                UUID.randomUUID().toString(), current.day.revision);
        CompletableFuture<QuizApiModels.Day> request = reopen
                ? orbit.reopenQuiz(current.day.quizDate, mutation)
                : orbit.finishQuiz(current.day.quizDate, mutation);
        state.setValue(new QuizScreenState(
                current.day, current.questionIndex, true, current.reviewing, null));
        observe(request, current.questionIndex, false);
    }

    private void observe(
            CompletableFuture<QuizApiModels.Day> request, int index, boolean reviewing) {
        request.whenComplete((day, failure) -> {
            if (failure != null) {
                QuizScreenState current = state.getValue();
                state.postValue(error(current, failure));
            } else {
                state.postValue(new QuizScreenState(day, index, false, reviewing, null));
            }
        });
    }

    private static QuizScreenState error(QuizScreenState current, Throwable failure) {
        QuizApiModels.Day day = current == null ? null : current.day;
        int index = current == null ? 0 : current.questionIndex;
        return new QuizScreenState(
                day, index, false, false, "Little Orbit could not sync this quiz. Try again.");
    }
}
