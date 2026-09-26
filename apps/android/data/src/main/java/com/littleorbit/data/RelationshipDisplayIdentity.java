package com.littleorbit.data;

import android.content.Context;
import android.content.SharedPreferences;
import dagger.hilt.android.qualifiers.ApplicationContext;
import java.util.UUID;
import javax.inject.Inject;
import javax.inject.Singleton;

/** Tracks one opaque relationship generation for passive Android and Wear surfaces. */
@Singleton
public final class RelationshipDisplayIdentity {
    private static final String PREFERENCES = "little-orbit-display-identity";
    private final SharedPreferences values;

    /** Creates the app-private relationship identity store. */
    @Inject
    public RelationshipDisplayIdentity(@ApplicationContext Context context) {
        values = context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE);
    }

    /** Activates the generation for the exact immutable pairing instant. */
    public synchronized Snapshot activate(String relationshipId) {
        String canonical = canonicalId(relationshipId);
        Snapshot next = activated(read(), canonical, System.currentTimeMillis());
        persist(next);
        return next;
    }

    /** Advances the generation and marks all passive relationship data unauthorized. */
    public synchronized Snapshot purge() {
        Snapshot next = purged(read(), System.currentTimeMillis());
        persist(next);
        return next;
    }

    /** Returns the current content-free relationship generation. */
    public synchronized Snapshot read() {
        return new Snapshot(
                values.getString("relationship_id", ""),
                values.getLong("generation", 0),
                values.getBoolean("active", false),
                values.getLong("changed_at", 0));
    }

    static Snapshot activated(Snapshot current, String relationshipId, long now) {
        if (current.active() && current.relationshipId().equals(relationshipId)) return current;
        return new Snapshot(relationshipId, nextGeneration(current.generation(), now), true, now);
    }

    static Snapshot purged(Snapshot current, long now) {
        return new Snapshot(
                current.relationshipId(), nextGeneration(current.generation(), now), false, now);
    }

    static String canonicalId(String relationshipId) {
        try {
            return UUID.fromString(relationshipId).toString();
        } catch (Exception invalid) {
            throw new IllegalArgumentException("Relationship identity is invalid", invalid);
        }
    }

    private void persist(Snapshot snapshot) {
        boolean stored = values.edit()
                .putString("relationship_id", snapshot.relationshipId())
                .putLong("generation", snapshot.generation())
                .putBoolean("active", snapshot.active())
                .putLong("changed_at", snapshot.changedAt())
                .commit();
        if (!stored) throw new IllegalStateException("Could not persist display identity");
    }

    private static long nextGeneration(long current, long now) {
        if (current == Long.MAX_VALUE) return Long.MAX_VALUE;
        return Math.max(current + 1, Math.max(1, now));
    }

    /** Opaque relationship identity and monotonic local authorization generation. */
    public record Snapshot(String relationshipId, long generation, boolean active, long changedAt) {}
}
