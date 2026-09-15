package com.littleorbit.wear;

import android.content.Context;
import android.content.SharedPreferences;
import java.io.IOException;
import java.io.InputStream;

/** Persists the Wear relationship generation and applies purge barriers before payloads. */
final class WearRelationshipGuard {
    private static final String PREFERENCES = "little_orbit_relationship_guard";

    private WearRelationshipGuard() {}

    static synchronized boolean acceptActive(
            Context context,
            String relationshipId,
            long generation,
            long authorizedAt,
            long now) {
        return apply(context, WearRelationshipPolicy.acceptActive(
                read(context), relationshipId, generation, authorizedAt, now));
    }

    static synchronized boolean acceptActiveAndRun(
            Context context,
            String relationshipId,
            long generation,
            long authorizedAt,
            long now,
            Runnable write) {
        if (!acceptActive(
                context, relationshipId, generation, authorizedAt, now)) return false;
        write.run();
        return true;
    }

    static synchronized boolean acceptLegacy(Context context, long authorizedAt, long now) {
        return apply(context, WearRelationshipPolicy.acceptLegacy(
                read(context), authorizedAt, now));
    }

    static synchronized boolean acceptLegacyAndRun(
            Context context, long authorizedAt, long now, Runnable write) {
        if (!acceptLegacy(context, authorizedAt, now)) return false;
        write.run();
        return true;
    }

    static synchronized boolean storePhotoIfAuthorized(
            Context context,
            boolean partner,
            InputStream input,
            String relationshipId,
            long generation,
            int schema) throws IOException {
        expireIfNeeded(context, System.currentTimeMillis());
        WearRelationshipPolicy.State current = read(context);
        boolean authorized = schema >= 2
                ? current.status() == WearRelationshipPolicy.Status.ACTIVE
                        && current.generation() == generation
                        && current.relationshipId().equals(relationshipId)
                : current.status() == WearRelationshipPolicy.Status.LEGACY;
        if (!authorized) {
            input.close();
            return false;
        }
        // Holding the relationship lock through the atomic replace makes purge win
        // either before this check or immediately after this bounded 64 KiB write.
        WearProfileStore.storePhoto(context, partner, input);
        return true;
    }

    static synchronized boolean purge(
            Context context, String relationshipId, long generation, long now) {
        WearRelationshipPolicy.Transition transition = WearRelationshipPolicy.purge(
                read(context), relationshipId, generation, now);
        boolean applied = apply(context, transition);
        if (applied) WearCacheExpiryReceiver.cancel(context);
        return applied;
    }

    static synchronized boolean purgeLegacy(Context context, long now) {
        boolean applied = apply(
                context, WearRelationshipPolicy.purgeLegacy(read(context), now));
        if (applied) WearCacheExpiryReceiver.cancel(context);
        return applied;
    }

    static synchronized boolean ensureReadable(Context context, long legacySyncedAt, long now) {
        WearRelationshipPolicy.State current = read(context);
        if (current.status() == WearRelationshipPolicy.Status.NONE && legacySyncedAt > 0) {
            apply(context, WearRelationshipPolicy.acceptLegacy(current, legacySyncedAt, now));
            current = read(context);
        }
        WearRelationshipPolicy.Transition expiry =
                WearRelationshipPolicy.expire(current, now);
        if (expiry.accepted()) apply(context, expiry);
        WearRelationshipPolicy.State resolved = read(context);
        if (WearRelationshipPolicy.readable(resolved)) {
            WearCacheExpiryReceiver.schedule(
                    context, WearRelationshipPolicy.expiresAt(resolved));
            return true;
        }
        return false;
    }

    static synchronized boolean isCurrentActive(
            Context context, String relationshipId, long generation) {
        WearRelationshipPolicy.State current = read(context);
        return current.status() == WearRelationshipPolicy.Status.ACTIVE
                && current.generation() == generation
                && current.relationshipId().equals(relationshipId);
    }

    static synchronized boolean expireIfNeeded(Context context, long now) {
        WearRelationshipPolicy.Transition expiry =
                WearRelationshipPolicy.expire(read(context), now);
        if (!expiry.accepted()) {
            scheduleCurrent(context);
            return false;
        }
        apply(context, expiry);
        WearCacheExpiryReceiver.cancel(context);
        return true;
    }

    static synchronized void scheduleCurrent(Context context) {
        long deadline = WearRelationshipPolicy.expiresAt(read(context));
        if (deadline > 0) WearCacheExpiryReceiver.schedule(context, deadline);
        else WearCacheExpiryReceiver.cancel(context);
    }

    private static boolean apply(
            Context context, WearRelationshipPolicy.Transition transition) {
        if (!transition.accepted() && !transition.clearLocal()) return false;
        if (transition.clearLocal()) clearRelationshipContent(context);
        if (!persist(context, transition.state())) return false;
        if (!transition.accepted()) return false;
        if (WearRelationshipPolicy.readable(transition.state())) {
            WearCacheExpiryReceiver.schedule(
                    context, WearRelationshipPolicy.expiresAt(transition.state()));
        }
        return true;
    }

    private static WearRelationshipPolicy.State read(Context context) {
        SharedPreferences values = context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE);
        String status = values.getString("status", WearRelationshipPolicy.Status.NONE.name());
        WearRelationshipPolicy.Status parsed;
        try {
            parsed = status == null
                    ? WearRelationshipPolicy.Status.PURGED
                    : WearRelationshipPolicy.Status.valueOf(status);
        } catch (IllegalArgumentException invalid) {
            parsed = WearRelationshipPolicy.Status.PURGED;
        }
        return new WearRelationshipPolicy.State(
                values.getString("relationship_id", ""),
                values.getLong("generation", 0),
                parsed,
                values.getLong("authorized_at", 0));
    }

    private static boolean persist(Context context, WearRelationshipPolicy.State state) {
        boolean stored = context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE).edit()
                .putString("relationship_id", state.relationshipId())
                .putLong("generation", state.generation())
                .putString("status", state.status().name())
                .putLong("authorized_at", state.authorizedAt())
                .commit();
        if (!stored) clearRelationshipContent(context);
        return stored;
    }

    private static void clearRelationshipContent(Context context) {
        WearDisplayCache.clearValues(context);
        WearProfileStore.clearAll(context);
    }
}
