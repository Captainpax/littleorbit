package com.littleorbit.data.local;

import androidx.annotation.NonNull;
import androidx.room.migration.Migration;
import androidx.sqlite.db.SupportSQLiteDatabase;

/** Explicit local migrations; destructive fallback is forbidden. */
public final class DatabaseMigrations {
    private DatabaseMigrations() {}

    /** Adds encrypted offline location queue storage. */
    public static final Migration MIGRATION_1_2 = new Migration(1, 2) {
        @Override
        public void migrate(@NonNull SupportSQLiteDatabase database) {
            database.execSQL(
                    "CREATE TABLE IF NOT EXISTS queued_locations ("
                            + "sampleId TEXT NOT NULL PRIMARY KEY,"
                            + "encryptedPayload TEXT NOT NULL,"
                            + "recordedAtEpochMillis INTEGER NOT NULL)");
        }
    };

    /** Adds encrypted countdown snapshots and retry-safe offline mutations. */
    public static final Migration MIGRATION_2_3 = new Migration(2, 3) {
        @Override
        public void migrate(@NonNull SupportSQLiteDatabase database) {
            database.execSQL(
                    "CREATE TABLE IF NOT EXISTS countdown_cache ("
                            + "countdownId TEXT NOT NULL PRIMARY KEY,"
                            + "encryptedPayload TEXT NOT NULL,"
                            + "occursAtEpochMillis INTEGER NOT NULL,"
                            + "pendingSync INTEGER NOT NULL,"
                            + "syncConflict INTEGER NOT NULL)");
            database.execSQL(
                    "CREATE TABLE IF NOT EXISTS queued_countdowns ("
                            + "operationId TEXT NOT NULL PRIMARY KEY,"
                            + "kind TEXT NOT NULL,"
                            + "countdownId TEXT,"
                            + "encryptedPayload TEXT NOT NULL,"
                            + "createdAtEpochMillis INTEGER NOT NULL)");
        }
    };

    /** Splits relationship age, nearby estimate recency, and cache-sync recency. */
    public static final Migration MIGRATION_3_4 = new Migration(3, 4) {
        @Override
        public void migrate(@NonNull SupportSQLiteDatabase database) {
            database.execSQL(
                    "CREATE TABLE IF NOT EXISTS display_cache_rc6 ("
                            + "cacheKey TEXT NOT NULL PRIMARY KEY,"
                            + "relationshipStartEpochDay INTEGER NOT NULL,"
                            + "nearbySeconds INTEGER NOT NULL,"
                            + "nearbyProcessedAtEpochMillis INTEGER NOT NULL,"
                            + "nextCountdownTitle TEXT NOT NULL,"
                            + "nextCountdownEpochMillis INTEGER NOT NULL,"
                            + "cacheSyncedAtEpochMillis INTEGER NOT NULL)");
            database.execSQL(
                    "INSERT INTO display_cache_rc6 SELECT cacheKey, -1, togetherSeconds, 0, "
                            + "COALESCE(nextCountdownTitle, 'No countdown yet'), "
                            + "nextCountdownEpochMillis, updatedAtEpochMillis FROM display_cache");
            database.execSQL("DROP TABLE display_cache");
            database.execSQL("ALTER TABLE display_cache_rc6 RENAME TO display_cache");
        }
    };

    /** Clears unbound coordinates and scopes every future row to one relationship generation. */
    public static final Migration MIGRATION_4_5 = new Migration(4, 5) {
        @Override
        public void migrate(@NonNull SupportSQLiteDatabase database) {
            database.execSQL("DROP TABLE queued_locations");
            database.execSQL(
                    "CREATE TABLE IF NOT EXISTS queued_locations ("
                            + "sampleId TEXT NOT NULL PRIMARY KEY,"
                            + "relationshipId TEXT NOT NULL,"
                            + "relationshipGeneration INTEGER NOT NULL,"
                            + "encryptedPayload TEXT NOT NULL,"
                            + "recordedAtEpochMillis INTEGER NOT NULL)");
        }
    };

    /** Adds exact timed/all-day semantics to the passive countdown cache. */
    public static final Migration MIGRATION_5_6 = new Migration(5, 6) {
        @Override
        public void migrate(@NonNull SupportSQLiteDatabase database) {
            database.execSQL(
                    "ALTER TABLE display_cache ADD COLUMN "
                            + "nextCountdownTimingKind TEXT NOT NULL DEFAULT 'timed'");
            database.execSQL(
                    "ALTER TABLE display_cache ADD COLUMN "
                            + "nextCountdownOccursOn TEXT NOT NULL DEFAULT ''");
            database.execSQL(
                    "ALTER TABLE display_cache ADD COLUMN "
                            + "nextCountdownTimezone TEXT NOT NULL DEFAULT 'UTC'");
        }
    };
}
