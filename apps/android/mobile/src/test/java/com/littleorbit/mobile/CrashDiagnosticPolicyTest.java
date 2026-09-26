package com.littleorbit.mobile;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;

import java.time.Instant;
import org.junit.Test;

public final class CrashDiagnosticPolicyTest {
    @Test
    public void captureDropsMessagesPathsAndNonAppFrames() {
        IllegalStateException failure = new IllegalStateException(
                "secret note /sdcard/private.jpg token=abc");
        failure.setStackTrace(new StackTraceElement[] {
                new StackTraceElement("com.littleorbit.mobile.QuizActivity", "render", "QuizActivity.java", 42),
                new StackTraceElement("third.party.Library", "invoke", "Library.java", 9)
        });

        CrashDiagnosticPolicy.Snapshot result = CrashDiagnosticPolicy.capture(
                failure, 19, "1.0.0-rc.14", Instant.parse("2026-09-14T12:00:00Z"));

        assertTrue(CrashDiagnosticPolicy.valid(result));
        assertEquals(1, result.exceptionChain().size());
        assertEquals("java.lang.IllegalStateException", result.exceptionChain().get(0));
        assertEquals(1, result.frames().size());
        assertEquals("com.littleorbit.mobile.QuizActivity", result.frames().get(0).className);
        assertEquals("render", result.frames().get(0).methodName);
        assertEquals(Integer.valueOf(42), result.frames().get(0).lineNumber);
        String serialized = result.toString();
        assertFalse(serialized.contains("secret"));
        assertFalse(serialized.contains("sdcard"));
        assertFalse(serialized.contains("token"));
    }

    @Test
    public void captureOmitsUnknownLinesAndRejectsNoAppFrame() {
        RuntimeException failure = new RuntimeException("private value");
        failure.setStackTrace(new StackTraceElement[] {
                new StackTraceElement("com.littleorbit.data.Sync", "run", null, -1)
        });
        CrashDiagnosticPolicy.Snapshot result = CrashDiagnosticPolicy.capture(
                failure, 19, "1.0.0-rc.14", Instant.parse("2026-09-14T12:00:00Z"));
        assertTrue(CrashDiagnosticPolicy.valid(result));
        assertNull(result.frames().get(0).lineNumber);

        failure.setStackTrace(new StackTraceElement[] {
                new StackTraceElement("vendor.Library", "run", "Library.java", 4)
        });
        assertFalse(CrashDiagnosticPolicy.valid(CrashDiagnosticPolicy.capture(
                failure, 19, "1.0.0-rc.14", Instant.parse("2026-09-14T12:00:00Z"))));
    }
}
