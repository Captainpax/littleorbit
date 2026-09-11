package com.littleorbit.mobile;

import android.app.Application;
import androidx.hilt.work.HiltWorkerFactory;
import androidx.work.Configuration;
import com.littleorbit.data.ReleaseCheckWorker;
import dagger.hilt.android.HiltAndroidApp;
import javax.inject.Inject;

/** Application root for constructor-injected Android dependencies. */
@HiltAndroidApp
public final class LittleOrbitApplication extends Application implements Configuration.Provider {
    @Inject HiltWorkerFactory workerFactory;

    @Override
    public void onCreate() {
        super.onCreate();
        ReleaseCheckWorker.schedule(this);
    }

    /** Routes WorkManager construction through Hilt without a global service locator. */
    @Override
    public Configuration getWorkManagerConfiguration() {
        return new Configuration.Builder().setWorkerFactory(workerFactory).build();
    }
}
