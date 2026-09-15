package com.littleorbit.wear;

import android.os.RemoteException;
import android.util.Log;
import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.wear.watchface.complications.data.ComplicationData;
import androidx.wear.watchface.complications.data.ComplicationType;
import androidx.wear.watchface.complications.data.PlainComplicationText;
import androidx.wear.watchface.complications.data.LongTextComplicationData;
import androidx.wear.watchface.complications.data.ShortTextComplicationData;
import androidx.wear.watchface.complications.datasource.ComplicationDataSourceService;
import androidx.wear.watchface.complications.datasource.ComplicationRequest;

/** Watch-face complication backed by the last privacy-minimal phone cache. */
public final class TogetherComplicationService extends ComplicationDataSourceService {
    private static final String TAG = "OrbitComplication";

    @Override
    public void onComplicationRequest(
            @NonNull ComplicationRequest request,
            @NonNull ComplicationRequestListener listener) {
        try {
            listener.onComplicationData(displayData(
                    WearDisplayCache.read(this), request.getComplicationType()));
        } catch (RemoteException exception) {
            // The watch-face binder disappeared; there is no user data to retry or persist.
            Log.w(TAG, "Watch face disconnected before complication delivery");
        }
    }

    @Nullable
    @Override
    public ComplicationData getPreviewData(@NonNull ComplicationType type) {
        return new ShortTextComplicationData.Builder(
                new PlainComplicationText.Builder(getString(R.string.complication_preview_short)).build(),
                new PlainComplicationText.Builder(getString(R.string.complication_preview_a11y)).build())
                .build();
    }

    private ComplicationData displayData(
            WearDisplayCache.State cache, ComplicationType type) {
        WearDisplayText display = new WearDisplayText(this);
        if (type == ComplicationType.LONG_TEXT) {
            String value = display.longComplication(cache);
            return new LongTextComplicationData.Builder(
                    new PlainComplicationText.Builder(value).build(),
                    new PlainComplicationText.Builder(display.accessibility(cache)).build())
                    .build();
        }
        if (!cache.available()) {
            return shortData(display.relationshipShort(cache), display.accessibility(cache));
        }
        if (cache.stale()) {
            return shortData(
                    display.relationshipShort(cache), getString(R.string.complication_stale_a11y));
        }
        return shortData(display.relationshipShort(cache), display.accessibility(cache));
    }

    private ComplicationData shortData(String text, String description) {
        return new ShortTextComplicationData.Builder(
                new PlainComplicationText.Builder(text).build(),
                new PlainComplicationText.Builder(description).build())
                .build();
    }
}
