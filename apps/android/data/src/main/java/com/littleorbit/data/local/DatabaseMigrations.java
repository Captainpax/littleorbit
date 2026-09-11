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
}
