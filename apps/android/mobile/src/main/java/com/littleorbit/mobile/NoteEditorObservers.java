package com.littleorbit.mobile;

import android.os.Handler;
import android.os.Looper;
import android.text.Editable;
import android.text.TextWatcher;
import android.widget.EditText;
import java.util.function.BooleanSupplier;

/** Coalesces editor callbacks without treating programmatic patches as user edits. */
final class NoteEditorObservers {
    private final EditText body;
    private final EditText title;
    private final BooleanSupplier rendering;
    private final Handler pending = new Handler(Looper.getMainLooper());

    NoteEditorObservers(EditText body, EditText title, BooleanSupplier rendering) {
        this.body = body;
        this.title = title;
        this.rendering = rendering;
    }

    void bind(Runnable bodyChanged, Runnable titleChanged) {
        body.addTextChangedListener(watcher(bodyChanged));
        title.addTextChangedListener(watcher(titleChanged));
    }

    void schedule(Runnable task, long delayMillis) {
        pending.removeCallbacks(task);
        pending.postDelayed(task, delayMillis);
    }

    void cancel(Runnable... tasks) {
        for (Runnable task : tasks) pending.removeCallbacks(task);
    }

    void clear() {
        pending.removeCallbacksAndMessages(null);
    }

    private TextWatcher watcher(Runnable changed) {
        return new TextWatcher() {
            @Override public void beforeTextChanged(
                    CharSequence value, int start, int count, int after) {}
            @Override public void onTextChanged(
                    CharSequence value, int start, int before, int count) {}
            @Override public void afterTextChanged(Editable value) {
                if (!rendering.getAsBoolean()) changed.run();
            }
        };
    }
}
