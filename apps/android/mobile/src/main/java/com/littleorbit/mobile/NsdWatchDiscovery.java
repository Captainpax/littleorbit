package com.littleorbit.mobile;

import android.content.Context;
import android.net.Network;
import android.net.nsd.NsdManager;
import android.net.nsd.NsdServiceInfo;
import android.os.Build;
import android.os.ext.SdkExtensions;
import androidx.annotation.RequiresApi;
import androidx.annotation.RequiresExtension;
import dagger.hilt.android.qualifiers.ApplicationContext;
import java.net.Inet4Address;
import java.net.InetAddress;
import java.util.ArrayDeque;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Queue;
import java.util.concurrent.Executor;
import javax.inject.Inject;
import javax.inject.Singleton;

/** Discovers and continuously tracks wireless-debugging services on the local network. */
@Singleton
public final class NsdWatchDiscovery {
    private static final String PAIRING = "_adb-tls-pairing._tcp.";
    private static final String CONNECT = "_adb-tls-connect._tcp.";
    private final NsdManager manager;
    private final Executor callbackExecutor;

    /** Creates the platform DNS-SD boundary. */
    @Inject
    public NsdWatchDiscovery(@ApplicationContext Context context) {
        manager = (NsdManager) context.getSystemService(Context.NSD_SERVICE);
        callbackExecutor = context.getMainExecutor();
    }

    /** Starts both discoveries and returns a session that must be closed. */
    public Session discover(Listener listener) {
        Session session = new Session(manager, callbackExecutor, listener);
        try {
            session.start();
            return session;
        } catch (RuntimeException failure) {
            session.close();
            throw failure;
        }
    }

    /** Receives immutable endpoint snapshots and privacy-safe discovery failures. */
    public interface Listener {
        void onUpdate(WearEndpointRegistry.Snapshot snapshot);
        void onFailure();
    }

    /** Owns discovery, modern service tracking, and serialized legacy resolution. */
    public static final class Session implements AutoCloseable {
        private final NsdManager manager;
        private final Executor executor;
        private final Listener listener;
        private final WearEndpointRegistry registry = new WearEndpointRegistry();
        private final Queue<Candidate> legacyQueue = new ArrayDeque<>();
        private final Map<String, NsdManager.ServiceInfoCallback> callbacks = new HashMap<>();
        private NsdManager.DiscoveryListener pairing;
        private NsdManager.DiscoveryListener connect;
        private boolean resolving;
        private boolean closed;

        Session(NsdManager manager, Executor executor, Listener listener) {
            this.manager = manager;
            this.executor = executor;
            this.listener = listener;
        }

        void start() {
            pairing = discovery(WearEndpointRegistry.Kind.PAIRING);
            connect = discovery(WearEndpointRegistry.Kind.CONNECT);
            manager.discoverServices(PAIRING, NsdManager.PROTOCOL_DNS_SD, pairing);
            manager.discoverServices(CONNECT, NsdManager.PROTOCOL_DNS_SD, connect);
        }

        private NsdManager.DiscoveryListener discovery(WearEndpointRegistry.Kind kind) {
            return new NsdManager.DiscoveryListener() {
                @Override public void onDiscoveryStarted(String type) {}
                @Override public void onDiscoveryStopped(String type) {}
                @Override public void onStopDiscoveryFailed(String type, int error) {}
                @Override public void onStartDiscoveryFailed(String type, int error) { failed(); }
                @Override public void onServiceFound(NsdServiceInfo service) { found(service, kind); }
                @Override public void onServiceLost(NsdServiceInfo service) { lost(service, kind); }
            };
        }

        private synchronized void found(NsdServiceInfo service, WearEndpointRegistry.Kind kind) {
            if (closed || service.getServiceName() == null) return;
            if (supportsServiceTracking()) track(service, kind);
            else enqueueLegacy(service, kind);
        }

        @RequiresApi(34)
        @RequiresExtension(extension = Build.VERSION_CODES.TIRAMISU, version = 7)
        private void track(NsdServiceInfo service, WearEndpointRegistry.Kind kind) {
            String key = callbackKey(service, kind);
            if (callbacks.containsKey(key)) return;
            NsdManager.ServiceInfoCallback callback = new NsdManager.ServiceInfoCallback() {
                @Override public void onServiceInfoCallbackRegistrationFailed(int errorCode) {
                    trackingFailed(key);
                }
                @Override public void onServiceUpdated(NsdServiceInfo info) { resolved(info, kind); }
                @Override public void onServiceLost() { removeTracked(key, service, kind); }
                @Override public void onServiceInfoCallbackUnregistered() {}
            };
            callbacks.put(key, callback);
            try { manager.registerServiceInfoCallback(service, executor, callback); }
            catch (RuntimeException failure) { trackingFailed(key); }
        }

        private synchronized void trackingFailed(String key) {
            callbacks.remove(key);
            failed();
        }

        private synchronized void lost(NsdServiceInfo service, WearEndpointRegistry.Kind kind) {
            if (closed) return;
            String key = callbackKey(service, kind);
            NsdManager.ServiceInfoCallback callback = callbacks.remove(key);
            unregister(callback);
            emit(registry.remove(kind, service.getServiceName(), networkHandle(service)));
        }

        private synchronized void removeTracked(String key, NsdServiceInfo service,
                WearEndpointRegistry.Kind kind) {
            callbacks.remove(key);
            if (!closed) emit(registry.remove(
                    kind, service.getServiceName(), networkHandle(service)));
        }

        private synchronized void enqueueLegacy(
                NsdServiceInfo service, WearEndpointRegistry.Kind kind) {
            legacyQueue.add(new Candidate(service, kind));
            resolveNext();
        }

        @SuppressWarnings("deprecation")
        private synchronized void resolveNext() {
            if (closed || resolving) return;
            Candidate candidate = legacyQueue.poll();
            if (candidate == null) return;
            resolving = true;
            manager.resolveService(candidate.service, new NsdManager.ResolveListener() {
                @Override public void onResolveFailed(NsdServiceInfo info, int error) {
                    legacyResolved(candidate, null);
                }
                @Override public void onServiceResolved(NsdServiceInfo info) {
                    legacyResolved(candidate, info);
                }
            });
        }

        private synchronized void legacyResolved(Candidate candidate, NsdServiceInfo info) {
            resolving = false;
            if (!closed && info != null) resolved(info, candidate.kind);
            resolveNext();
        }

        private synchronized void resolved(NsdServiceInfo info, WearEndpointRegistry.Kind kind) {
            WearEndpointRegistry.Endpoint endpoint = endpoint(info);
            if (!closed && endpoint != null) emit(registry.upsert(kind, endpoint));
        }

        private void emit(WearEndpointRegistry.Snapshot snapshot) { listener.onUpdate(snapshot); }

        private void failed() { if (!closed) listener.onFailure(); }

        @Override public synchronized void close() {
            if (closed) return;
            closed = true;
            legacyQueue.clear();
            stop(pairing);
            stop(connect);
            List<NsdManager.ServiceInfoCallback> active = List.copyOf(callbacks.values());
            callbacks.clear();
            for (NsdManager.ServiceInfoCallback callback : active) unregister(callback);
            registry.clear();
        }

        private void stop(NsdManager.DiscoveryListener value) {
            if (value == null) return;
            try { manager.stopServiceDiscovery(value); }
            catch (IllegalArgumentException ignored) { /* Android already stopped it. */ }
        }

        private void unregister(NsdManager.ServiceInfoCallback callback) {
            if (callback == null || Build.VERSION.SDK_INT < 34) return;
            try { manager.unregisterServiceInfoCallback(callback); }
            catch (IllegalArgumentException ignored) { /* Callback already ended. */ }
        }

        private static WearEndpointRegistry.Endpoint endpoint(NsdServiceInfo info) {
            InetAddress address = preferredAddress(info);
            String name = info.getServiceName();
            if (address == null || name == null || name.isBlank()
                    || info.getPort() <= 0 || info.getPort() > 65_535) return null;
            return new WearEndpointRegistry.Endpoint(
                    name, address.getHostAddress(), info.getPort(), networkHandle(info));
        }

        @SuppressWarnings("deprecation")
        private static InetAddress preferredAddress(NsdServiceInfo info) {
            if (Build.VERSION.SDK_INT < 34) return info.getHost();
            List<InetAddress> addresses = info.getHostAddresses();
            return addresses.stream().filter(value -> value instanceof Inet4Address)
                    .findFirst().orElse(addresses.isEmpty() ? null : addresses.get(0));
        }

        private static long networkHandle(NsdServiceInfo info) {
            Network network = Build.VERSION.SDK_INT >= 33 ? info.getNetwork() : null;
            return network == null ? 0 : network.getNetworkHandle();
        }

        private static String callbackKey(NsdServiceInfo info, WearEndpointRegistry.Kind kind) {
            return kind + "|" + networkHandle(info) + "|" + info.getServiceName();
        }

        private static boolean supportsServiceTracking() {
            return Build.VERSION.SDK_INT >= 34
                    && SdkExtensions.getExtensionVersion(Build.VERSION_CODES.TIRAMISU) >= 7;
        }

        private record Candidate(NsdServiceInfo service, WearEndpointRegistry.Kind kind) {}
    }
}
