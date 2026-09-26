package com.littleorbit.mobile;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNull;

import java.util.List;
import org.junit.Test;

/** Regression tests for endpoint matching, replacement, loss, and reconnect discovery. */
public final class WearEndpointRegistryTest {
    private final WearEndpointRegistry registry = new WearEndpointRegistry();

    @Test public void matchesPairingAndConnectOnTheSameHostAndNetwork() {
        endpoint(WearEndpointRegistry.Kind.CONNECT, "phone", "192.0.2.1", 41000, 1);
        WearEndpointRegistry.Endpoint watch = endpoint(
                WearEndpointRegistry.Kind.CONNECT, "watch-connect", "192.0.2.2", 42000, 1);
        endpoint(WearEndpointRegistry.Kind.PAIRING, "watch-pair", "192.0.2.2", 43000, 1);

        WearEndpointRegistry.Snapshot snapshot = registry.snapshot();

        assertEquals(watch, snapshot.connect());
        assertEquals(2, snapshot.connectCandidates().size());
    }

    @Test public void doesNotMixTheSameAddressAcrossDifferentNetworks() {
        endpoint(WearEndpointRegistry.Kind.CONNECT, "watch-connect", "192.0.2.2", 42000, 2);
        endpoint(WearEndpointRegistry.Kind.PAIRING, "watch-pair", "192.0.2.2", 43000, 1);

        assertNull(registry.snapshot().connect());
    }

    @Test public void updatesRotatedPortAndRemovesLostService() {
        endpoint(WearEndpointRegistry.Kind.CONNECT, "watch", "192.0.2.2", 42000, 1);
        WearEndpointRegistry.Endpoint rotated = endpoint(
                WearEndpointRegistry.Kind.CONNECT, "watch", "192.0.2.2", 42001, 1);
        assertEquals(List.of(rotated), registry.snapshot().connectCandidates());

        WearEndpointRegistry.Snapshot removed = registry.remove(
                WearEndpointRegistry.Kind.CONNECT, "watch", 1);

        assertEquals(List.of(), removed.connectCandidates());
    }

    @Test public void exposesConnectOnlyRecordsForRememberedAuthorization() {
        WearEndpointRegistry.Endpoint watch = endpoint(
                WearEndpointRegistry.Kind.CONNECT, "watch", "192.0.2.2", 42000, 1);

        WearEndpointRegistry.Snapshot snapshot = registry.snapshot();

        assertNull(snapshot.pairing());
        assertNull(snapshot.connect());
        assertEquals(List.of(watch), snapshot.connectCandidates());
    }

    private WearEndpointRegistry.Endpoint endpoint(WearEndpointRegistry.Kind kind,
            String name, String host, int port, long network) {
        WearEndpointRegistry.Endpoint value = new WearEndpointRegistry.Endpoint(
                name, host, port, network);
        registry.upsert(kind, value);
        return value;
    }
}
