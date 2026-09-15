package com.littleorbit.data.repository;

import android.content.Context;
import java.io.File;
import java.util.concurrent.CompletableFuture;

/** Deletes pair-scoped Android files and recognizes sanitized repository failures. */
final class RelationshipCachePurger {
    private RelationshipCachePurger() {}

    static void clearFiles(Context context) {
        deleteTree(new File(context.getFilesDir(), "kept-space"));
        deleteTree(new File(context.getCacheDir(), "note-attachments"));
        deleteTree(new File(context.getCacheDir(), "profile-crops"));
        clearTransientUploads(context.getCacheDir());
    }

    static void clearTransientUploads(File cacheDirectory) {
        File[] uploads = cacheDirectory.listFiles(
                file -> file.isFile() && file.getName().startsWith("space-upload-"));
        if (uploads == null) return;
        for (File file : uploads) file.delete();
    }

    static int statusCode(Throwable failure) {
        Throwable current = failure;
        while (current != null) {
            if (current instanceof OrbitServiceException service) return service.statusCode();
            current = current.getCause();
        }
        return 0;
    }

    static boolean relationshipInactive(Throwable failure) {
        Throwable current = failure;
        while (current != null) {
            if (current instanceof OrbitServiceException service
                    && service.hasSafeCode("relationship_inactive")) return true;
            current = current.getCause();
        }
        return false;
    }

    static <T> CompletableFuture<T> purgeWhenInactive(
            CompletableFuture<T> request, Runnable purge) {
        return request.whenComplete((result, failure) -> {
            if (relationshipInactive(failure)) purge.run();
        });
    }

    static void deleteTree(File target) {
        File[] children = target.listFiles();
        if (children != null) {
            for (File child : children) deleteTree(child);
        }
        if (target.exists()) target.delete();
    }
}
