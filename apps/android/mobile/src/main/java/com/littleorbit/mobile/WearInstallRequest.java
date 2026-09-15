package com.littleorbit.mobile;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

/** Immutable, transient selection of one watch pairing flow and TLS endpoints. */
record WearInstallRequest(
        WearEndpointRegistry.Endpoint pairing,
        List<WearEndpointRegistry.Endpoint> connectCandidates,
        String pairingCode) {

    static WearInstallRequest create(
            WearEndpointRegistry.Snapshot discovered,
            boolean manual,
            String host,
            int pairingPort,
            int connectPort,
            String pairingCode) {
        WearEndpointRegistry.Endpoint manualPair = endpoint(
                "manual-pair", host, pairingPort);
        WearEndpointRegistry.Endpoint manualConnect = endpoint(
                "manual-connect", host, connectPort);
        WearEndpointRegistry.Endpoint selectedPair = manual
                ? manualPair : discovered.pairing();
        List<WearEndpointRegistry.Endpoint> candidates = new ArrayList<>();
        if (manual) {
            if (manualConnect != null) candidates.add(manualConnect);
        } else {
            candidates.addAll(discovered.connectCandidates());
        }
        return new WearInstallRequest(
                selectedPair, unique(candidates), pairingCode == null ? "" : pairingCode.trim());
    }

    boolean canPair() {
        return pairing != null && pairingCode.matches("[0-9]{6}");
    }

    boolean canStart(boolean remembered) {
        return (remembered && !connectCandidates.isEmpty()) || canPair();
    }

    @Override
    public String toString() {
        return "WearInstallRequest[pairing=" + pairing
                + ", connectCandidates=" + connectCandidates
                + ", pairingCode=<redacted>]";
    }

    static List<WearEndpointRegistry.Endpoint> unique(
            List<WearEndpointRegistry.Endpoint> candidates) {
        List<WearEndpointRegistry.Endpoint> result = new ArrayList<>();
        Set<String> seen = new HashSet<>();
        for (WearEndpointRegistry.Endpoint candidate : candidates) {
            if (candidate != null && seen.add(candidate.host() + ":" + candidate.port())) {
                result.add(candidate);
            }
        }
        return List.copyOf(result);
    }

    private static WearEndpointRegistry.Endpoint endpoint(String name, String host, int port) {
        String safeHost = host == null ? "" : host.trim();
        return safeHost.isBlank() || port <= 0 || port > 65_535 ? null
                : new WearEndpointRegistry.Endpoint(name, safeHost, port, 0);
    }
}
