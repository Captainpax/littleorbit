package com.littleorbit.mobile;

import android.os.Build;
import java.io.File;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.lang.reflect.Proxy;
import java.util.Collections;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicReference;
import javax.inject.Inject;
import javax.inject.Singleton;
import kotlin.ResultKt;
import kotlin.Unit;
import kotlin.coroutines.Continuation;
import kotlin.coroutines.CoroutineContext;
import kotlin.coroutines.EmptyCoroutineContext;
import kotlin.coroutines.intrinsics.IntrinsicsKt;

/** Java 17 reflection boundary around Kadb's Java 21-published Android artifact. */
@Singleton
public final class KadbWatchClient {
    private static final AtomicBoolean CONFIGURED = new AtomicBoolean();
    private final EncryptedKadbPrivateKeyStore keys;

    /** Configures Kadb with an encrypted private-key adapter and prepares its identity. */
    @Inject
    public KadbWatchClient(EncryptedKadbPrivateKeyStore keys) {
        this.keys = keys;
        try {
            if (CONFIGURED.compareAndSet(false, true)) configure();
            invoke(cert(), "ensureReady", new Class<?>[0]);
        } catch (Exception failure) {
            throw new IllegalStateException("Could not initialize watch authorization", failure);
        }
    }

    /** Pairs the remembered host identity using the watch's short-lived code. */
    public void pair(String host, int port, String code) throws Exception {
        CountDownLatch finished = new CountDownLatch(1);
        AtomicReference<Throwable> failure = new AtomicReference<>();
        Continuation<Unit> continuation = new Continuation<>() {
            @Override public CoroutineContext getContext() { return EmptyCoroutineContext.INSTANCE; }
            @Override public void resumeWith(Object result) {
                try { ResultKt.throwOnFailure(result); }
                catch (Throwable invalid) { failure.set(invalid); }
                finally { finished.countDown(); }
            }
        };
        Class<?> kadb = Class.forName("com.flyfishxu.kadb.Kadb");
        Object companion = kadb.getField("Companion").get(null);
        Method pair = companion.getClass().getMethod(
                "pair", String.class, int.class, String.class, String.class, Continuation.class);
        Object immediate = unwrap(() -> pair.invoke(
                companion, host, port, code, "Little Orbit on " + Build.MODEL, continuation));
        if (immediate != IntrinsicsKt.getCOROUTINE_SUSPENDED()) finished.countDown();
        if (!finished.await(30, TimeUnit.SECONDS)) throw new Exception("Pairing timed out");
        if (failure.get() != null) throw new Exception("Pairing failed", failure.get());
    }

    /** Connects to one endpoint and returns privacy-safe compatibility properties. */
    public Device connectAndInspect(String host, int port) throws Exception {
        Object client = create(host, port, 30_000);
        try {
            if (!check(client)) throw new Exception("Watch connection failed");
            String model = shell(client, "getprop ro.product.model");
            String sdk = shell(client, "getprop ro.build.version.sdk");
            String patch = shell(client, "getprop ro.build.version.security_patch");
            String traits = shell(client, "getprop ro.build.characteristics");
            String packages = shell(client, "dumpsys package com.littleorbit.mobile");
            return new Device(model, number(sdk), patch, installedVersion(packages), traits);
        } finally { close(client); }
    }

    /** Sends the preverified artifact through package manager without downgrade flags. */
    public void install(String host, int port, File apk) throws Exception {
        Object client = create(host, port, 60_000);
        try {
            if (!check(client)) throw new Exception("Watch connection failed");
            invoke(client, "install", new Class<?>[] {File.class, String[].class}, apk,
                    new String[] {"-r"});
        } finally { close(client); }
    }

    /** Removes the saved ADB authorization identity from this phone. */
    public boolean forget() {
        try { invoke(cert(), "clear", new Class<?>[0]); }
        catch (Exception ignored) {
            try { keys.clear(); }
            catch (IllegalStateException unavailable) { return false; }
        }
        return !keys.isRemembered();
    }

    private void configure() throws Exception {
        Class<?> storeType = Class.forName("com.flyfishxu.kadb.cert.KadbPrivateKeyStore");
        Object adapter = Proxy.newProxyInstance(
                storeType.getClassLoader(), new Class<?>[] {storeType}, (proxy, method, args) -> {
                    return switch (method.getName()) {
                        case "readPrivateKeyPem" -> keys.readPrivateKeyPem();
                        case "writePrivateKeyPemAtomic" -> { keys.writePrivateKeyPemAtomic((byte[]) args[0]); yield null; }
                        case "clear" -> { keys.clear(); yield null; }
                        default -> throw new UnsupportedOperationException(method.getName());
                    };
                });
        Class<?> policyType = Class.forName("com.flyfishxu.kadb.cert.KadbCertPolicy");
        invoke(cert(), "configure",
                new Class<?>[] {storeType, policyType, java.util.List.class},
                adapter, policyType.getConstructor().newInstance(), Collections.emptyList());
    }

    private static Object cert() throws Exception {
        return Class.forName("com.flyfishxu.kadb.cert.KadbCert").getField("INSTANCE").get(null);
    }

    private static Object create(String host, int port, int socketTimeout) throws Exception {
        Class<?> type = Class.forName("com.flyfishxu.kadb.Kadb");
        return type.getConstructor(String.class, int.class, int.class, int.class)
                .newInstance(host, port, 10_000, socketTimeout);
    }

    private static boolean check(Object client) throws Exception {
        return (boolean) invoke(client, "connectionCheck", new Class<?>[0]);
    }

    private static String shell(Object client, String command) throws Exception {
        Object response = invoke(client, "shell", new Class<?>[] {String.class}, command);
        int exit = (int) invoke(response, "getExitCode", new Class<?>[0]);
        if (exit != 0) throw new Exception("Watch property query failed");
        return ((String) invoke(response, "getOutput", new Class<?>[0])).trim();
    }

    private static Object invoke(Object receiver, String name, Class<?>[] types, Object... args)
            throws Exception {
        Method method = receiver.getClass().getMethod(name, types);
        return unwrap(() -> method.invoke(receiver, args));
    }

    private static Object unwrap(ReflectiveCall call) throws Exception {
        try { return call.run(); }
        catch (InvocationTargetException wrapped) {
            Throwable cause = wrapped.getCause();
            if (cause instanceof Exception exception) throw exception;
            throw new Exception("ADB operation failed", cause);
        }
    }

    private static void close(Object client) {
        try { ((AutoCloseable) client).close(); }
        catch (Exception ignored) { /* Socket is already closed. */ }
    }

    private static int installedVersion(String value) {
        java.util.regex.Matcher match = java.util.regex.Pattern
                .compile("versionCode=(\\d+)").matcher(value);
        return match.find() ? number(match.group(1)) : 0;
    }

    private static int number(String value) {
        try { return Integer.parseInt(value.trim()); }
        catch (NumberFormatException invalid) { return 0; }
    }

    /** Privacy-safe directory and compatibility data read from the selected watch. */
    public record Device(String model, int sdk, String securityPatch, int installedVersion,
            String characteristics) {
        /** Returns true only for a watch build characteristic. */
        public boolean isWatch() { return characteristics != null && characteristics.contains("watch"); }
    }

    @FunctionalInterface private interface ReflectiveCall { Object run() throws Exception; }
}
