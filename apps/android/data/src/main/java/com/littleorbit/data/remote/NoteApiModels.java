package com.littleorbit.data.remote;

import com.squareup.moshi.Json;

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
}
