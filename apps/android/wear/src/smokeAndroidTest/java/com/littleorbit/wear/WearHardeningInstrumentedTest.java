package com.littleorbit.wear;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import android.content.Context;
import androidx.test.core.app.ApplicationProvider;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import java.util.List;
import org.junit.After;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;

@RunWith(AndroidJUnit4.class)
public final class WearHardeningInstrumentedTest {
    private Context context;

    @Before public void setUp() {
        context = ApplicationProvider.getApplicationContext();
        clear();
    }

    @After public void tearDown() {
        clear();
    }

    @Test public void encryptedQueueAcceptsOneItemWithoutImmutableListCrash() {
        long now = System.currentTimeMillis();
        WearSmoochQueue.enqueue(
                context, "operation", "😘", now, "relationship", 2, 3);

        List<WearSmoochQueue.Pending> pending = WearSmoochQueue.pending(context, now);
        assertEquals(1, pending.size());
        assertEquals("operation", pending.get(0).operationId());

        WearSmoochQueue.enqueue(
                context, "operation", "😘", now, "relationship", 2, 3);
        assertEquals(1, WearSmoochQueue.pending(context, now).size());
        WearSmoochQueue.remove(context, "operation");
        assertTrue(WearSmoochQueue.pending(context, now).isEmpty());
    }

    @Test public void controllerBindingRejectsAnotherPhoneAndClearsOnPurge() {
        assertTrue(WearTargetGuard.accept(
                context, "watch", "watch", 3, "phone-a"));
        assertTrue(WearTargetGuard.authorizesController(context, "phone-a"));
        assertTrue(WearTargetGuard.authorizesRelationshipSource(context, "phone-a"));
        assertFalse(WearTargetGuard.authorizesRelationshipSource(context, "phone-b"));
        assertFalse(WearTargetGuard.accept(
                context, "watch", "watch", 3, "phone-b"));

        assertTrue(WearTargetGuard.purge(context, 4));
        assertFalse(WearTargetGuard.authorizesController(context, "phone-a"));
        assertTrue(WearTargetGuard.authorizesRelationshipSource(context, "phone-b"));
    }

    private void clear() {
        WearSmoochQueue.clear(context);
        context.getSharedPreferences("little_orbit_watch_target_v1", Context.MODE_PRIVATE)
                .edit().clear().commit();
    }
}

