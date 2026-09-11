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
            state.setValue(HomeStateMapper.fromCache(cache, orbit.isSignedIn(), Instant.now()));
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
            if (latest == null || !latest.signedIn()) {
                state.postValue(HomeScreenState.signedInWithoutCache());
            }
            return null;
        });
    }
}
