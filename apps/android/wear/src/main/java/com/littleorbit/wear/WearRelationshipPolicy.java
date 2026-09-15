package com.littleorbit.wear;

/** Pure generation and expiry policy for relationship-scoped Wear cache updates. */
final class WearRelationshipPolicy {
    static final long EXPIRY_MILLIS = 24L * 60 * 60 * 1_000;
    static final long MAX_CLOCK_SKEW_MILLIS = 5L * 60 * 1_000;

    private WearRelationshipPolicy() {}

    enum Status { NONE, LEGACY, ACTIVE, EXPIRED, PURGED }

    record State(String relationshipId, long generation, Status status, long authorizedAt) {
        static State empty() { return new State("", 0, Status.NONE, 0); }
    }

    record Transition(State state, boolean accepted, boolean clearLocal) {}

    static Transition acceptActive(
            State current,
            String relationshipId,
            long generation,
            long authorizedAt,
            long now) {
        State safe = current == null ? State.empty() : current;
        if (relationshipId == null || relationshipId.isBlank()
                || generation <= 0 || !validTimes(authorizedAt, now)) {
            return rejected(safe);
        }
        if (generation < safe.generation()) return rejected(safe);
        long boundedAuthorization = Math.min(authorizedAt, now);
        if (generation == safe.generation()) {
            if (safe.status() == Status.PURGED) return rejected(safe);
            if (!safe.relationshipId().isBlank()
                    && !safe.relationshipId().equals(relationshipId)) return rejected(safe);
            if (expiredAt(boundedAuthorization, now)) {
                if (readable(safe) && !expiredAt(safe.authorizedAt(), now)) {
                    return accepted(safe, false);
                }
                return expired(safe, relationshipId, generation, boundedAuthorization);
            }
            boolean clear = safe.status() != Status.ACTIVE;
            long newestAuthorization = Math.max(safe.authorizedAt(), boundedAuthorization);
            return accepted(
                    new State(relationshipId, generation, Status.ACTIVE, newestAuthorization), clear);
        }
        if (expiredAt(boundedAuthorization, now)) {
            return expired(safe, relationshipId, generation, boundedAuthorization);
        }
        return accepted(
                new State(relationshipId, generation, Status.ACTIVE, boundedAuthorization), true);
    }

    static Transition acceptLegacy(State current, long authorizedAt, long now) {
        State safe = current == null ? State.empty() : current;
        if (safe.generation() > 0 || !validTimes(authorizedAt, now)) return rejected(safe);
        long boundedAuthorization = Math.min(authorizedAt, now);
        if ((safe.status() == Status.LEGACY || safe.status() == Status.EXPIRED)
                && boundedAuthorization <= safe.authorizedAt()) return rejected(safe);
        if (expiredAt(boundedAuthorization, now)) {
            return new Transition(
                    new State("", 0, Status.EXPIRED, boundedAuthorization), false, true);
        }
        return accepted(new State("", 0, Status.LEGACY, boundedAuthorization), false);
    }

    static Transition purge(State current, String relationshipId, long generation, long now) {
        State safe = current == null ? State.empty() : current;
        if (generation <= 0 || generation < safe.generation()) return rejected(safe);
        String markerId = relationshipId == null ? "" : relationshipId;
        return new Transition(
                new State(markerId, generation, Status.PURGED, Math.max(0, now)), true, true);
    }

    static Transition purgeLegacy(State current, long now) {
        State safe = current == null ? State.empty() : current;
        if (safe.generation() > 0 || now <= 0) return rejected(safe);
        return new Transition(new State("", 0, Status.EXPIRED, now), true, true);
    }

    static Transition expire(State current, long now) {
        State safe = current == null ? State.empty() : current;
        if ((safe.status() != Status.ACTIVE && safe.status() != Status.LEGACY)
                || !expiredAt(safe.authorizedAt(), now)) return rejected(safe);
        return new Transition(
                new State(
                        safe.relationshipId(), safe.generation(), Status.EXPIRED,
                        safe.authorizedAt()),
                true,
                true);
    }

    static boolean readable(State state) {
        return state.status() == Status.ACTIVE || state.status() == Status.LEGACY;
    }

    static long expiresAt(State state) {
        if (!readable(state) || state.authorizedAt() <= 0) return 0;
        if (state.authorizedAt() > Long.MAX_VALUE - EXPIRY_MILLIS) return Long.MAX_VALUE;
        return state.authorizedAt() + EXPIRY_MILLIS;
    }

    private static boolean expiredAt(long authorizedAt, long now) {
        return authorizedAt <= 0 || expiresAt(
                new State("", 0, Status.ACTIVE, authorizedAt)) <= now;
    }

    private static boolean validTimes(long authorizedAt, long now) {
        if (authorizedAt <= 0 || now <= 0) return false;
        long futureLimit = now > Long.MAX_VALUE - MAX_CLOCK_SKEW_MILLIS
                ? Long.MAX_VALUE : now + MAX_CLOCK_SKEW_MILLIS;
        return authorizedAt <= futureLimit;
    }

    private static Transition expired(
            State current, String relationshipId, long generation, long authorizedAt) {
        if (generation == current.generation() && current.status() == Status.EXPIRED) {
            return rejected(current);
        }
        return new Transition(
                new State(relationshipId, generation, Status.EXPIRED, authorizedAt), false, true);
    }

    private static Transition accepted(State state, boolean clear) {
        return new Transition(state, true, clear);
    }

    private static Transition rejected(State state) {
        return new Transition(state, false, false);
    }
}
