package com.littleorbit.mobile;

import android.content.Context;
import android.net.nsd.NsdManager;
import android.net.nsd.NsdServiceInfo;
import dagger.hilt.android.qualifiers.ApplicationContext;
import java.net.InetAddress;
import javax.inject.Inject;
import javax.inject.Singleton;

/** Discovers Android wireless-debugging pairing and TLS endpoints on the local network. */
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

    /** Receives newly resolved endpoints without exposing unrelated service names. */
    public interface Listener {
        void onPairing(Endpoint endpoint);
        void onConnect(Endpoint endpoint);
        void onFailure();
    }

    /** Owns two DNS-SD listeners and stops them together. */
    public static final class Session implements AutoCloseable {
        private final NsdManager manager;
        private final Listener listener;
        private NsdManager.DiscoveryListener pairing;
        private NsdManager.DiscoveryListener connect;

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
                @Override public void onServiceFound(NsdServiceInfo service) { resolve(service, isPairing); }
            };
        }

        @SuppressWarnings("deprecation")
        private void resolve(NsdServiceInfo service, boolean isPairing) {
            manager.resolveService(service, new NsdManager.ResolveListener() {
                @Override public void onResolveFailed(NsdServiceInfo info, int error) {}
                @Override public void onServiceResolved(NsdServiceInfo info) {
                    InetAddress address = info.getHost();
                    if (address == null || info.getPort() <= 0) return;
                    Endpoint endpoint = new Endpoint(address.getHostAddress(), info.getPort());
                    if (isPairing) listener.onPairing(endpoint); else listener.onConnect(endpoint);
                }
            });
        }

        @Override public void close() {
            stop(pairing);
            stop(connect);
        }

        private void stop(NsdManager.DiscoveryListener value) {
            if (value == null) return;
            try { manager.stopServiceDiscovery(value); }
            catch (IllegalArgumentException ignored) { /* Discovery already stopped by Android. */ }
        }
    }
}
