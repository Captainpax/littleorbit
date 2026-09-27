package com.littleorbit.data.remote;

import com.squareup.moshi.Json;

/** Private profile identity DTOs shared only with authenticated repositories. */
public final class ProfileApiModels {
    private ProfileApiModels() {}

    /** Revision metadata used to decide whether cached image bytes are current. */
    public static final class PhotoMetadata {
        public final int revision;
        public final String sha256;
        @Json(name = "updated_at") public final String updatedAt;

        /** Creates decoded immutable photo metadata. */
        public PhotoMetadata(int revision, String sha256, String updatedAt) {
            this.revision = revision;
            this.sha256 = sha256;
            this.updatedAt = updatedAt;
        }
    }

    /** Display identity for one authorized member. */
    public static final class Person {
        @Json(name = "display_name") public final String displayName;
        public final PhotoMetadata photo;
        @Json(name = "name_revision") public final int nameRevision;
        @Json(name = "partner_assigned") public final boolean partnerAssigned;

        /** Creates one decoded profile person. */
        public Person(
                String displayName,
                PhotoMetadata photo,
                int nameRevision,
                boolean partnerAssigned) {
            this.displayName = displayName;
            this.photo = photo;
            this.nameRevision = nameRevision;
            this.partnerAssigned = partnerAssigned;
        }
    }

    /** Retry-safe request to assign the caller's current partner a shared name. */
    public static final class PartnerNameMutation {
        @Json(name = "operation_id") public final String operationId;
        @Json(name = "expected_revision") public final int expectedRevision;
        @Json(name = "display_name") public final String displayName;

        /** Creates one immutable name mutation. */
        public PartnerNameMutation(String operationId, int expectedRevision, String displayName) {
            this.operationId = operationId;
            this.expectedRevision = expectedRevision;
            this.displayName = displayName;
        }
    }

    /** Retry-safe request to reset the caller-controlled partner name. */
    public static final class PartnerNameReset {
        @Json(name = "operation_id") public final String operationId;
        @Json(name = "expected_revision") public final int expectedRevision;

        /** Creates one immutable reset request. */
        public PartnerNameReset(String operationId, int expectedRevision) {
            this.operationId = operationId;
            this.expectedRevision = expectedRevision;
        }
    }

    /** Current relationship name after a successful mutation or replay. */
    public static final class PartnerNameState {
        @Json(name = "display_name") public final String displayName;
        @Json(name = "assigned_name") public final String assignedName;
        public final int revision;
        @Json(name = "partner_assigned") public final boolean partnerAssigned;
        @Json(name = "updated_at") public final String updatedAt;

        /** Creates one decoded mutation result. */
        public PartnerNameState(
                String displayName,
                String assignedName,
                int revision,
                boolean partnerAssigned,
                String updatedAt) {
            this.displayName = displayName;
            this.assignedName = assignedName;
            this.revision = revision;
            this.partnerAssigned = partnerAssigned;
            this.updatedAt = updatedAt;
        }
    }

    /** Caller identity plus an optional currently paired partner. */
    public static final class OrbitProfile {
        public final Person me;
        public final Person partner;

        /** Creates one decoded orbit profile. */
        public OrbitProfile(Person me, Person partner) {
            this.me = me;
            this.partner = partner;
        }
    }
}
