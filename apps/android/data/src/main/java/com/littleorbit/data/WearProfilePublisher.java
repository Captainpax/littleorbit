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
    private final Context context;
    private final RelationshipDisplayIdentity relationshipIdentity;

    /** Creates the Wear Data Layer profile publisher. */
    @Inject
    public WearProfilePublisher(
            @ApplicationContext Context context,
            RelationshipDisplayIdentity relationshipIdentity) {
        this.context = context;
        this.relationshipIdentity = relationshipIdentity;
    }

    /** Replaces the watch profile cache without sending account identifiers or tokens. */
    public void publish(ProfileRepository.State state) {
        RelationshipDisplayIdentity.Snapshot relationship = relationshipIdentity.read();
        if (!relationship.active()) {
            clear(relationship);
            return;
        }
        PutDataMapRequest request = PutDataMapRequest.create(PATH);
        putRelationship(request, relationship, true);
        request.getDataMap().putString("my_name", state.myName());
        request.getDataMap().putString(
                "partner_name", state.partnerName() == null ? "" : state.partnerName());
        putAsset(request, "my_photo", state.myPhoto());
        putAsset(request, "partner_photo", state.partnerPhoto());
        request.getDataMap().putLong("changed_at", System.currentTimeMillis());
        Wearable.getDataClient(context).putDataItem(request.asPutDataRequest().setUrgent());
    }

    /** Explicitly invalidates both watch images when the session ends. */
    public void clear() { clear(relationshipIdentity.read()); }

    /** Publishes a blank profile under the same durable purge generation. */
    public void clear(RelationshipDisplayIdentity.Snapshot purge) {
        PutDataMapRequest request = PutDataMapRequest.create(PATH);
        putRelationship(request, purge, false);
        request.getDataMap().putString("my_name", "You");
        request.getDataMap().putString("partner_name", "");
        request.getDataMap().putLong("changed_at", System.currentTimeMillis());
        Wearable.getDataClient(context).putDataItem(request.asPutDataRequest().setUrgent());
    }

    private static void putAsset(PutDataMapRequest request, String key, byte[] bytes) {
        if (bytes == null || bytes.length == 0) request.getDataMap().remove(key);
        else request.getDataMap().putAsset(key, Asset.createFromBytes(bytes));
    }

    private static void putRelationship(
            PutDataMapRequest request,
            RelationshipDisplayIdentity.Snapshot relationship,
            boolean active) {
        request.getDataMap().putInt("schema_version", 2);
        request.getDataMap().putString("relationship_id", relationship.relationshipId());
        request.getDataMap().putLong("relationship_generation", relationship.generation());
        request.getDataMap().putBoolean("relationship_active", active);
        request.getDataMap().putLong("authorized_at", System.currentTimeMillis());
    }
}
