package com.littleorbit.data;

import android.content.Context;
import android.content.Intent;
import com.littleorbit.data.local.DisplayCacheDao;
import com.littleorbit.data.local.DisplayCacheEntity;
import com.littleorbit.data.remote.ApiModels;
import com.littleorbit.data.remote.CountdownApiModels;
import com.littleorbit.data.remote.LittleOrbitApi;
import com.littleorbit.data.remote.TogetherTimeModels;
import dagger.hilt.android.qualifiers.ApplicationContext;
import java.io.IOException;
import java.time.Instant;
import java.util.List;
import javax.inject.Inject;
import javax.inject.Singleton;
import retrofit2.Response;

/** Refreshes the privacy-minimal phone, widget, and Wear cache in one transaction boundary. */
@Singleton
public final class DisplayCacheSynchronizer {
    public static final String ACTION_CACHE_UPDATED = "com.littleorbit.action.DISPLAY_CACHE_UPDATED";
    private final Context context;
    private final LittleOrbitApi api;
    private final DisplayCacheDao cacheDao;
    private final WearCachePublisher wearPublisher;

    /** Creates the display synchronization boundary. */
    @Inject
    public DisplayCacheSynchronizer(
            @ApplicationContext Context context,
            LittleOrbitApi api,
            DisplayCacheDao cacheDao,
            WearCachePublisher wearPublisher) {
        this.context = context;
        this.api = api;
        this.cacheDao = cacheDao;
        this.wearPublisher = wearPublisher;
    }

    /** Loads current authorized state and publishes one internally consistent cache row. */
    public void refresh() throws SyncException {
        TogetherTimeModels.PairSummary summary;
        List<CountdownApiModels.Countdown> countdowns;
        try {
            summary = body(api.togetherSummaryV3().execute());
            countdowns = body(api.countdowns().execute());
        } catch (IOException failure) {
            throw new SyncException(failure);
        }
        CountdownApiModels.Countdown next = countdowns.stream()
                .filter(item -> Instant.parse(item.occursAt).isAfter(Instant.now()))
                .min((left, right) -> left.occursAt.compareTo(right.occursAt))
                .orElse(null);
        DisplayCacheEntity cache = new DisplayCacheEntity(
                "primary",
                Instant.parse(summary.pairedAt).atZone(java.time.ZoneOffset.UTC)
                        .toLocalDate().toEpochDay(),
                summary.nearbyEstimatedSeconds,
                instantMillis(summary.nearbyLastProcessedAt),
                next == null ? "No countdown yet" : next.title,
                next == null ? 0 : Instant.parse(next.occursAt).toEpochMilli(),
                Instant.now().toEpochMilli());
        cacheDao.replace(cache);
        wearPublisher.publish(cache);
        notifyWidget();
    }

    /** Clears all relationship display values from every local surface. */
    public void clear() {
        cacheDao.clear();
        wearPublisher.clear();
        notifyWidget();
    }

    private void notifyWidget() {
        Intent intent = new Intent(ACTION_CACHE_UPDATED).setPackage(context.getPackageName());
        context.sendBroadcast(intent);
    }

    private static long instantMillis(String value) {
        return value == null ? 0 : Instant.parse(value).toEpochMilli();
    }

    private static <T> T body(Response<T> response) throws SyncException {
        T result = response.body();
        if (!response.isSuccessful() || result == null) {
            throw new SyncException(response.code());
        }
        return result;
    }

    /** Status-only sync failure that never carries a response body or relationship content. */
    public static final class SyncException extends Exception {
        private final int statusCode;

        private SyncException(int statusCode) {
            super("Display cache sync failed with status " + statusCode);
            this.statusCode = statusCode;
        }

        /** Creates a retryable transport failure. */
        public SyncException(IOException cause) {
            super("Display cache sync could not reach the server", cause);
            this.statusCode = -1;
        }

        /** Returns the HTTP status, or -1 for a transport failure. */
        public int statusCode() {
            return statusCode;
        }
    }
}
