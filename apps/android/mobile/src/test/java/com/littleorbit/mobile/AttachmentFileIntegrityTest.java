package com.littleorbit.mobile;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import org.junit.Test;

/** Digest checks for app-private offline attachment copies. */
public final class AttachmentFileIntegrityTest {
    @Test
    public void acceptsExactBytesAndRejectsCorruption() throws Exception {
        File file = File.createTempFile("little-orbit-attachment", ".txt");
        try {
            Files.write(file.toPath(), "memory".getBytes(StandardCharsets.UTF_8));
            assertTrue(AttachmentFileIntegrity.matches(
                    file, "c064fbca9d9de8dd9bb0624984403b28d0da807a69365d4f7fb09123ecb0c405"));
            Files.write(file.toPath(), "changed".getBytes(StandardCharsets.UTF_8));
            assertFalse(AttachmentFileIntegrity.matches(
                    file, "c064fbca9d9de8dd9bb0624984403b28d0da807a69365d4f7fb09123ecb0c405"));
        } finally {
            file.delete();
        }
    }
}
