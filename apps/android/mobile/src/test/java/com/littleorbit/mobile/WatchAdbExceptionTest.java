package com.littleorbit.mobile;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;

import java.net.ConnectException;
import javax.net.ssl.SSLException;
import org.junit.Test;

/** Verifies safe diagnostic classification without retaining sensitive exception text. */
public final class WatchAdbExceptionTest {
    @Test public void classifiesNestedConnectionFailureWithoutEndpointText() {
        Exception failure = new Exception("wrapper",
                new ConnectException("failed to connect to 192.0.2.4:41234"));

        WatchAdbException result = WatchAdbException.classify(
                WatchAdbException.Operation.CONNECT, failure);

        assertEquals(WatchAdbException.Reason.ENDPOINT_UNREACHABLE, result.reason());
        assertEquals("WCONN-02", result.diagnosticCode());
        assertFalse(result.toString().contains("192.0.2.4"));
    }

    @Test public void distinguishesTlsRuntimeFromRejectedCode() {
        WatchAdbException runtime = WatchAdbException.classify(
                WatchAdbException.Operation.PAIR,
                new SSLException(new NoSuchMethodException("exportKeyingMaterial")));
        WatchAdbException rejected = WatchAdbException.classify(
                WatchAdbException.Operation.PAIR,
                new Exception("Exchanging message wasn't successful"));

        assertEquals(WatchAdbException.Reason.TLS_RUNTIME_UNAVAILABLE, runtime.reason());
        assertEquals(WatchAdbException.Reason.PAIRING_REJECTED, rejected.reason());
    }

    @Test public void classifiesKadbTrustFailureByType() {
        WatchAdbException result = WatchAdbException.classify(
                WatchAdbException.Operation.CONNECT, new FakeAdbPairAuthException());

        assertEquals(WatchAdbException.Reason.AUTHORIZATION_REJECTED, result.reason());
        assertEquals("WCONN-06", result.diagnosticCode());
    }

    @Test public void doesNotMislabelUnrelatedReflectionFailureAsTls() {
        WatchAdbException result = WatchAdbException.classify(
                WatchAdbException.Operation.INSTALL,
                new NoSuchMethodException("installMultiple"));

        assertEquals(WatchAdbException.Reason.UNKNOWN, result.reason());
    }

    private static final class FakeAdbPairAuthException extends Exception {}
}
