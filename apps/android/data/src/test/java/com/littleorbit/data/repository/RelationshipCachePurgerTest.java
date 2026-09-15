package com.littleorbit.data.repository;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import java.io.File;
import java.io.IOException;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CompletionException;
import java.util.concurrent.atomic.AtomicBoolean;
import org.junit.Rule;
import org.junit.Test;
import org.junit.rules.TemporaryFolder;

/** Fail-closed relationship-cache boundary tests. */
public final class RelationshipCachePurgerTest {
    @Rule public final TemporaryFolder temporary = new TemporaryFolder();

    @Test
    public void recognizesWrappedInactiveRelationshipStatus() {
        Throwable failure = new CompletionException(new OrbitServiceException(409));
        assertEquals(409, RelationshipCachePurger.statusCode(failure));
    }

    @Test
    public void distinguishesRelationshipInvalidationFromOrdinaryConflict() {
        Throwable inactive = new CompletionException(
                new OrbitServiceException(409, "relationship_inactive"));
        Throwable staleEdit = new CompletionException(new OrbitServiceException(409));

        assertTrue(RelationshipCachePurger.relationshipInactive(inactive));
        assertFalse(RelationshipCachePurger.relationshipInactive(staleEdit));
    }

    @Test
    public void purgesOnlyForStructuredInactiveFailure() {
        AtomicBoolean purged = new AtomicBoolean();
        CompletableFuture<Object> request = new CompletableFuture<>();
        RelationshipCachePurger.purgeWhenInactive(request, () -> purged.set(true));

        request.completeExceptionally(
                new OrbitServiceException(409, "relationship_inactive"));

        assertTrue(purged.get());

        purged.set(false);
        CompletableFuture<Object> staleEdit = new CompletableFuture<>();
        RelationshipCachePurger.purgeWhenInactive(staleEdit, () -> purged.set(true));
        staleEdit.completeExceptionally(new OrbitServiceException(409));
        assertFalse(purged.get());
    }

    @Test
    public void purgeDeletesSpaceFilesButPreservesUnrelatedCache() throws IOException {
        File cache = temporary.newFolder("cache");
        File kept = temporary.newFolder("kept-space");
        File nested = new File(kept, "note/attachment");
        assertTrue(nested.getParentFile().mkdirs());
        assertTrue(nested.createNewFile());
        File upload = new File(cache, "space-upload-private");
        File unrelated = new File(cache, "other-cache");
        assertTrue(upload.createNewFile());
        assertTrue(unrelated.createNewFile());
        RelationshipCachePurger.deleteTree(kept);
        RelationshipCachePurger.clearTransientUploads(cache);
        assertFalse(kept.exists());
        assertFalse(upload.exists());
        assertTrue(unrelated.exists());
    }
}
