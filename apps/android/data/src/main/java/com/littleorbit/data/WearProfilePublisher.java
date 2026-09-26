package com.littleorbit.data;

import android.content.Context;
import com.google.android.gms.wearable.Asset;
import com.google.android.gms.wearable.PutDataMapRequest;
import com.google.android.gms.wearable.Wearable;
import com.littleorbit.data.repository.ProfileRepository;
import dagger.hilt.android.qualifiers.ApplicationContext;
import javax.inject.Inject;
import javax.inject.Singleton;

/** Sends only authorized names and small profile thumbnails to the paired watch. */
@Singleton
public final class WearProfilePublisher {
    public static final String PATH = "/little-orbit/profile-v1";
    public static final String MANAGED_PATH = "/little-orbit/watch-profile-v1";
    private final Context context;
    private final RelationshipDisplayIdentity relationshipIdentity;
    private final ManagedWatchStore watches;

    /** Creates the Wear Data Layer profile publisher. */
    @Inject
    public WearProfilePublisher(
            @ApplicationContext Context context,
            RelationshipDisplayIdentity relationshipIdentity,
            ManagedWatchStore watches) {
        this.context = context;
        this.relationshipIdentity = relationshipIdentity;
        this.watches = watches;
    }

    /** Replaces the watch profile cache without sending account identifiers or tokens. */
    public void publish(ProfileRepository.State state) {
        RelationshipDisplayIdentity.Snapshot relationship = relationshipIdentity.read();
        ManagedWatchStore.Snapshot watch = watches.read();
        if (!relationship.active()) {
            clear(relationship);
            return;
        }
        if (!watch.enabled() || watch.nodeId().isBlank()) return;
        PutDataMapRequest request = PutDataMapRequest.create(MANAGED_PATH);
        putRelationship(request, relationship, true);
        putTarget(request, watch);
        request.getDataMap().putString("my_name", state.myName());
        request.getDataMap().putString(
                "partner_name", state.partnerName() == null ? "" : state.partnerName());
        putAsset(request, "my_photo", watch.showPhotos() ? state.myPhoto() : null);
        putAsset(request, "partner_photo", watch.showPhotos() ? state.partnerPhoto() : null);
        request.getDataMap().putLong("changed_at", System.currentTimeMillis());
        Wearable.getDataClient(context).putDataItem(request.asPutDataRequest().setUrgent());
    }

    /** Explicitly invalidates both watch images when the session ends. */
    public void clear() { clear(relationshipIdentity.read()); }

    /** Publishes a blank profile under the same durable purge generation. */
    public void clear(RelationshipDisplayIdentity.Snapshot purge) {
        publishBlank(PATH, purge, null);
        ManagedWatchStore.Snapshot watch = watches.read();
        if (!watch.nodeId().isBlank()) publishBlank(MANAGED_PATH, purge, watch);
    }

    private static void putAsset(PutDataMapRequest request, String key, byte[] bytes) {
        if (bytes == null || bytes.length == 0) request.getDataMap().remove(key);
        else request.getDataMap().putAsset(key, Asset.createFromBytes(bytes));
    }

    private static void putRelationship(
            PutDataMapRequest request,
            RelationshipDisplayIdentity.Snapshot relationship,
            boolean active) {
        request.getDataMap().putInt("schema_version", 3);
        request.getDataMap().putString("relationship_id", relationship.relationshipId());
        request.getDataMap().putLong("relationship_generation", relationship.generation());
        request.getDataMap().putBoolean("relationship_active", active);
        request.getDataMap().putLong("authorized_at", System.currentTimeMillis());
    }

    private void publishBlank(
            String path,
            RelationshipDisplayIdentity.Snapshot purge,
            ManagedWatchStore.Snapshot watch) {
        PutDataMapRequest request = PutDataMapRequest.create(path);
        putRelationship(request, purge, false);
        if (watch != null) putTarget(request, watch);
        request.getDataMap().putString("my_name", "You");
        request.getDataMap().putString("partner_name", "");
        request.getDataMap().putLong("changed_at", System.currentTimeMillis());
        Wearable.getDataClient(context).putDataItem(request.asPutDataRequest().setUrgent());
    }

    private static void putTarget(
            PutDataMapRequest request, ManagedWatchStore.Snapshot watch) {
        request.getDataMap().putString("target_node_id", watch.nodeId());
        request.getDataMap().putLong("watch_generation", watch.generation());
    }
}
