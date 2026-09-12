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

    /** Creates the Wear Data Layer profile publisher. */
    @Inject
    public WearProfilePublisher(@ApplicationContext Context context) { this.context = context; }

    /** Replaces the watch profile cache without sending account identifiers or tokens. */
    public void publish(ProfileRepository.State state) {
        PutDataMapRequest request = PutDataMapRequest.create(PATH);
        request.getDataMap().putString("my_name", state.myName());
        request.getDataMap().putString(
                "partner_name", state.partnerName() == null ? "" : state.partnerName());
        putAsset(request, "my_photo", state.myPhoto());
        putAsset(request, "partner_photo", state.partnerPhoto());
        request.getDataMap().putLong("changed_at", System.currentTimeMillis());
        Wearable.getDataClient(context).putDataItem(request.asPutDataRequest().setUrgent());
    }

    /** Explicitly invalidates both watch images when the session ends. */
    public void clear() { publish(new ProfileRepository.State("You", null, null, null)); }

    private static void putAsset(PutDataMapRequest request, String key, byte[] bytes) {
        if (bytes == null || bytes.length == 0) request.getDataMap().remove(key);
        else request.getDataMap().putAsset(key, Asset.createFromBytes(bytes));
    }
}
