package com.littleorbit.mobile;

import android.os.Handler;
import android.os.Looper;

/** Debounces note edits while guaranteeing a bounded continuous-typing flush. */
final class NoteAutosaveScheduler {
    static final long IDLE_MILLIS = 800L;
    static final long MAX_DIRTY_MILLIS = 5_000L;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private final Runnable save;
    private final Runnable idle = this::runSave;
    private final Runnable maximum = this::runSave;
    private boolean maximumScheduled;

    NoteAutosaveScheduler(Runnable save) {
        this.save = save;
    }

    void edited() {
        handler.removeCallbacks(idle);
        handler.postDelayed(idle, IDLE_MILLIS);
        if (maximumScheduled) return;
        maximumScheduled = true;
        handler.postDelayed(maximum, MAX_DIRTY_MILLIS);
    }

    void flush() {
        boolean pending = maximumScheduled || handler.hasCallbacks(idle);
        cancel();
        if (pending) save.run();
    }

    void cancel() {
        handler.removeCallbacks(idle);
        handler.removeCallbacks(maximum);
        maximumScheduled = false;
    }

    private void runSave() {
        cancel();
        save.run();
    }
}
