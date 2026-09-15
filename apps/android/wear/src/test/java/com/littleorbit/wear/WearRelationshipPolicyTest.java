package com.littleorbit.wear;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

/** Covers stale, purge, delayed-payload, and new-relationship ordering. */
public final class WearRelationshipPolicyTest {
    private static final long NOW = 2_000_000_000_000L;

    @Test
    public void purgeRejectsDelayedPayloadFromTheSameGeneration() {
        WearRelationshipPolicy.Transition active = WearRelationshipPolicy.acceptActive(
                WearRelationshipPolicy.State.empty(), "first", 4, NOW, NOW);
        WearRelationshipPolicy.Transition purge = WearRelationshipPolicy.purge(
                active.state(), "first", 5, NOW + 1);
        WearRelationshipPolicy.Transition delayed = WearRelationshipPolicy.acceptActive(
                purge.state(), "first", 4, NOW + 2, NOW + 2);
        WearRelationshipPolicy.Transition sameGeneration = WearRelationshipPolicy.acceptActive(
                purge.state(), "first", 5, NOW + 2, NOW + 2);

        assertTrue(purge.accepted());
        assertTrue(purge.clearLocal());
        assertFalse(delayed.accepted());
        assertFalse(sameGeneration.accepted());
    }

    @Test
    public void newerRelationshipClearsOldStateBeforeAcceptance() {
        WearRelationshipPolicy.State purged = new WearRelationshipPolicy.State(
                "first", 5, WearRelationshipPolicy.Status.PURGED, NOW);
        WearRelationshipPolicy.Transition next = WearRelationshipPolicy.acceptActive(
                purged, "second", 6, NOW + 1, NOW + 1);

        assertTrue(next.accepted());
        assertTrue(next.clearLocal());
        assertTrue(WearRelationshipPolicy.readable(next.state()));
    }

    @Test
    public void cacheExpiresAtTwentyFourHoursAndCanRefreshSameRelationship() {
        WearRelationshipPolicy.State active = new WearRelationshipPolicy.State(
                "first", 7, WearRelationshipPolicy.Status.ACTIVE, NOW);
        WearRelationshipPolicy.Transition before = WearRelationshipPolicy.expire(
                active, NOW + WearRelationshipPolicy.EXPIRY_MILLIS - 1);
        WearRelationshipPolicy.Transition atBoundary = WearRelationshipPolicy.expire(
                active, NOW + WearRelationshipPolicy.EXPIRY_MILLIS);
        WearRelationshipPolicy.Transition refreshed = WearRelationshipPolicy.acceptActive(
                atBoundary.state(), "first", 7,
                NOW + WearRelationshipPolicy.EXPIRY_MILLIS + 1,
                NOW + WearRelationshipPolicy.EXPIRY_MILLIS + 1);

        assertFalse(before.accepted());
        assertTrue(atBoundary.accepted());
        assertTrue(atBoundary.clearLocal());
        assertTrue(refreshed.accepted());
    }

    @Test
    public void protocolGenerationDisablesLegacyReplay() {
        WearRelationshipPolicy.State active = new WearRelationshipPolicy.State(
                "first", 2, WearRelationshipPolicy.Status.ACTIVE, NOW);

        assertFalse(WearRelationshipPolicy.acceptLegacy(active, NOW + 1, NOW + 1).accepted());
    }

    @Test
    public void malformedScopedPayloadCannotAuthorizeAWatchCache() {
        WearRelationshipPolicy.State empty = WearRelationshipPolicy.State.empty();

        assertFalse(WearRelationshipPolicy.acceptActive(empty, "", 1, NOW, NOW).accepted());
        assertFalse(WearRelationshipPolicy.acceptActive(
                empty, "first", 0, NOW, NOW).accepted());
        assertFalse(WearRelationshipPolicy.acceptActive(
                empty, "first", 1, 0, NOW).accepted());
    }

    @Test
    public void delayedLegacyClearCannotWipeScopedRelationship() {
        WearRelationshipPolicy.State active = new WearRelationshipPolicy.State(
                "first", 9, WearRelationshipPolicy.Status.ACTIVE, NOW);

        assertFalse(WearRelationshipPolicy.purgeLegacy(active, NOW + 1).accepted());
        assertTrue(WearRelationshipPolicy.purgeLegacy(
                WearRelationshipPolicy.State.empty(), NOW).clearLocal());
    }

    @Test
    public void alreadyExpiredLegacyPayloadRequestsDeletionWithoutAcceptance() {
        WearRelationshipPolicy.Transition stale = WearRelationshipPolicy.acceptLegacy(
                WearRelationshipPolicy.State.empty(),
                NOW - WearRelationshipPolicy.EXPIRY_MILLIS,
                NOW);

        assertFalse(stale.accepted());
        assertTrue(stale.clearLocal());
        assertTrue(stale.state().status() == WearRelationshipPolicy.Status.EXPIRED);
    }

    @Test
    public void delayedScopedPayloadCannotResurrectAnExpiredRelationship() {
        WearRelationshipPolicy.State active = new WearRelationshipPolicy.State(
                "first", 7, WearRelationshipPolicy.Status.ACTIVE, NOW);
        long afterExpiry = NOW + WearRelationshipPolicy.EXPIRY_MILLIS + 1;
        WearRelationshipPolicy.State expired = WearRelationshipPolicy.expire(
                active, afterExpiry).state();

        WearRelationshipPolicy.Transition replay = WearRelationshipPolicy.acceptActive(
                expired, "first", 7, NOW, afterExpiry);
        WearRelationshipPolicy.Transition fresh = WearRelationshipPolicy.acceptActive(
                expired, "first", 7, afterExpiry, afterExpiry);

        assertFalse(replay.accepted());
        assertTrue(fresh.accepted());
    }

    @Test
    public void implausibleFutureAuthorizationCannotExtendRetention() {
        long tooFarAhead = NOW + WearRelationshipPolicy.MAX_CLOCK_SKEW_MILLIS + 1;

        assertFalse(WearRelationshipPolicy.acceptActive(
                WearRelationshipPolicy.State.empty(), "first", 1,
                tooFarAhead, NOW).accepted());
        assertFalse(WearRelationshipPolicy.acceptLegacy(
                WearRelationshipPolicy.State.empty(), tooFarAhead, NOW).accepted());
    }
}
