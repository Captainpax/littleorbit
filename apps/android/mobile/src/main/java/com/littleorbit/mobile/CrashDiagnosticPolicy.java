package com.littleorbit.mobile;

import com.littleorbit.data.remote.DiagnosticApiModels;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.regex.Pattern;

/** Converts a crash into bounded code identifiers without retaining runtime content. */
final class CrashDiagnosticPolicy {
    private static final int MAX_CAUSES = 8;
    private static final int MAX_FRAMES = 64;
    private static final Pattern CLASS_NAME = Pattern.compile(
            "^(?:java|android|androidx|com\\.littleorbit)\\.[A-Za-z_$][A-Za-z0-9_.$]{0,150}$");
    private static final Pattern APP_CLASS = Pattern.compile(
            "^com\\.littleorbit\\.[A-Za-z_$][A-Za-z0-9_.$]{0,140}$");
    private static final Pattern METHOD = Pattern.compile(
            "^[A-Za-z_$<>][A-Za-z0-9_$<>]{0,119}$");

    private CrashDiagnosticPolicy() {}

    /** Returns a report candidate containing no messages, values, or source paths. */
    static Snapshot capture(Throwable failure, int versionCode, String versionName, Instant occurredAt) {
        List<String> causes = causes(failure);
        List<DiagnosticApiModels.Frame> frames = frames(failure);
        return new Snapshot(versionCode, safeVersion(versionName), causes, frames, occurredAt.toString());
    }

    /** Returns whether a stored report still satisfies the wire privacy boundary. */
    static boolean valid(Snapshot value) {
        return value.versionCode() > 0
                && safeVersion(value.versionName()).equals(value.versionName())
                && value.exceptionChain().size() >= 1
                && value.exceptionChain().size() <= MAX_CAUSES
                && value.exceptionChain().stream().allMatch(CrashDiagnosticPolicy::allowedException)
                && value.frames().size() >= 1
                && value.frames().size() <= MAX_FRAMES
                && value.frames().stream().allMatch(CrashDiagnosticPolicy::allowedFrame)
                && parseInstant(value.occurredAt());
    }

    private static List<String> causes(Throwable failure) {
        List<String> values = new ArrayList<>();
        Throwable current = failure;
        while (current != null && values.size() < MAX_CAUSES) {
            String name = current.getClass().getName();
            if (allowedException(name)) values.add(name);
            current = current.getCause();
        }
        if (values.isEmpty()) values.add("java.lang.RuntimeException");
        return List.copyOf(values);
    }

    private static List<DiagnosticApiModels.Frame> frames(Throwable failure) {
        List<DiagnosticApiModels.Frame> values = new ArrayList<>();
        Throwable current = failure;
        while (current != null && values.size() < MAX_FRAMES) {
            for (StackTraceElement frame : current.getStackTrace()) {
                if (values.size() == MAX_FRAMES) break;
                DiagnosticApiModels.Frame safe = frame(frame);
                if (safe != null) values.add(safe);
            }
            current = current.getCause();
        }
        return List.copyOf(values);
    }

    private static DiagnosticApiModels.Frame frame(StackTraceElement value) {
        String className = value.getClassName();
        String methodName = value.getMethodName();
        if (!APP_CLASS.matcher(className).matches() || !METHOD.matcher(methodName).matches()) {
            return null;
        }
        Integer line = value.getLineNumber() > 0 && value.getLineNumber() <= 1_000_000
                ? value.getLineNumber() : null;
        return new DiagnosticApiModels.Frame(className, methodName, line);
    }

    private static boolean allowedException(String value) {
        return value != null && CLASS_NAME.matcher(value).matches();
    }

    private static boolean allowedFrame(DiagnosticApiModels.Frame value) {
        return value != null
                && APP_CLASS.matcher(value.className).matches()
                && METHOD.matcher(value.methodName).matches()
                && (value.lineNumber == null
                        || value.lineNumber >= 1 && value.lineNumber <= 1_000_000);
    }

    private static String safeVersion(String value) {
        return value != null && value.matches("[0-9A-Za-z._-]{1,40}") ? value : "unknown";
    }

    private static boolean parseInstant(String value) {
        try {
            Instant.parse(value);
            return true;
        } catch (RuntimeException invalid) {
            return false;
        }
    }

    /** Immutable locally sanitized crash record. */
    record Snapshot(
            int versionCode,
            String versionName,
            List<String> exceptionChain,
            List<DiagnosticApiModels.Frame> frames,
            String occurredAt) {}
}
