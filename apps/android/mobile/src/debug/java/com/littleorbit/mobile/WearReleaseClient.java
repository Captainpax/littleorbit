package com.littleorbit.mobile;

import android.content.Context;
import com.littleorbit.data.remote.LittleOrbitApi;
import dagger.hilt.android.qualifiers.ApplicationContext;
import javax.inject.Inject;
import javax.inject.Singleton;
import okhttp3.OkHttpClient;

/** Production-authority Wear source used by the ordinary debug phone build. */
@Singleton
public final class WearReleaseClient extends ProductionWearReleaseClient {
    @Inject
    public WearReleaseClient(
            LittleOrbitApi api, OkHttpClient http, @ApplicationContext Context context) {
        super(api, http, context);
    }
}
