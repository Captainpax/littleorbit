package com.littleorbit.data.repository;

import static org.junit.Assert.assertTrue;

import java.io.File;
import java.nio.file.Files;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;
import org.junit.Test;

/** Concurrency checks for the private attachment cache boundary. */
public final class NoteAttachmentTransferTest {
    @Test
    public void concurrentImageDownloadsAcceptDirectoryCreatedByPeer() throws Exception {
        File root = Files.createTempDirectory("orbit-attachment-cache").toFile();
        File directory = new File(root, "note-attachments");
        ExecutorService workers = Executors.newFixedThreadPool(8);
        CountDownLatch ready = new CountDownLatch(8);
        CountDownLatch start = new CountDownLatch(1);
        List<Future<Boolean>> results = new ArrayList<>();
        try {
            for (int index = 0; index < 8; index++) {
                results.add(workers.submit(() -> {
                    ready.countDown();
                    assertTrue(start.await(2, TimeUnit.SECONDS));
                    return NoteAttachmentTransfer.ensureDirectory(directory);
                }));
            }
            assertTrue(ready.await(2, TimeUnit.SECONDS));
            start.countDown();
            for (Future<Boolean> result : results) {
                assertTrue(result.get(2, TimeUnit.SECONDS));
            }
            assertTrue(directory.isDirectory());
        } finally {
            workers.shutdownNow();
            directory.delete();
            root.delete();
        }
    }
}
