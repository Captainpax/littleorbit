package com.littleorbit.data.local;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

import android.database.Cursor;

import androidx.room.testing.MigrationTestHelper;
import androidx.sqlite.db.SupportSQLiteDatabase;
import androidx.sqlite.db.framework.FrameworkSQLiteOpenHelperFactory;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;

import org.junit.Rule;
import org.junit.Test;
import org.junit.runner.RunWith;

import java.io.IOException;

/** Verifies explicit local migrations without retaining unbound relationship data. */
@RunWith(AndroidJUnit4.class)
public final class DatabaseMigrationTest {
    private static final String DATABASE_NAME = "rc6-migration-test";

    @Rule
    public final MigrationTestHelper helper = new MigrationTestHelper(
            InstrumentationRegistry.getInstrumentation(),
            LittleOrbitDatabase.class.getCanonicalName(),
            new FrameworkSQLiteOpenHelperFactory());

    @Test
    public void migrateThreeToFourPreservesCachedValues() throws IOException {
        SupportSQLiteDatabase database = helper.createDatabase(DATABASE_NAME, 3);
        database.execSQL(
                "INSERT INTO display_cache "
                        + "(cacheKey, togetherSeconds, nextCountdownTitle, "
                        + "nextCountdownEpochMillis, updatedAtEpochMillis) "
                        + "VALUES ('primary', 7200, NULL, 1234, 5678)");
        database.close();

        database = helper.runMigrationsAndValidate(
                DATABASE_NAME, 4, true, DatabaseMigrations.MIGRATION_3_4);
        try (Cursor cursor = database.query("SELECT * FROM display_cache")) {
            assertTrue(cursor.moveToFirst());
            assertEquals(-1L, value(cursor, "relationshipStartEpochDay"));
            assertEquals(7200L, value(cursor, "nearbySeconds"));
            assertEquals(0L, value(cursor, "nearbyProcessedAtEpochMillis"));
            assertEquals("No countdown yet", text(cursor, "nextCountdownTitle"));
            assertEquals(1234L, value(cursor, "nextCountdownEpochMillis"));
            assertEquals(5678L, value(cursor, "cacheSyncedAtEpochMillis"));
        }
        database.close();
    }

    @Test
    public void migrateFourToFiveDropsCoordinatesWithoutRelationshipIdentity() throws IOException {
        String name = "location-generation-migration-test";
        SupportSQLiteDatabase database = helper.createDatabase(name, 4);
        database.execSQL(
                "INSERT INTO queued_locations "
                        + "(sampleId, encryptedPayload, recordedAtEpochMillis) "
                        + "VALUES ('sample', 'sealed', 1234)");
        database.close();

        database = helper.runMigrationsAndValidate(
                name, 5, true, DatabaseMigrations.MIGRATION_4_5);
        try (Cursor rows = database.query("SELECT COUNT(*) FROM queued_locations")) {
            assertTrue(rows.moveToFirst());
            assertEquals(0L, rows.getLong(0));
        }
        try (Cursor columns = database.query("PRAGMA table_info(queued_locations)")) {
            boolean relationshipId = false;
            boolean generation = false;
            while (columns.moveToNext()) {
                String column = text(columns, "name");
                relationshipId |= "relationshipId".equals(column);
                generation |= "relationshipGeneration".equals(column);
            }
            assertTrue(relationshipId);
            assertTrue(generation);
        }
        database.close();
    }

    @Test
    public void migrateFiveToSixPreservesCountdownWithSafeTimedDefaults() throws IOException {
        String name = "watch-countdown-migration-test";
        SupportSQLiteDatabase database = helper.createDatabase(name, 5);
        database.execSQL(
                "INSERT INTO display_cache (cacheKey, relationshipStartEpochDay, nearbySeconds, "
                        + "nearbyProcessedAtEpochMillis, nextCountdownTitle, "
                        + "nextCountdownEpochMillis, cacheSyncedAtEpochMillis) VALUES "
                        + "('primary', 1, 2, 3, 'Trip', 4, 5)");
        database.close();

        database = helper.runMigrationsAndValidate(
                name, 6, true, DatabaseMigrations.MIGRATION_5_6);
        try (Cursor cursor = database.query("SELECT * FROM display_cache")) {
            assertTrue(cursor.moveToFirst());
            assertEquals("Trip", text(cursor, "nextCountdownTitle"));
            assertEquals("timed", text(cursor, "nextCountdownTimingKind"));
            assertEquals("", text(cursor, "nextCountdownOccursOn"));
            assertEquals("UTC", text(cursor, "nextCountdownTimezone"));
        }
        database.close();
    }

    private static long value(Cursor cursor, String column) {
        return cursor.getLong(cursor.getColumnIndexOrThrow(column));
    }

    private static String text(Cursor cursor, String column) {
        return cursor.getString(cursor.getColumnIndexOrThrow(column));
    }
}
