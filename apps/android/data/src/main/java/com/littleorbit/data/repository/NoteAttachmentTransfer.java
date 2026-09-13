package com.littleorbit.data.repository;

import android.content.Context;
import com.littleorbit.data.remote.LittleOrbitApi;
import com.littleorbit.data.remote.NoteApiModels;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.Arrays;
import java.util.UUID;
import okhttp3.MediaType;
import okhttp3.RequestBody;
import okhttp3.ResponseBody;
import retrofit2.Call;
import retrofit2.Response;

/** Resumable private note-attachment transfer and verified app-private caching. */
final class NoteAttachmentTransfer {
    private static final int CLIENT_CHUNK_BYTES = 1024 * 1024;
    private final LittleOrbitApi api;
    private final Context context;

    NoteAttachmentTransfer(LittleOrbitApi api, Context context) {
        this.api = api;
        this.context = context;
    }

    NoteApiModels.Attachment upload(
            String noteId, String displayName, String mediaType, File file) {
        NoteApiModels.AttachmentCreate request = new NoteApiModels.AttachmentCreate(
                UUID.randomUUID().toString(), displayName, mediaType, file.length(), sha256(file));
        NoteApiModels.AttachmentUpload upload = execute(api.createNoteAttachment(noteId, request));
        long offset = upload.attachment.uploadedBytes;
        try (InputStream input = new FileInputStream(file)) {
            skipExactly(input, offset);
            return uploadChunks(noteId, upload, input, offset);
        } catch (IOException error) {
            throw failure("attachment_io_failed", error);
        }
    }

    private NoteApiModels.Attachment uploadChunks(
            String noteId, NoteApiModels.AttachmentUpload upload,
            InputStream input, long initialOffset) throws IOException {
        long offset = initialOffset;
        NoteApiModels.Attachment result = upload.attachment;
        byte[] buffer = new byte[Math.min(upload.chunkSizeBytes, CLIENT_CHUNK_BYTES)];
        while (offset < result.sizeBytes) {
            int count = input.read(buffer, 0, (int) Math.min(buffer.length, result.sizeBytes - offset));
            if (count < 0) throw new IOException("attachment ended before declared size");
            RequestBody body = RequestBody.create(
                    Arrays.copyOf(buffer, count), MediaType.get("application/octet-stream"));
            result = execute(api.uploadNoteAttachmentChunk(noteId, result.id, offset, body));
            offset = result.uploadedBytes;
        }
        return result;
    }

    File download(String noteId, NoteApiModels.Attachment attachment) {
        File directory = new File(context.getCacheDir(), "note-attachments");
        if (!directory.isDirectory() && !directory.mkdirs()) {
            throw new OrbitServiceException(-1, "attachment_cache_failed");
        }
        File target = new File(directory, attachment.id);
        if (target.isFile() && attachment.sha256.equals(sha256(target))) return target;
        ResponseBody response = execute(api.downloadNoteAttachment(noteId, attachment.id));
        try (InputStream input = response.byteStream();
                FileOutputStream output = new FileOutputStream(target)) {
            copyExpectedBytes(input, output, attachment.sizeBytes);
        } catch (IOException error) {
            target.delete();
            throw failure("attachment_download_failed", error);
        }
        if (!attachment.sha256.equals(sha256(target))) {
            target.delete();
            throw new OrbitServiceException(-1, "attachment_hash_failed");
        }
        return target;
    }

    private static String sha256(File file) {
        try (InputStream input = new FileInputStream(file)) {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] buffer = new byte[CLIENT_CHUNK_BYTES];
            for (int count; (count = input.read(buffer)) >= 0; ) digest.update(buffer, 0, count);
            return lowerHex(digest.digest());
        } catch (IOException | NoSuchAlgorithmException error) {
            throw failure("attachment_hash_failed", error);
        }
    }

    private static void skipExactly(InputStream input, long bytes) throws IOException {
        long remaining = bytes;
        while (remaining > 0) {
            long skipped = input.skip(remaining);
            if (skipped <= 0 && input.read() < 0) throw new IOException("resume offset is invalid");
            remaining -= Math.max(skipped, 1);
        }
    }

    private static void copyExpectedBytes(
            InputStream input, FileOutputStream output, long expected) throws IOException {
        byte[] buffer = new byte[64 * 1024];
        long copied = 0;
        for (int count; (count = input.read(buffer)) >= 0; ) {
            if (count == 0) continue;
            copied += count;
            if (copied > expected) throw new IOException("attachment exceeded declared size");
            output.write(buffer, 0, count);
        }
        if (copied != expected) throw new IOException("attachment did not match declared size");
    }

    private static String lowerHex(byte[] bytes) {
        char[] result = new char[bytes.length * 2];
        char[] digits = "0123456789abcdef".toCharArray();
        for (int index = 0; index < bytes.length; index++) {
            int value = bytes[index] & 0xff;
            result[index * 2] = digits[value >>> 4];
            result[index * 2 + 1] = digits[value & 0x0f];
        }
        return new String(result);
    }

    private static <T> T execute(Call<T> call) {
        try {
            Response<T> response = call.execute();
            T body = response.body();
            if (!response.isSuccessful() || body == null) {
                throw new OrbitServiceException(response.code());
            }
            return body;
        } catch (IOException error) {
            throw new OrbitServiceException(error);
        }
    }

    private static OrbitServiceException failure(
            String reason, Throwable cause) {
        return new OrbitServiceException(-1, reason, cause);
    }
}
