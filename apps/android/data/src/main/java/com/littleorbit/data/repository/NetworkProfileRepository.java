package com.littleorbit.data.repository;

import com.littleorbit.data.DisplayCacheSynchronizer;
import com.littleorbit.data.WearProfilePublisher;
import com.littleorbit.data.remote.LittleOrbitApi;
import com.littleorbit.data.remote.ProfileApiModels;
import com.littleorbit.data.security.SessionStore;
import java.io.IOException;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import javax.inject.Inject;
import javax.inject.Singleton;
import okhttp3.MediaType;
import okhttp3.RequestBody;
import okhttp3.ResponseBody;
import retrofit2.Call;

/** Serial profile synchronizer that preserves the last encrypted state during outages. */
@Singleton
public final class NetworkProfileRepository implements ProfileRepository {
    private static final MediaType WEBP = MediaType.get("image/webp");
    private final LittleOrbitApi api;
    private final ProfilePhotoStore store;
    private final WearProfilePublisher wear;
    private final DisplayCacheSynchronizer displays;
    private final SessionStore sessions;
    private final ExecutorService executor = Executors.newSingleThreadExecutor(runnable -> {
        Thread thread = new Thread(runnable, "orbit-profile-sync");
        thread.setDaemon(true);
        return thread;
    });

    /** Creates the authenticated profile sync boundary. */
    @Inject
    public NetworkProfileRepository(
            LittleOrbitApi api,
            ProfilePhotoStore store,
            WearProfilePublisher wear,
            DisplayCacheSynchronizer displays,
            SessionStore sessions) {
        this.api = api;
        this.store = store;
        this.wear = wear;
        this.displays = displays;
        this.sessions = sessions;
    }

    @Override public State cached() { return store.read(); }

    @Override
    public CompletableFuture<State> refresh() {
        return CompletableFuture.supplyAsync(() -> {
            try { return refreshNow(); }
            catch (RuntimeException failure) {
                if (RelationshipCachePurger.sessionInvalid(failure)) {
                    clearAll();
                    displays.clear();
                    sessions.clear();
                    throw failure;
                }
                if (RelationshipCachePurger.relationshipInactive(failure)) {
                    clearAll();
                    displays.clear();
                    throw failure;
                }
                return store.read();
            }
        }, executor);
    }

    @Override
    public CompletableFuture<State> uploadPartnerPhoto(byte[] webp) {
        return CompletableFuture.supplyAsync(() -> {
            execute(api.putPartnerAvatar(RequestBody.create(webp.clone(), WEBP)));
            return refreshNow();
        }, executor);
    }

    @Override
    public CompletableFuture<State> deletePartnerPhoto() {
        return CompletableFuture.supplyAsync(() -> {
            executeNoBody(api.deletePartnerAvatar());
            return refreshNow();
        }, executor);
    }

    @Override public void clearPartner() { store.clearPartner(); wear.publish(store.read()); }
    @Override public void clearAll() { store.clearAll(); wear.clear(); }

    private State refreshNow() {
        ProfileApiModels.OrbitProfile profile = execute(api.orbitProfile());
        State cached = store.read();
        byte[] own = resolvePhoto(false, profile.me.photo, cached.myPhoto());
        ProfileApiModels.Person partner = profile.partner;
        byte[] partnerPhoto = partner == null
                ? null : resolvePhoto(true, partner.photo, cached.partnerPhoto());
        int ownRevision = profile.me.photo == null ? 0 : profile.me.photo.revision;
        int partnerRevision = partner == null || partner.photo == null ? 0 : partner.photo.revision;
        store.save(
                profile.me.displayName, ownRevision, hash(profile.me.photo), own,
                partner == null ? null : partner.displayName,
                partnerRevision, hash(partner == null ? null : partner.photo), partnerPhoto);
        State refreshed = store.read();
        wear.publish(refreshed);
        return refreshed;
    }

    private byte[] resolvePhoto(
            boolean partner, ProfileApiModels.PhotoMetadata metadata, byte[] cached) {
        if (metadata == null) return null;
        if (store.revision(partner) == metadata.revision
                && metadata.sha256.equals(store.hash(partner)) && cached != null) return cached;
        ResponseBody body = execute(
                partner ? api.partnerProfilePhoto(true) : api.profilePhoto(true));
        try (body) { return body.bytes(); }
        catch (IOException failure) { throw new ProfileServiceException("Could not read profile image", failure); }
    }

    private static String hash(ProfileApiModels.PhotoMetadata metadata) {
        return metadata == null ? "" : metadata.sha256;
    }

    private static <T> T execute(Call<T> call) {
        return RetrofitCalls.execute(call);
    }

    private static void executeNoBody(Call<Void> call) {
        RetrofitCalls.executeVoid(call);
    }

    /** Content-free profile sync failure. */
    public static final class ProfileServiceException extends RuntimeException {
        ProfileServiceException(String message) { super(message); }
        ProfileServiceException(String message, Throwable cause) { super(message, cause); }
    }
}
