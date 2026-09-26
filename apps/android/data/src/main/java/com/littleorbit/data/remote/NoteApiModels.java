package com.littleorbit.data.remote;

import com.squareup.moshi.Json;
import java.util.List;

/** Wire-only models for the shared note workspace. */
public final class NoteApiModels {
    private NoteApiModels() {}

    /** Shared plain-text note response. */
    public static final class Note {
        public final String id;
        public final String title;
        public final String body;
        public final int revision;
        @Json(name = "metadata_revision") public final int metadataRevision;
        @Json(name = "updated_at") public final String updatedAt;
        @Json(name = "archived_at") public final String archivedAt;
        @Json(name = "purge_after") public final String purgeAfter;

        /** Creates a decoded note including independent body, metadata, and archive state. */
        public Note(String id, String title, String body, int revision, int metadataRevision,
                String updatedAt, String archivedAt, String purgeAfter) {
            this.id = id;
            this.title = title;
            this.body = body;
            this.revision = revision;
            this.metadataRevision = metadataRevision;
            this.updatedAt = updatedAt;
            this.archivedAt = archivedAt;
            this.purgeAfter = purgeAfter;
        }
    }

    /** Retry-safe note creation request. */
    public static final class CreateRequest {
        @Json(name = "operation_id") public final String operationId;
        public final String title;
        public final String body;

        /** Creates note input while a draft stays local. */
        public CreateRequest(String operationId, String title, String body) {
            this.operationId = operationId;
            this.title = title;
            this.body = body;
        }
    }

    /** Retry-safe note title mutation on the independent metadata revision. */
    public static final class TitleRequest {
        @Json(name = "operation_id") public final String operationId;
        @Json(name = "expected_metadata_revision") public final int expectedRevision;
        public final String title;

        /** Creates a title mutation. */
        public TitleRequest(String operationId, int expectedRevision, String title) {
            this.operationId = operationId;
            this.expectedRevision = expectedRevision;
            this.title = title;
        }
    }

    /** Retry-safe note archive or restore mutation. */
    public static final class ArchiveRequest {
        @Json(name = "operation_id") public final String operationId;
        @Json(name = "expected_metadata_revision") public final int expectedRevision;

        /** Creates a lifecycle mutation. */
        public ArchiveRequest(String operationId, int expectedRevision) {
            this.operationId = operationId;
            this.expectedRevision = expectedRevision;
        }
    }

    /** Explicit, retry-safe copy used when an offline draft conflicts. */
    public static final class ForkRequest {
        @Json(name = "operation_id") public final String operationId;
        public final String title;
        public final String body;

        /** Creates a separate note without mutating the shared source. */
        public ForkRequest(String operationId, String title, String body) {
            this.operationId = operationId;
            this.title = title;
            this.body = body;
        }
    }

    /** Attachment metadata that never exposes a server storage path. */
    public static final class Attachment {
        public final String id;
        @Json(name = "note_id") public final String noteId;
        @Json(name = "file_name") public final String fileName;
        @Json(name = "media_type") public final String mediaType;
        @Json(name = "size_bytes") public final long sizeBytes;
        @Json(name = "uploaded_bytes") public final long uploadedBytes;
        public final String sha256;
        public final String status;
        @Json(name = "rejection_reason") public final String rejectionReason;
        @Json(name = "download_url") public final String downloadUrl;

        /** Creates privacy-safe decoded attachment state. */
        public Attachment(
                String id, String noteId, String fileName, String mediaType,
                long sizeBytes, long uploadedBytes, String sha256, String status,
                String rejectionReason, String downloadUrl) {
            this.id = id;
            this.noteId = noteId;
            this.fileName = fileName;
            this.mediaType = mediaType;
            this.sizeBytes = sizeBytes;
            this.uploadedBytes = uploadedBytes;
            this.sha256 = sha256;
            this.status = status;
            this.rejectionReason = rejectionReason;
            this.downloadUrl = downloadUrl;
        }
    }

    /** Idempotent upload reservation using the original file digest. */
    public static final class AttachmentCreate {
        @Json(name = "operation_id") public final String operationId;
        @Json(name = "file_name") public final String fileName;
        @Json(name = "media_type") public final String mediaType;
        @Json(name = "size_bytes") public final long sizeBytes;
        public final String sha256;

        /** Creates one bounded upload reservation. */
        public AttachmentCreate(
                String operationId, String fileName, String mediaType,
                long sizeBytes, String sha256) {
            this.operationId = operationId;
            this.fileName = fileName;
            this.mediaType = mediaType;
            this.sizeBytes = sizeBytes;
            this.sha256 = sha256;
        }
    }

    /** Stable upload target and current accepted offset. */
    public static final class AttachmentUpload {
        public final Attachment attachment;
        @Json(name = "upload_url") public final String uploadUrl;
        @Json(name = "chunk_size_bytes") public final int chunkSizeBytes;

        /** Creates decoded resumable upload state. */
        public AttachmentUpload(
                Attachment attachment, String uploadUrl, int chunkSizeBytes) {
            this.attachment = attachment;
            this.uploadUrl = uploadUrl;
            this.chunkSizeBytes = chunkSizeBytes;
        }
    }
}
