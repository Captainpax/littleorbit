package com.littleorbit.mobile;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNotEquals;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import android.content.Context;
import android.content.SharedPreferences;
import androidx.test.core.app.ApplicationProvider;
import org.junit.After;
import org.junit.Before;
import org.junit.Test;

/** Verifies that the private FCM address is never retained as preference plaintext. */
public final class NotificationDeviceStoreInstrumentedTest {
    private static final String TOKEN = "private-fcm-installation-address";
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
    public void saveEncryptsAndClearRemovesToken() {
        NotificationDeviceStore store = new NotificationDeviceStore(context);

        assertTrue(store.savePushToken(TOKEN));

        String sealed = preferences.getString("push_token_sealed_v1", null);
        assertNotEquals(TOKEN, sealed);
        assertEquals(TOKEN, store.pushToken());
        store.clearPushToken();
        assertNull(store.pushToken());
    }

    @Test
    public void rejectedTokenIsQuarantinedAndRecoveryIsBounded() {
        NotificationDeviceStore store = new NotificationDeviceStore(context);
        assertTrue(store.savePushToken(TOKEN));

        assertTrue(store.rejectPushToken(TOKEN));
        assertNull(store.pushToken());
        assertFalse(store.savePushToken(TOKEN));
        assertFalse(store.rejectPushToken(TOKEN));
        assertTrue(store.savePushToken(TOKEN + "-rotated"));

        store.pushTokenAccepted();
        assertEquals(TOKEN + "-rotated", store.pushToken());
    }

    @Test
    public void constructorMigratesAndDeletesLegacyPlaintext() {
        preferences.edit().putString("push_token", TOKEN).commit();

        NotificationDeviceStore store = new NotificationDeviceStore(context);

        assertNull(preferences.getString("push_token", null));
        assertEquals(TOKEN, store.pushToken());
    }
}
