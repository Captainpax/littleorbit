package com.littleorbit.wear;

import android.os.RemoteException;
import android.util.Log;
import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.wear.watchface.complications.data.ComplicationData;
import androidx.wear.watchface.complications.data.ComplicationType;
import androidx.wear.watchface.complications.data.PlainComplicationText;
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
            listener.onComplicationData(displayData(WearDisplayCache.read(this)));
        } catch (RemoteException exception) {
            // The watch-face binder disappeared; there is no user data to retry or persist.
            Log.w(TAG, "Watch face disconnected before complication delivery");
        }
    }

    @Nullable
    @Override
    public ComplicationData getPreviewData(@NonNull ComplicationType type) {
        return new ShortTextComplicationData.Builder(
                new PlainComplicationText.Builder("42d").build(),
                new PlainComplicationText.Builder("Little Orbit preview").build())
                .build();
    }

    private ComplicationData displayData(WearDisplayCache.State cache) {
        return new ShortTextComplicationData.Builder(
                new PlainComplicationText.Builder(cache.togetherText()).build(),
                new PlainComplicationText.Builder(cache.statusText()).build())
                .build();
    }
}
