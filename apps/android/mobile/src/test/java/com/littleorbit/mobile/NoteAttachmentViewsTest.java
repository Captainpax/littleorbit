package com.littleorbit.mobile;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import java.io.File;
import java.util.Set;
import org.junit.Rule;
import org.junit.Test;
import org.junit.rules.TemporaryFolder;

/** Retained attachment lifecycle checks independent of Android rendering. */
public final class NoteAttachmentViewsTest {
    private static final String ACTIVE = "123e4567-e89b-12d3-a456-426614174000";
    private static final String PURGED = "123e4567-e89b-12d3-a456-426614174001";
    @Rule public final TemporaryFolder temporary = new TemporaryFolder();

    @Test
    public void removesPurgedNoteAndLegacyCopiesOnly() throws Exception {
        File root = temporary.newFolder("kept-space");
        File activeFile = file(root, ACTIVE, "attachment");
        File purgedFile = file(root, PURGED, "attachment");
        File legacy = new File(root, "legacy-attachment");
        assertTrue(legacy.createNewFile());

        NoteAttachmentViews.removeUnknownNoteDirectories(root, Set.of(ACTIVE));

        assertTrue(activeFile.isFile());
        assertFalse(purgedFile.exists());
        assertFalse(legacy.exists());
    }

    private static File file(File root, String noteId, String name) throws Exception {
        File directory = new File(root, noteId);
        assertTrue(directory.mkdirs());
        File file = new File(directory, name);
        assertTrue(file.createNewFile());
        return file;
    }
}
