package com.littleorbit.data.remote;

import com.squareup.moshi.Json;

/** Network-only health response. */
public final class HealthDto {
    public final String status;
    public final String service;
    public final String version;
    @Json(name = "checked_at") public final String checkedAt;

    /** Creates a decoded network DTO. */
    public HealthDto(String status, String service, String version, String checkedAt) {
        this.status = status;
        this.service = service;
        this.version = version;
        this.checkedAt = checkedAt;
    }
}
