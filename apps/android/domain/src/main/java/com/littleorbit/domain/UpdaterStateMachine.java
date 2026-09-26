package com.littleorbit.domain;

import java.util.Set;

/** Deterministic, persistence-friendly updater phases and retry transitions. */
public final class UpdaterStateMachine {
    public static final String IDLE = "idle";
    public static final String CHECKING = "checking";
    public static final String AVAILABLE = "available";
    public static final String DEFERRED = "deferred";
    public static final String DOWNLOADING = "downloading";
    public static final String PAUSED = "paused";
    public static final String VERIFYING = "verifying";
    public static final String PERMISSION_REQUIRED = "permission_required";
    public static final String INSTALLING = "installing";
    public static final String AWAITING_CONFIRMATION = "awaiting_confirmation";
    public static final String RETRY_DOWNLOAD = "retry_download";
    public static final String RETRY_INSTALL = "retry_install";
    public static final String INSTALLED = "installed";
    public static final String FAILED = "failed";

    private static final Set<String> PHASES = Set.of(
            IDLE, CHECKING, AVAILABLE, DEFERRED, DOWNLOADING, PAUSED, VERIFYING,
            PERMISSION_REQUIRED, INSTALLING, AWAITING_CONFIRMATION,
            RETRY_DOWNLOAD, RETRY_INSTALL, INSTALLED, FAILED);
    private static final Set<String> RESUMABLE_PHASES = Set.of(
            DOWNLOADING, PAUSED, VERIFYING, PERMISSION_REQUIRED, INSTALLING,
            AWAITING_CONFIRMATION, RETRY_DOWNLOAD, RETRY_INSTALL);

    private Snapshot current;

    /** Creates an idle updater. */
    public UpdaterStateMachine() {
        this(new Snapshot(IDLE, "", "", 0, 0, false));
    }

    /** Restores an allowlisted state while discarding untrusted phase strings. */
    public UpdaterStateMachine(Snapshot restored) {
        current = PHASES.contains(restored.phase())
                ? restored
                : new Snapshot(IDLE, "", "", 0, 0, false);
    }

    /** Returns the immutable state suitable for persistence and UI rendering. */
    public synchronized Snapshot snapshot() {
        return current;
    }

    /** Returns whether Android-owned work must survive an activity or process restart. */
    public synchronized boolean hasResumableWork() {
        return RESUMABLE_PHASES.contains(current.phase());
    }

    /** Preserves active work for identical bytes while allowing required status to escalate. */
    public synchronized Snapshot selectPreservingWork(String releaseId, boolean required) {
        if (!releaseId.equals(current.releaseId()) || !hasResumableWork()) {
            return select(releaseId, required);
        }
        current = new Snapshot(
                current.phase(),
                current.releaseId(),
                current.failureCode(),
                current.downloadedBytes(),
                current.totalBytes(),
                current.required() || required);
        return current;
    }

    public synchronized Snapshot checking() { return set(CHECKING, "", 0, 0, false); }
    public synchronized Snapshot available(boolean required) {
        return set(AVAILABLE, "", 0, 0, required);
    }
    public synchronized Snapshot deferred() { return set(DEFERRED, "", 0, 0, false); }
    public synchronized Snapshot downloading(long bytes, long total) {
        return set(DOWNLOADING, "", bytes, total, current.required());
    }
    public synchronized Snapshot paused(String code, long bytes, long total) {
        return set(PAUSED, code, bytes, total, current.required());
    }
    public synchronized Snapshot verifying(long bytes) {
        return set(VERIFYING, "", bytes, bytes, current.required());
    }
    public synchronized Snapshot permissionRequired(long bytes) {
        return set(PERMISSION_REQUIRED, "", bytes, bytes, current.required());
    }
    public synchronized Snapshot installing(long bytes) {
        return set(INSTALLING, "", bytes, bytes, current.required());
    }
    public synchronized Snapshot awaitingConfirmation(long bytes) {
        return set(AWAITING_CONFIRMATION, "", bytes, bytes, current.required());
    }
    public synchronized Snapshot retryDownload(String code, long bytes, long total) {
        return set(RETRY_DOWNLOAD, code, bytes, total, current.required());
    }
    public synchronized Snapshot retryInstall(String code, long bytes) {
        return set(RETRY_INSTALL, code, bytes, bytes, current.required());
    }
    public synchronized Snapshot installed(long bytes) {
        return set(INSTALLED, "", bytes, bytes, false);
    }
    public synchronized Snapshot failed(String code) {
        return set(FAILED, code, current.downloadedBytes(), current.totalBytes(), current.required());
    }

    private Snapshot set(String phase, String code, long bytes, long total, boolean required) {
        current = new Snapshot(
                phase,
                current.releaseId(),
                code == null ? "" : code,
                Math.max(0, bytes),
                Math.max(0, total),
                required);
        return current;
    }

    /** Associates all later transitions with the exact release bytes being handled. */
    public synchronized Snapshot select(String releaseId, boolean required) {
        current = new Snapshot(AVAILABLE, releaseId, "", 0, 0, required);
        return current;
    }

    /** Minimal state whose fields contain no URL, filesystem path, or server response. */
    public record Snapshot(
            String phase,
            String releaseId,
            String failureCode,
            long downloadedBytes,
            long totalBytes,
            boolean required) {}
}
