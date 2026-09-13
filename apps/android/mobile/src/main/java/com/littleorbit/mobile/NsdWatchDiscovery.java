package com.littleorbit.mobile;

import android.content.Context;
import android.net.nsd.NsdManager;
import android.net.nsd.NsdServiceInfo;
import dagger.hilt.android.qualifiers.ApplicationContext;
import java.net.InetAddress;
import java.util.ArrayDeque;
import java.util.Queue;
import javax.inject.Inject;
import javax.inject.Singleton;

/** Discovers wireless-debugging endpoints while serializing legacy NSD resolution. */
@Singleton
public final class NsdWatchDiscovery {
    private static final String PAIRING = "_adb-tls-pairing._tcp.";
    private static final String CONNECT = "_adb-tls-connect._tcp.";
    private final NsdManager manager;

    /** Creates the platform DNS-SD boundary. */
    @Inject
    public NsdWatchDiscovery(@ApplicationContext Context context) {
        manager = (NsdManager) context.getSystemService(Context.NSD_SERVICE);
    }

    /** One resolved local socket endpoint. */
    public record Endpoint(String host, int port) {}

    /** Starts both discoveries and returns a session that must be closed. */
    public Session discover(Listener listener) {
        Session session = new Session(manager, listener);
        try {
            session.start();
            return session;
        } catch (RuntimeException failure) {
            session.close();
            throw failure;
        }
    }

    /** Receives endpoints without exposing service names or TXT records. */
    public interface Listener {
        void onPairing(Endpoint endpoint);
        void onConnect(Endpoint endpoint);
        void onFailure();
    }

    /** Owns discovery and a single-file resolver queue required on older Android releases. */
    public static final class Session implements AutoCloseable {
        private final NsdManager manager;
        private final Listener listener;
        private final Queue<Candidate> queue = new ArrayDeque<>();
        private NsdManager.DiscoveryListener pairing;
        private NsdManager.DiscoveryListener connect;
        private boolean resolving;
        private boolean closed;

        Session(NsdManager manager, Listener listener) {
            this.manager = manager;
            this.listener = listener;
        }

        void start() {
            pairing = discovery(true);
            connect = discovery(false);
            manager.discoverServices(PAIRING, NsdManager.PROTOCOL_DNS_SD, pairing);
            manager.discoverServices(CONNECT, NsdManager.PROTOCOL_DNS_SD, connect);
        }

        private NsdManager.DiscoveryListener discovery(boolean isPairing) {
            return new NsdManager.DiscoveryListener() {
                @Override public void onDiscoveryStarted(String type) {}
                @Override public void onServiceLost(NsdServiceInfo service) {}
                @Override public void onDiscoveryStopped(String type) {}
                @Override public void onStartDiscoveryFailed(String type, int error) {
                    listener.onFailure();
                }
                @Override public void onStopDiscoveryFailed(String type, int error) {}
                @Override public void onServiceFound(NsdServiceInfo service) {
                    enqueue(service, isPairing);
                }
            };
        }

        private synchronized void enqueue(NsdServiceInfo service, boolean isPairing) {
            if (closed) return;
            queue.add(new Candidate(service, isPairing));
            resolveNext();
        }

        @SuppressWarnings("deprecation")
        private synchronized void resolveNext() {
            if (closed || resolving) return;
            Candidate candidate = queue.poll();
            if (candidate == null) return;
            resolving = true;
            manager.resolveService(candidate.service, new NsdManager.ResolveListener() {
                @Override public void onResolveFailed(NsdServiceInfo info, int error) {
                    resolved(candidate, null);
                }
                @Override public void onServiceResolved(NsdServiceInfo info) {
                    resolved(candidate, info);
                }
            });
        }

        private synchronized void resolved(Candidate candidate, NsdServiceInfo info) {
            resolving = false;
            if (!closed && info != null) {
                InetAddress address = info.getHost();
                if (address != null && info.getPort() > 0) {
                    Endpoint endpoint = new Endpoint(address.getHostAddress(), info.getPort());
                    if (candidate.pairing) listener.onPairing(endpoint);
                    else listener.onConnect(endpoint);
                }
            }
            resolveNext();
        }

        @Override public synchronized void close() {
            closed = true;
            queue.clear();
            stop(pairing);
            stop(connect);
        }

        private void stop(NsdManager.DiscoveryListener value) {
            if (value == null) return;
            try { manager.stopServiceDiscovery(value); }
            catch (IllegalArgumentException ignored) { /* Android already stopped it. */ }
        }

        private record Candidate(NsdServiceInfo service, boolean pairing) {}
    }
}
