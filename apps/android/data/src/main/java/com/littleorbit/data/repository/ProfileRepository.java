package com.littleorbit.data.repository;

import java.util.concurrent.CompletableFuture;

/** Authenticated profile-photo boundary with encrypted offline thumbnails. */
public interface ProfileRepository {
    /** Immutable names and private thumbnails safe for the signed-in phone UI. */
    record State(String myName, byte[] myPhoto, String partnerName, byte[] partnerPhoto) {
        /** Copies mutable byte arrays at the repository boundary. */
        public State {
            myPhoto = myPhoto == null ? null : myPhoto.clone();
            partnerPhoto = partnerPhoto == null ? null : partnerPhoto.clone();
        }

        @Override public byte[] myPhoto() { return myPhoto == null ? null : myPhoto.clone(); }
        @Override public byte[] partnerPhoto() {
            return partnerPhoto == null ? null : partnerPhoto.clone();
        }

        /** Returns true when an active partner identity is present. */
        public boolean paired() { return partnerName != null && !partnerName.isBlank(); }
    }

    /** Returns the last encrypted local copy without doing network I/O. */
    State cached();

    /** Refreshes authorized names and changed thumbnails, falling back to the cache offline. */
    CompletableFuture<State> refresh();

    /** Uploads a cropped WebP image and refreshes all profile state. */
    CompletableFuture<State> upload(byte[] webp);

    /** Deletes the caller's image and refreshes the fallback identity. */
    CompletableFuture<State> deleteOwnPhoto();

    /** Clears partner identity as soon as sharing ends. */
    void clearPartner();

    /** Clears all cached profile identity when the local session ends. */
    void clearAll();
}
