package com.littleorbit.mobile;

import androidx.lifecycle.LiveData;
import androidx.lifecycle.MediatorLiveData;
import androidx.lifecycle.ViewModel;
import com.littleorbit.data.repository.DisplayCacheRepository;
import com.littleorbit.data.repository.OrbitRepository;
import dagger.hilt.android.lifecycle.HiltViewModel;
import java.time.Duration;
import java.time.Instant;
import javax.inject.Inject;

/** Maps repository data into one immutable render state. */
@HiltViewModel
public final class HomeViewModel extends ViewModel {
    private final MediatorLiveData<HomeScreenState> state = new MediatorLiveData<>();
    private final OrbitRepository orbit;

    /** Starts observing the privacy-limited display cache. */
    @Inject
    public HomeViewModel(DisplayCacheRepository repository, OrbitRepository orbit) {
        this.orbit = orbit;
        state.setValue(HomeScreenState.signedOut());
        state.addSource(repository.observe(), cache -> {
            if (cache == null) {
                state.setValue(HomeScreenState.signedOut());
                return;
            }
            Instant updatedAt = Instant.ofEpochMilli(cache.updatedAtEpochMillis);
            boolean stale = updatedAt.plus(Duration.ofHours(6)).isBefore(Instant.now());
            state.setValue(new HomeScreenState(
                    "Your little orbit",
                    Duration.ofSeconds(cache.togetherSeconds).toDays() + " days together",
                    cache.nextCountdownTitle,
                    stale ? "Estimate may be stale" : "Updated recently",
                    orbit.isSignedIn()));
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
        orbit.refreshHome().exceptionally(failure -> {
            if (state.getValue() == null) {
                state.postValue(HomeScreenState.syncUnavailable());
            }
            return null;
        });
    }
}
