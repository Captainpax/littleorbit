package com.littleorbit.data;

import android.content.Context;
import com.littleorbit.data.repository.ProfileRepository;
import com.littleorbit.data.repository.SmoochOutbox;
import dagger.hilt.android.qualifiers.ApplicationContext;
import javax.inject.Inject;
import javax.inject.Singleton;

/** Coordinates target selection with legacy purge and relationship generation barriers. */
@Singleton
public final class ManagedWatchCoordinator {
    private final Context context;
    private final ManagedWatchStore watches;
    private final RelationshipDisplayIdentity relationships;
    private final WearCachePublisher display;
    private final WearProfilePublisher profilePublisher;
    private final WearConfigurationPublisher configuration;
    private final ProfileRepository profiles;
    private final SmoochOutbox smooches;

    /** Creates the cross-store watch lifecycle boundary. */
    @Inject
    public ManagedWatchCoordinator(
            @ApplicationContext Context context,
            ManagedWatchStore watches,
            RelationshipDisplayIdentity relationships,
            WearCachePublisher display,
            WearProfilePublisher profilePublisher,
            WearConfigurationPublisher configuration,
            ProfileRepository profiles,
            SmoochOutbox smooches) {
        this.context = context;
        this.watches = watches;
        this.relationships = relationships;
        this.display = display;
        this.profilePublisher = profilePublisher;
        this.configuration = configuration;
        this.profiles = profiles;
        this.smooches = smooches;
    }

    /** Explicitly selects one watch after purging every legacy global payload. */
    public synchronized ManagedWatchStore.Snapshot select(String nodeId, String displayName) {
        ManagedWatchStore.Snapshot current = watches.read();
        if (!current.nodeId().equals(nodeId)) rotateRelationshipBarrier();
        ManagedWatchStore.Snapshot selected = watches.select(nodeId, displayName);
        configuration.publish();
        profilePublisher.publish(profiles.cached());
        DisplayCacheSyncWorker.enqueue(context);
        return selected;
    }

    /** Applies curated settings and republishes only affected target-scoped records. */
    public synchronized ManagedWatchStore.Snapshot updatePreferences(
            boolean photos,
            boolean countdownTitles,
            boolean smoochEnabled,
            boolean updateAlerts,
            String destination) {
        ManagedWatchStore.Snapshot updated = watches.updatePreferences(
                photos, countdownTitles, smoochEnabled, updateAlerts, destination);
        if (!smoochEnabled) smooches.clearWatchOrigin();
        configuration.publish();
        profilePublisher.publish(profiles.cached());
        DisplayCacheSyncWorker.enqueue(context);
        return updated;
    }

    /** Stops sync and leaves durable purge barriers before uninstall begins. */
    public synchronized ManagedWatchStore.Snapshot prepareRemoval() {
        ManagedWatchStore.Snapshot selected = watches.read();
        rotateRelationshipBarrier();
        smooches.clearWatchOrigin();
        ManagedWatchStore.Snapshot cleared = watches.clearTarget();
        display.clearTarget(selected.nodeId(), cleared.generation());
        return selected;
    }

    private void rotateRelationshipBarrier() {
        RelationshipDisplayIdentity.Snapshot active = relationships.read();
        if (!active.active() || active.relationshipId().isBlank()) return;
        RelationshipDisplayIdentity.Snapshot purge = relationships.purge();
        display.retireLegacy(purge);
        profilePublisher.clear(purge);
        relationships.activate(active.relationshipId());
    }
}
