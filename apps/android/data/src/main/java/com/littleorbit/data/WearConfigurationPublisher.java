package com.littleorbit.data;

import android.content.Context;
import com.google.android.gms.wearable.PutDataMapRequest;
import com.google.android.gms.wearable.Wearable;
import dagger.hilt.android.qualifiers.ApplicationContext;
import javax.inject.Inject;
import javax.inject.Singleton;

/** Publishes one target-scoped preference record without account credentials. */
@Singleton
public final class WearConfigurationPublisher {
    public static final String PATH = "/little-orbit/watch-config-v1";
    private final Context context;
    private final ManagedWatchStore watches;
    private final RelationshipDisplayIdentity relationships;

    /** Creates the managed-watch configuration boundary. */
    @Inject
    public WearConfigurationPublisher(
            @ApplicationContext Context context,
            ManagedWatchStore watches,
            RelationshipDisplayIdentity relationships) {
        this.context = context;
        this.watches = watches;
        this.relationships = relationships;
    }

    /** Sends current preferences only to the selected node. */
    public void publish() {
        ManagedWatchStore.Snapshot watch = watches.read();
        RelationshipDisplayIdentity.Snapshot relationship = relationships.read();
        if (!watch.enabled() || watch.nodeId().isBlank() || !relationship.active()) return;
        PutDataMapRequest request = PutDataMapRequest.create(PATH);
        request.getDataMap().putInt("schema_version", 1);
        request.getDataMap().putString("target_node_id", watch.nodeId());
        request.getDataMap().putLong("watch_generation", watch.generation());
        request.getDataMap().putString("relationship_id", relationship.relationshipId());
        request.getDataMap().putLong("relationship_generation", relationship.generation());
        request.getDataMap().putLong("authorized_at", System.currentTimeMillis());
        request.getDataMap().putBoolean("show_photos", watch.showPhotos());
        request.getDataMap().putBoolean(
                "show_countdown_titles", watch.showCountdownTitles());
        request.getDataMap().putBoolean("smooch_enabled", watch.smoochEnabled());
        request.getDataMap().putString("default_destination", watch.defaultDestination());
        Wearable.getDataClient(context).putDataItem(request.asPutDataRequest().setUrgent());
    }
}
