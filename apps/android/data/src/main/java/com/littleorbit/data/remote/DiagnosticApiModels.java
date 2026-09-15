package com.littleorbit.data.remote;

import com.squareup.moshi.Json;
import java.util.List;

/** Content-free Android crash identifiers accepted by the opt-in diagnostics endpoint. */
public final class DiagnosticApiModels {
    private DiagnosticApiModels() {}

    /** One Little Orbit method location without source paths or runtime values. */
    public static final class Frame {
        @Json(name = "class_name") public final String className;
        @Json(name = "method_name") public final String methodName;
        @Json(name = "line_number") public final Integer lineNumber;

        /** Creates one validated app-owned frame. */
        public Frame(String className, String methodName, Integer lineNumber) {
            this.className = className;
            this.methodName = methodName;
            this.lineNumber = lineNumber;
        }
    }

    /** Explicitly consented report containing only code identifiers. */
    public static final class Report {
        public final boolean consent;
        @Json(name = "installation_id") public final String installationId;
        @Json(name = "app_version_code") public final int appVersionCode;
        @Json(name = "app_version_name") public final String appVersionName;
        @Json(name = "exception_chain") public final List<String> exceptionChain;
        public final List<Frame> frames;
        @Json(name = "occurred_at") public final String occurredAt;

        /** Creates one bounded report after local sanitization. */
        public Report(
                String installationId,
                int appVersionCode,
                String appVersionName,
                List<String> exceptionChain,
                List<Frame> frames,
                String occurredAt) {
            this.consent = true;
            this.installationId = installationId;
            this.appVersionCode = appVersionCode;
            this.appVersionName = appVersionName;
            this.exceptionChain = List.copyOf(exceptionChain);
            this.frames = List.copyOf(frames);
            this.occurredAt = occurredAt;
        }
    }
}
