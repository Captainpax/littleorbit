package com.littleorbit.mobile;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import java.util.List;
import org.junit.Test;

/** Covers explicit manual selection, discovery, and transient pairing-code validation. */
public final class WearInstallRequestTest {
    private static final WearEndpointRegistry.Endpoint AUTO_PAIR = endpoint("auto-pair", 41_000);
    private static final WearEndpointRegistry.Endpoint AUTO_CONNECT = endpoint("auto-connect", 42_000);
    private static final WearEndpointRegistry.Snapshot DISCOVERED =
            new WearEndpointRegistry.Snapshot(AUTO_PAIR, AUTO_CONNECT, List.of(AUTO_CONNECT));

    @Test
    public void manualValuesReplaceDiscoveredValues() {
        WearInstallRequest request = WearInstallRequest.create(
                DISCOVERED, true, "192.0.2.8", 43_000, 44_000, "123456");

        assertEquals(43_000, request.pairing().port());
        assertEquals(44_000, request.connectCandidates().get(0).port());
        assertTrue(request.canPair());
        assertFalse(request.toString().contains("123456"));
    }

    @Test
    public void automaticModeUsesOnlyDiscoveredCandidates() {
        WearInstallRequest request = WearInstallRequest.create(
                DISCOVERED, false, "192.0.2.8", 43_000, 44_000, "123456");

        assertEquals(AUTO_PAIR, request.pairing());
        assertEquals(List.of(AUTO_CONNECT), request.connectCandidates());
    }

    @Test
    public void rememberedIdentityStillRequiresAConnectEndpoint() {
        WearInstallRequest request = WearInstallRequest.create(
                WearEndpointRegistry.Snapshot.empty(), true, "192.0.2.8", 0, 0, "246810");

        assertFalse(request.canPair());
        assertFalse(request.canStart(true));
    }

    private static WearEndpointRegistry.Endpoint endpoint(String name, int port) {
        return new WearEndpointRegistry.Endpoint(name, "192.0.2.7", port, 7);
    }
}
