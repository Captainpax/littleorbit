package com.littleorbit.mobile;

import android.database.Cursor;
import android.net.Uri;
import android.provider.OpenableColumns;
import android.widget.TextView;
import com.littleorbit.data.remote.NoteApiModels;
import com.littleorbit.data.repository.OrbitRepository;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.util.Locale;
import java.util.UUID;

/** Copies a selected document privately and uploads it through the resumable repository path. */
public final class NoteAttachmentUploadCoordinator {
    private static final long MAX_BYTES = 100L * 1024 * 1024;
    /** Exact Android picker types accepted by the server. */
    public static final String[] TYPES = {
        "image/jpeg", "image/png", "image/webp", "image/gif", "application/pdf",
        "text/plain", "text/markdown", "audio/mpeg", "audio/mp4", "audio/ogg",
        "video/mp4", "video/webm"
    };

    private final NotesActivity activity;
    private final OrbitRepository orbit;
    private final TextView status;

    /** Creates one bounded picker-to-repository coordinator. */
    public NoteAttachmentUploadCoordinator(
            NotesActivity activity, OrbitRepository orbit, TextView status) {
        this.activity = activity;
        this.orbit = orbit;
        this.status = status;
    }

    /** Validates, privately copies, and uploads one user-selected content URI. */
    public void upload(Uri uri, NoteApiModels.Note note, Result result) {
        SelectedFile selected = inspect(uri);
        if (selected == null || selected.size() > MAX_BYTES) {
            status.setText(R.string.attachment_too_large);
            return;
        }
        File temporary = copy(uri, selected.size());
        if (temporary == null) {
            status.setText(R.string.attachment_preview_failed);
            return;
        }
        status.setText(R.string.uploading_attachment);
        orbit.uploadNoteAttachment(note.id, selected.name(), selected.mediaType(), temporary)
                .whenComplete((attachment, failure) -> activity.runOnUiThread(() -> {
                    temporary.delete();
                    if (failure != null) {
                        status.setText(R.string.attachment_upload_failed);
                    } else {
                        result.completed(note.id, attachment);
                    }
                }));
    }

    private SelectedFile inspect(Uri uri) {
        String name = "attachment";
        long size = -1;
        try (Cursor cursor = activity.getContentResolver().query(
                uri, new String[] {OpenableColumns.DISPLAY_NAME, OpenableColumns.SIZE},
                null, null, null)) {
            if (cursor != null && cursor.moveToFirst()) {
                name = cursor.getString(0);
                size = cursor.isNull(1) ? -1 : cursor.getLong(1);
            }
        }
        String mediaType = activity.getContentResolver().getType(uri);
        if (mediaType == null || "application/octet-stream".equals(mediaType)) {
            mediaType = inferMediaType(name);
        }
        return mediaType == null ? null : new SelectedFile(name, mediaType, size);
    }

    private static String inferMediaType(String name) {
        String lower = name.toLowerCase(Locale.ROOT);
        if (lower.endsWith(".md")) return "text/markdown";
        if (lower.endsWith(".txt")) return "text/plain";
        if (lower.endsWith(".jpg") || lower.endsWith(".jpeg")) return "image/jpeg";
        if (lower.endsWith(".png")) return "image/png";
        if (lower.endsWith(".webp")) return "image/webp";
        if (lower.endsWith(".gif")) return "image/gif";
        if (lower.endsWith(".pdf")) return "application/pdf";
        if (lower.endsWith(".mp3")) return "audio/mpeg";
        if (lower.endsWith(".m4a")) return "audio/mp4";
        if (lower.endsWith(".ogg")) return "audio/ogg";
        if (lower.endsWith(".mp4")) return "video/mp4";
        if (lower.endsWith(".webm")) return "video/webm";
        return null;
    }

    private File copy(Uri uri, long expectedSize) {
        File target = new File(activity.getCacheDir(), "space-upload-" + UUID.randomUUID());
        try (InputStream input = activity.getContentResolver().openInputStream(uri);
                FileOutputStream output = new FileOutputStream(target)) {
            if (input == null) return null;
            long total = transferBounded(input, output);
            return expectedSize < 0 || total == expectedSize ? target : null;
        } catch (IOException error) {
            target.delete();
            return null;
        }
    }

    private static long transferBounded(InputStream input, FileOutputStream output)
            throws IOException {
        byte[] buffer = new byte[1024 * 1024];
        long total = 0;
        int count;
        while ((count = input.read(buffer)) >= 0) {
            total += count;
            if (total > MAX_BYTES) throw new IOException("attachment too large");
            output.write(buffer, 0, count);
        }
        return total;
    }

    /** Successful upload callback bound to the note that initiated it. */
    public interface Result {
        /** Receives pending-scan metadata without assuming immediate availability. */
        void completed(String noteId, NoteApiModels.Attachment attachment);
    }

    private record SelectedFile(String name, String mediaType, long size) {}
}
