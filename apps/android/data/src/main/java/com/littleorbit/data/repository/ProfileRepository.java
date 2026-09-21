package com.littleorbit.data.repository;

import java.util.concurrent.CompletableFuture;

/** Partner-assigned relationship-avatar boundary with encrypted offline thumbnails. */
public interface ProfileRepository {
    /** Immutable names and private thumbnails safe for the signed-in phone UI. */
    record State(
            String myName,
            byte[] myPhoto,
            String partnerName,
            byte[] partnerPhoto,
            int myNameRevision,
            boolean myNamePartnerAssigned,
            int partnerNameRevision,
            boolean partnerNameAssigned) {
        /** Backward-compatible empty name metadata for signed-out and test states. */
        public State(String myName, byte[] myPhoto, String partnerName, byte[] partnerPhoto) {
            this(myName, myPhoto, partnerName, partnerPhoto, 0, false, 0, false);
        }

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

    /** Assigns a cropped WebP image to the current partner. */
    CompletableFuture<State> uploadPartnerPhoto(byte[] webp);

    /** Deletes the avatar that the caller assigned to the current partner. */
    CompletableFuture<State> deletePartnerPhoto();

    /** Assigns a shared relationship name to the current partner. */
    CompletableFuture<State> savePartnerName(String displayName);

    /** Resets the current partner to the privacy-safe account-name fallback. */
    CompletableFuture<State> resetPartnerName();

    /** Clears both relationship-scoped avatars as soon as sharing ends. */
    void clearPartner();

    /** Clears all cached profile identity when the local session ends. */
    void clearAll();
}
