package com.littleorbit.mobile;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import android.content.Context;
import android.os.Bundle;
import androidx.test.core.app.ApplicationProvider;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import com.littleorbit.data.repository.NoteDraftStore;
import com.littleorbit.data.security.SessionStore;
import org.junit.Test;
import org.junit.runner.RunWith;

/** Verifies process restoration keeps relationship content outside ordinary saved state. */
@RunWith(AndroidJUnit4.class)
public final class NoteWorkspaceControllerInstrumentedTest {
    @Test
    public void bundleContainsOnlyOpaqueReferenceAndEncryptedStoreRestoresContent() {
        Context context = ApplicationProvider.getApplicationContext();
        NoteDraftStore store = new NoteDraftStore(context, new SessionStore(context));
        store.clearAll();
        NoteWorkspaceController original = new NoteWorkspaceController(store, null);
        original.begin();
        original.persist(new NoteDraftStore.Workspace(
                null, "", "Private title", "", "Private body", 0, 0,
                null, null, null, "stable-operation", 4, 7, false));
        Bundle state = new Bundle();
        original.saveReference(state);
        assertEquals(1, state.keySet().size());
        assertFalse(state.toString().contains("Private body"));
        NoteWorkspaceController restored = new NoteWorkspaceController(store, state);
        assertTrue(restored.restored().isPresent());
        assertEquals("Private body", restored.restored().orElseThrow().body());
        restored.finish();
        store.clearAll();
    }
}
