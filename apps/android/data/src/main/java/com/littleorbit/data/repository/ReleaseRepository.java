package com.littleorbit.data.repository;

import com.littleorbit.domain.ReleaseUpdate;
import java.util.Optional;
import java.util.concurrent.CompletableFuture;

/** Public release-discovery boundary with a non-sensitive offline cache. */
public interface ReleaseRepository {
    /** Fetches and validates current metadata, replacing the cached release atomically. */
    CompletableFuture<ReleaseUpdate> refresh();

    /** Returns the last successfully validated response, if one exists. */
    Optional<ReleaseUpdate> cached();

    /** Returns the last successful network-check epoch milliseconds. */
    long lastCheckedAtMillis();

    /** Records a bounded dismissal for one optional release. */
    void defer(String releaseId, long untilEpochMillis);

    /** Returns whether the exact optional release is still deferred. */
    boolean isDeferred(String releaseId, long nowEpochMillis);
}
