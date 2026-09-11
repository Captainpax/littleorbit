package com.littleorbit.data;

import android.content.Context;
import androidx.room.Room;
import com.littleorbit.data.local.DisplayCacheDao;
import com.littleorbit.data.local.CountdownDao;
import com.littleorbit.data.local.DatabaseMigrations;
import com.littleorbit.data.local.LittleOrbitDatabase;
import com.littleorbit.data.local.LocationQueueDao;
import com.littleorbit.data.remote.LittleOrbitApi;
import com.littleorbit.data.remote.SessionInterceptor;
import com.littleorbit.data.repository.DisplayCacheRepository;
import com.littleorbit.data.repository.NetworkOrbitRepository;
import com.littleorbit.data.repository.OrbitRepository;
import com.littleorbit.data.repository.RoomDisplayCacheRepository;
import com.squareup.moshi.Moshi;
import dagger.Binds;
import dagger.Module;
import dagger.Provides;
import dagger.hilt.InstallIn;
import dagger.hilt.android.qualifiers.ApplicationContext;
import dagger.hilt.components.SingletonComponent;
import javax.inject.Singleton;
import okhttp3.OkHttpClient;
import retrofit2.Retrofit;
import retrofit2.converter.moshi.MoshiConverterFactory;

/** Hilt bindings for local storage and the authenticated repository graph. */
@Module
@InstallIn(SingletonComponent.class)
public abstract class DisplayModule {
    /** Binds the cache abstraction. */
    @Binds
    abstract DisplayCacheRepository bindCache(RoomDisplayCacheRepository repository);

    /** Binds authenticated feature operations. */
    @Binds
    abstract OrbitRepository bindOrbit(NetworkOrbitRepository repository);

    /** Provides the single Room database. Destructive migration is intentionally absent. */
    @Provides @Singleton
    static LittleOrbitDatabase database(@ApplicationContext Context context) {
        return Room.databaseBuilder(context, LittleOrbitDatabase.class, "little-orbit.db")
                .addMigrations(DatabaseMigrations.MIGRATION_1_2)
                .addMigrations(DatabaseMigrations.MIGRATION_2_3)
                .build();
    }

    /** Provides cache operations. */
    @Provides
    static DisplayCacheDao displayCacheDao(LittleOrbitDatabase database) {
        return database.displayCache();
    }

    /** Provides encrypted queued-location operations. */
    @Provides
    static LocationQueueDao locationQueueDao(LittleOrbitDatabase database) {
        return database.locationQueue();
    }

    /** Provides encrypted countdown cache and queue operations. */
    @Provides
    static CountdownDao countdownDao(LittleOrbitDatabase database) {
        return database.countdowns();
    }

    /** Provides a metadata-only HTTP logger; bodies may contain relationship content. */
    @Provides @Singleton
    static OkHttpClient httpClient(SessionInterceptor sessions) {
        return new OkHttpClient.Builder().addInterceptor(sessions).build();
    }

    /** Provides the versioned API client. Session injection is added by the auth repository. */
    @Provides @Singleton
    static LittleOrbitApi api(OkHttpClient client) {
        Moshi moshi = new Moshi.Builder().build();
        return new Retrofit.Builder()
                .baseUrl("https://lil-orb.pax-kun.com/")
                .client(client)
                .addConverterFactory(MoshiConverterFactory.create(moshi))
                .build()
                .create(LittleOrbitApi.class);
    }
}
