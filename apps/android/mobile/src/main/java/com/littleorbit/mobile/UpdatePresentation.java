package com.littleorbit.mobile;

import com.littleorbit.domain.ReleaseUpdate;
import com.littleorbit.domain.UpdatePolicy;
import com.littleorbit.domain.UpdaterStateMachine;

/** Immutable updater state rendered by phone UI without exposing local file paths. */
public record UpdatePresentation(
        ReleaseUpdate release,
        UpdatePolicy.Decision decision,
        UpdaterStateMachine.Snapshot progress) {

    /** Returns whether the current release must interrupt ordinary navigation. */
    public boolean required() {
        return decision == UpdatePolicy.Decision.REQUIRED;
    }

    /** Returns an integer progress percentage only when Android reports a total. */
    public int percent() {
        if (progress.totalBytes() <= 0) return 0;
        return (int) Math.min(100, progress.downloadedBytes() * 100 / progress.totalBytes());
    }
}
