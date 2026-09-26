package com.littleorbit.wear;

import android.os.RemoteException;
import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.wear.watchface.complications.data.ComplicationData;
import androidx.wear.watchface.complications.data.ComplicationType;
import androidx.wear.watchface.complications.data.LongTextComplicationData;
import androidx.wear.watchface.complications.data.PlainComplicationText;
import androidx.wear.watchface.complications.data.ShortTextComplicationData;
import androidx.wear.watchface.complications.datasource.ComplicationDataSourceService;
import androidx.wear.watchface.complications.datasource.ComplicationRequest;
import java.time.Instant;

/** Dedicated next-countdown complication; it never exposes Smooch as a passive action. */
public final class CountdownComplicationService extends ComplicationDataSourceService {
    @Override
    public void onComplicationRequest(
            @NonNull ComplicationRequest request,
            @NonNull ComplicationRequestListener listener) {
        try {
            listener.onComplicationData(data(
                    WearDisplayCache.read(this), request.getComplicationType()));
        } catch (RemoteException ignored) {
            // A watch face may disappear between request and response.
        }
    }

    @Nullable
    @Override
    public ComplicationData getPreviewData(@NonNull ComplicationType type) {
        return shortData("12d", getString(R.string.countdown_preview_a11y));
    }

    private ComplicationData data(WearDisplayCache.State cache, ComplicationType type) {
        String remaining = cache.stale() ? getString(R.string.unavailable_short)
                : WearCountdownText.remaining(this, cache, Instant.now());
        String title = WearCountdownText.title(this, cache);
        String description = cache.stale() ? getString(R.string.complication_stale_a11y)
                : getString(R.string.countdown_complication_a11y, title, remaining);
        if (type == ComplicationType.LONG_TEXT) {
            return new LongTextComplicationData.Builder(
                    text(getString(R.string.countdown_complication_long, title, remaining)),
                    text(description)).build();
        }
        return shortData(remaining, description);
    }

    private static ComplicationData shortData(String value, String description) {
        return new ShortTextComplicationData.Builder(text(value), text(description)).build();
    }

    private static PlainComplicationText text(String value) {
        return new PlainComplicationText.Builder(value).build();
    }
}
