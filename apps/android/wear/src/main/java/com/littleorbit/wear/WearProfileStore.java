package com.littleorbit.wear;

import android.annotation.SuppressLint;
import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.StandardCopyOption;

/** Private app-storage cache for phone-authorized names and small thumbnails. */
final class WearProfileStore {
    private static final int MAX_THUMBNAIL_BYTES = 64 * 1024;
    private WearProfileStore() {}

    record State(String myName, Bitmap myPhoto, String partnerName, Bitmap partnerPhoto) {}

    static synchronized void storeNames(Context context, String me, String partner) {
        context.getSharedPreferences("profile", Context.MODE_PRIVATE).edit()
                .putString("my_name", me == null ? "You" : me)
                .putString("partner_name", partner == null ? "" : partner)
                .apply();
        if (partner == null || partner.isBlank()) delete(context, "partner.webp");
    }

    static synchronized void storePhoto(Context context, boolean partner, InputStream input)
            throws IOException {
        File target = new File(context.getFilesDir(), partner ? "partner.webp" : "me.webp");
        File pending = new File(target.getPath() + ".pending");
        try {
            try (input; FileOutputStream output = new FileOutputStream(pending)) {
                byte[] buffer = new byte[8192];
                int total = 0;
                int read;
                while ((read = input.read(buffer)) >= 0) {
                    total += read;
                    if (total > MAX_THUMBNAIL_BYTES) {
                        throw new IOException("Thumbnail exceeds limit");
                    }
                    output.write(buffer, 0, read);
                }
            }
            replace(pending, target);
            if (!target.isFile()) throw new IOException("Could not replace thumbnail");
        } finally {
            delete(context, pending.getName());
        }
    }

    static synchronized void clearPhoto(Context context, boolean partner) {
        delete(context, partner ? "partner.webp" : "me.webp");
        delete(context, partner ? "partner.webp.pending" : "me.webp.pending");
    }

    @SuppressLint("ApplySharedPref")
    static synchronized void clearAll(Context context) {
        // Names must be gone before a delayed photo callback can evaluate its guard.
        context.getSharedPreferences("profile", Context.MODE_PRIVATE).edit().clear().commit();
        clearPhoto(context, false);
        clearPhoto(context, true);
    }

    static synchronized State read(Context context) {
        android.content.SharedPreferences values =
                context.getSharedPreferences("profile", Context.MODE_PRIVATE);
        return new State(
                values.getString("my_name", "You"), bitmap(context, "me.webp"),
                values.getString("partner_name", ""), bitmap(context, "partner.webp"));
    }

    private static Bitmap bitmap(Context context, String name) {
        File file = new File(context.getFilesDir(), name);
        return file.isFile() ? BitmapFactory.decodeFile(file.getPath()) : null;
    }

    private static void replace(File pending, File target) throws IOException {
        try {
            Files.move(
                    pending.toPath(), target.toPath(),
                    StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING);
        } catch (IOException atomicUnavailable) {
            Files.move(pending.toPath(), target.toPath(), StandardCopyOption.REPLACE_EXISTING);
        }
    }

    private static void delete(Context context, String name) {
        File file = new File(context.getFilesDir(), name);
        if (file.exists()) file.delete();
    }
}
