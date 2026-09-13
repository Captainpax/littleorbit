package com.littleorbit.mobile;

import android.app.Activity;
import android.widget.TextView;
import com.littleorbit.data.repository.OrbitServiceException;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CompletionException;
import java.util.function.Consumer;

/** Delivers repository completion on an activity's UI thread without exposing secrets. */
final class AsyncUi {
    private AsyncUi() {}

    static <T> void observe(
            Activity activity,
            CompletableFuture<T> future,
            TextView status,
            Consumer<T> success) {
        future.whenComplete((value, failure) -> activity.runOnUiThread(() -> {
            if (activity.isDestroyed()) {
                return;
            }
            if (failure != null) {
                Throwable cause = failure instanceof CompletionException && failure.getCause() != null
                        ? failure.getCause()
                        : failure;
                boolean changed = cause instanceof OrbitServiceException error
                        && error.statusCode() == 409;
                status.setText(changed ? R.string.remote_change_conflict : R.string.request_failed);
                return;
            }
            status.setText("");
            success.accept(value);
        }));
    }
}
