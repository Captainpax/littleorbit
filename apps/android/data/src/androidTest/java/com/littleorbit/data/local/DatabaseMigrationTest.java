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

/** Verifies that RC6 preserves legacy display values while splitting their meaning. */
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

    private static long value(Cursor cursor, String column) {
        return cursor.getLong(cursor.getColumnIndexOrThrow(column));
    }

    private static String text(Cursor cursor, String column) {
        return cursor.getString(cursor.getColumnIndexOrThrow(column));
    }
}
