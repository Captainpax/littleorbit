package com.littleorbit.data.repository;

import android.content.Context;
import com.littleorbit.data.DisplayCacheSyncWorker;
import com.littleorbit.data.remote.ApiModels;
import com.littleorbit.data.remote.CountdownApiModels;
import com.littleorbit.data.remote.LittleOrbitApi;
import java.util.List;

/** Owns the online-first countdown mutation and encrypted-offline fallback policy. */
final class CountdownSyncGateway {
    private final LittleOrbitApi api;
    private final CountdownOfflineStore offline;
    private final Context context;

    CountdownSyncGateway(LittleOrbitApi api, CountdownOfflineStore offline, Context context) {
        this.api = api;
        this.offline = offline;
        this.context = context;
    }

    List<CountdownApiModels.Countdown> load() {
        try {
            List<CountdownApiModels.Countdown> remote = RetrofitCalls.execute(api.countdowns());
            offline.replaceRemote(remote);
            return offline.cached();
        } catch (OrbitServiceException failure) {
            if (failure.statusCode() != -1) throw failure;
            return offline.cached();
        }
    }

    CountdownApiModels.Countdown create(CountdownApiModels.Mutation mutation) {
        try {
            CountdownApiModels.Countdown result = RetrofitCalls.execute(api.createCountdown(mutation));
            DisplayCacheSyncWorker.enqueue(context);
            return result;
        } catch (OrbitServiceException failure) {
            if (failure.statusCode() == -1) return offline.queueCreate(mutation);
            throw failure;
        }
    }

    CountdownApiModels.Countdown update(
            String countdownId, CountdownApiModels.Mutation mutation) {
        if (countdownId.startsWith("local:")) return offline.queueUpdate(countdownId, mutation);
        try {
            CountdownApiModels.Countdown result = RetrofitCalls.execute(
                    api.updateCountdown(countdownId, mutation));
            DisplayCacheSyncWorker.enqueue(context);
            return result;
        } catch (OrbitServiceException failure) {
            if (failure.statusCode() == -1) return offline.queueUpdate(countdownId, mutation);
            throw failure;
        }
    }

    ApiModels.Message delete(String countdownId, CountdownApiModels.DeleteRequest request) {
        if (countdownId.startsWith("local:")) return offline.queueDelete(countdownId, request);
        try {
            ApiModels.Message result = RetrofitCalls.execute(api.deleteCountdown(countdownId, request));
            DisplayCacheSyncWorker.enqueue(context);
            return result;
        } catch (OrbitServiceException failure) {
            if (failure.statusCode() == -1) return offline.queueDelete(countdownId, request);
            throw failure;
        }
    }

    void clear() {
        offline.clear();
    }
}
