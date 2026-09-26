package com.littleorbit.mobile;

import java.net.ConnectException;
import java.net.NoRouteToHostException;
import java.net.SocketTimeoutException;
import java.net.UnknownHostException;
import java.util.HashSet;
import java.util.Locale;
import java.util.Set;
import javax.net.ssl.SSLException;

/** A privacy-safe wireless-ADB failure that never retains endpoint or pairing-code text. */
final class WatchAdbException extends Exception {
    enum Operation { PAIR, CONNECT, INSPECT, INSTALL, REMOVE }

    enum Reason {
        ADDRESS_INVALID,
        ENDPOINT_UNREACHABLE,
        TIMED_OUT,
        TLS_RUNTIME_UNAVAILABLE,
        PAIRING_REJECTED,
        AUTHORIZATION_REJECTED,
        DEVICE_QUERY_FAILED,
        INSTALL_REJECTED,
        INTERRUPTED,
        UNKNOWN
    }

    private final Operation operation;
    private final Reason reason;

    WatchAdbException(Operation operation, Reason reason) {
        super(codeFor(operation, reason));
        this.operation = operation;
        this.reason = reason;
    }

    Operation operation() { return operation; }

    Reason reason() { return reason; }

    String diagnosticCode() { return getMessage(); }

    static WatchAdbException classify(Operation operation, Throwable failure) {
        if (failure instanceof WatchAdbException known) return known;
        Set<Throwable> visited = new HashSet<>();
        for (Throwable current = failure; current != null && visited.add(current);
                current = current.getCause()) {
            Reason reason = classifyOne(operation, current);
            if (reason != null) return new WatchAdbException(operation, reason);
        }
        return new WatchAdbException(operation, Reason.UNKNOWN);
    }

    private static Reason classifyOne(Operation operation, Throwable failure) {
        if (failure instanceof UnknownHostException || failure instanceof IllegalArgumentException) {
            return Reason.ADDRESS_INVALID;
        }
        if (failure instanceof ConnectException || failure instanceof NoRouteToHostException) {
            return Reason.ENDPOINT_UNREACHABLE;
        }
        if (failure instanceof SocketTimeoutException) return Reason.TIMED_OUT;
        String type = failure.getClass().getName();
        String message = String.valueOf(failure.getMessage()).toLowerCase(Locale.ROOT);
        if (type.endsWith("AdbPairAuthException")) return Reason.AUTHORIZATION_REJECTED;
        if (isTlsRuntimeFailure(failure, type, message)) return Reason.TLS_RUNTIME_UNAVAILABLE;
        if (operation == Operation.PAIR && isPairingRejection(message)) {
            return Reason.PAIRING_REJECTED;
        }
        if (operation == Operation.INSTALL && message.contains("install_failed")) {
            return Reason.INSTALL_REJECTED;
        }
        return null;
    }

    private static boolean isTlsRuntimeFailure(Throwable failure, String type, String message) {
        if ((type.contains("ClassNotFound") || type.contains("NoSuchMethod")
                || type.contains("IllegalAccess") || type.contains("UnsatisfiedLink"))
                && (message.contains("conscrypt") || message.contains("openssl")
                || message.contains("exportkeyingmaterial"))) {
            return true;
        }
        return failure instanceof SSLException && (message.contains("conscrypt")
                || message.contains("exportkeyingmaterial") || failure.getCause() != null);
    }

    private static boolean isPairingRejection(String message) {
        return message.contains("exchanging message") || message.contains("peer info")
                || message.contains("pairing failed") || message.contains("connection closed");
    }

    private static String codeFor(Operation operation, Reason reason) {
        String prefix = switch (operation) {
            case PAIR -> "WPAIR";
            case CONNECT -> "WCONN";
            case INSPECT -> "WINFO";
            case INSTALL -> "WINST";
            case REMOVE -> "WREMV";
        };
        return prefix + "-" + String.format(Locale.ROOT, "%02d", reason.ordinal() + 1);
    }
}
