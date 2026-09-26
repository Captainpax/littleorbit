package com.littleorbit.mobile;

import androidx.lifecycle.LiveData;
import androidx.lifecycle.MediatorLiveData;
import androidx.lifecycle.ViewModel;
import com.littleorbit.data.repository.DisplayCacheRepository;
import com.littleorbit.data.repository.OrbitRepository;
import dagger.hilt.android.lifecycle.HiltViewModel;
import java.time.Instant;
import javax.inject.Inject;

/** Maps repository data into one immutable render state. */
@HiltViewModel
public final class HomeViewModel extends ViewModel {
    private final MediatorLiveData<HomeScreenState> state = new MediatorLiveData<>();
    private final OrbitRepository orbit;
    private String quizPrompt = "Open today’s five questions";

    /** Starts observing the privacy-limited display cache. */
    @Inject
    public HomeViewModel(DisplayCacheRepository repository, OrbitRepository orbit) {
        this.orbit = orbit;
        state.setValue(HomeStateMapper.withoutCache(orbit.isSignedIn()));
        state.addSource(repository.observe(), cache -> {
            if (cache == null) {
                state.setValue(HomeStateMapper.withoutCache(orbit.isSignedIn()));
                return;
            }
            state.setValue(HomeStateMapper.fromCache(cache, orbit.isSignedIn(), Instant.now())
                    .withQuizPrompt(quizPrompt));
        });
    }

    /** Returns state for lifecycle-aware rendering. */
    public LiveData<HomeScreenState> state() { return state; }

    /** Refreshes compact server state while retaining cached content on failure. */
    public void refresh() {
        if (!orbit.isSignedIn()) {
            state.setValue(HomeScreenState.signedOut());
            return;
        }
        HomeScreenState current = state.getValue();
        if (current == null || !current.signedIn()) {
            state.setValue(HomeScreenState.signedInWithoutCache());
        }
        orbit.refreshHome().exceptionally(failure -> {
            HomeScreenState latest = state.getValue();
            state.postValue(HomeStateMapper.afterRefreshFailure(latest, orbit.isSignedIn()));
            return null;
        });
        refreshQuizPrompt();
    }

    private void refreshQuizPrompt() {
        orbit.quizToday().thenAccept(day -> {
            if (day.questions == null || day.questions.isEmpty()) return;
            quizPrompt = day.myFinished
                    ? (day.revealed ? "Your answers are ready together" : "Waiting for your partner")
                    : day.questions.get(0).prompt;
            HomeScreenState current = state.getValue();
            if (current != null) state.postValue(current.withQuizPrompt(quizPrompt));
        }).exceptionally(failure -> null);
    }
}
