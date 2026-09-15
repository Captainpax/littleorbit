package com.littleorbit.mobile;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNotEquals;
import static org.junit.Assert.assertNull;

import android.content.Context;
import android.content.SharedPreferences;
import androidx.test.core.app.ApplicationProvider;
import org.junit.After;
import org.junit.Before;
import org.junit.Test;

/** Verifies random installation identity and cleanup of retired hosted transport state. */
public final class NotificationDeviceStoreInstrumentedTest {
    private Context context;
    private SharedPreferences preferences;

    @Before
    public void clearBefore() {
        context = ApplicationProvider.getApplicationContext();
        preferences = context.getSharedPreferences("notification-device", Context.MODE_PRIVATE);
        preferences.edit().clear().commit();
    }

    @After
    public void clearAfter() {
        preferences.edit().clear().commit();
    }

    @Test
    public void identifierIsStableUntilAccountStateIsCleared() {
        NotificationDeviceStore store = new NotificationDeviceStore(context);
        String first = store.id();

        assertEquals(first, store.id());
        store.clearForAccountChange();

        assertNotEquals(first, store.id());
    }

    @Test
    public void constructorDeletesEveryRetiredHostedTransportValue() {
        preferences.edit()
                .putString("push_token", "retired-address")
                .putString("push_token_sealed_v1", "retired-ciphertext")
                .putString("rejected_push_digest_v1", "retired-digest")
                .putBoolean("push_recovery_attempted_v1", true)
                .commit();

        new NotificationDeviceStore(context);

        assertNull(preferences.getString("push_token", null));
        assertNull(preferences.getString("push_token_sealed_v1", null));
        assertNull(preferences.getString("rejected_push_digest_v1", null));
        assertNull(preferences.getString("push_recovery_attempted_v1", null));
    }
}
