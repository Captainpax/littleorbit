package com.littleorbit.mobile;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Keeps live DNS-SD records and selects pairing and TLS endpoints from one device. */
final class WearEndpointRegistry {
    enum Kind { PAIRING, CONNECT }

    record Endpoint(String serviceName, String host, int port, long networkHandle) {
        boolean matchesDevice(Endpoint other) {
            if (other == null || !host.equals(other.host)) return false;
            return networkHandle == 0 || other.networkHandle == 0
                    || networkHandle == other.networkHandle;
        }
    }

    record Snapshot(Endpoint pairing, Endpoint connect, List<Endpoint> connectCandidates) {
        static Snapshot empty() { return new Snapshot(null, null, List.of()); }
    }

    private final Map<String, Endpoint> pairing = new LinkedHashMap<>();
    private final Map<String, Endpoint> connect = new LinkedHashMap<>();

    synchronized Snapshot upsert(Kind kind, Endpoint endpoint) {
        Map<String, Endpoint> target = records(kind);
        String key = key(endpoint.serviceName, endpoint.networkHandle);
        target.remove(key);
        target.put(key, endpoint);
        return snapshot();
    }

    synchronized Snapshot remove(Kind kind, String serviceName, long networkHandle) {
        records(kind).remove(key(serviceName, networkHandle));
        return snapshot();
    }

    synchronized Snapshot clear() {
        pairing.clear();
        connect.clear();
        return Snapshot.empty();
    }

    synchronized Snapshot snapshot() {
        Endpoint selectedPairing = newest(pairing);
        List<Endpoint> candidates = newestFirst(connect);
        Endpoint selectedConnect = candidates.stream()
                .filter(endpoint -> endpoint.matchesDevice(selectedPairing))
                .findFirst().orElse(null);
        return new Snapshot(selectedPairing, selectedConnect, List.copyOf(candidates));
    }

    private Map<String, Endpoint> records(Kind kind) {
        return kind == Kind.PAIRING ? pairing : connect;
    }

    private static String key(String serviceName, long networkHandle) {
        return networkHandle + "|" + serviceName;
    }

    private static Endpoint newest(Map<String, Endpoint> values) {
        Endpoint newest = null;
        for (Endpoint value : values.values()) newest = value;
        return newest;
    }

    private static List<Endpoint> newestFirst(Map<String, Endpoint> values) {
        List<Endpoint> result = new ArrayList<>(values.values());
        java.util.Collections.reverse(result);
        return result;
    }
}
