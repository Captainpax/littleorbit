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

        /** Creates one decoded profile person. */
        public Person(String displayName, PhotoMetadata photo) {
            this.displayName = displayName;
            this.photo = photo;
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
