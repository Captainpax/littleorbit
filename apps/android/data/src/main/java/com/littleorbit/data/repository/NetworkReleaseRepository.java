package com.littleorbit.data.repository;

import android.content.Context;
import android.content.SharedPreferences;
import com.littleorbit.data.remote.ApiModels;
import com.littleorbit.data.remote.LittleOrbitApi;
import com.littleorbit.domain.ReleaseUpdate;
import dagger.hilt.android.qualifiers.ApplicationContext;
import java.io.IOException;
import java.net.URI;
import java.time.Instant;
import java.util.Optional;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import javax.inject.Inject;
import javax.inject.Singleton;
import retrofit2.Response;

/** HTTPS release metadata client that accepts only the canonical GitHub artifact authority. */
@Singleton
public final class NetworkReleaseRepository implements ReleaseRepository {
    public static final String EXPECTED_PACKAGE = "com.littleorbit.mobile";
    public static final String EXPECTED_SIGNER =
            "43e83a420c7496ce9121339ab5bd6b01a6357161a83a95042ace56855bd89337";
    private static final String STORE = "little-orbit-updates";
    private final LittleOrbitApi api;
    private final SharedPreferences preferences;
    private final ExecutorService executor = Executors.newSingleThreadExecutor(runnable -> {
        Thread thread = new Thread(runnable, "little-orbit-release-check");
        thread.setDaemon(true);
        return thread;
    });

    /** Creates release discovery with application-private, non-sensitive state. */
    @Inject
    public NetworkReleaseRepository(LittleOrbitApi api, @ApplicationContext Context context) {
        this.api = api;
        preferences = context.getSharedPreferences(STORE, Context.MODE_PRIVATE);
    }

    @Override
    public CompletableFuture<ReleaseUpdate> refresh() {
        return CompletableFuture.supplyAsync(() -> {
            try {
                Response<ApiModels.ApkRelease> response = api.currentRelease().execute();
                ApiModels.ApkRelease body = response.body();
                if (!response.isSuccessful() || body == null) {
                    throw new ReleaseCheckException("release_metadata_unavailable");
                }
                ReleaseUpdate release = map(body);
                write(release, System.currentTimeMillis());
                return release;
            } catch (IOException exception) {
                throw new ReleaseCheckException("release_network_unavailable", exception);
            }
        }, executor);
    }

    @Override
    public Optional<ReleaseUpdate> cached() {
        try {
            if (!preferences.contains("version_code")) return Optional.empty();
            return Optional.of(read());
        } catch (RuntimeException invalid) {
            preferences.edit().clear().apply();
            return Optional.empty();
        }
    }

    @Override
    public long lastCheckedAtMillis() {
        return preferences.getLong("checked_at", 0);
    }

    @Override
    public void defer(String releaseId, long untilEpochMillis) {
        preferences.edit()
                .putString("deferred_release", releaseId)
                .putLong("deferred_until", untilEpochMillis)
                .apply();
    }

    @Override
    public boolean isDeferred(String releaseId, long nowEpochMillis) {
        return releaseId.equals(preferences.getString("deferred_release", ""))
                && nowEpochMillis < preferences.getLong("deferred_until", 0);
    }

    private static ReleaseUpdate map(ApiModels.ApkRelease dto) {
        validateAuthority(dto);
        return new ReleaseUpdate(
                dto.version,
                dto.versionCode,
                dto.apkUrl,
                dto.githubReleaseUrl,
                dto.sha256,
                dto.sizeBytes,
                dto.packageName,
                dto.signerSha256,
                dto.minimumAndroid,
                dto.minimumSupportedVersionCode,
                dto.requiredAfter == null ? null : Instant.parse(dto.requiredAfter),
                dto.releaseNotes,
                Instant.parse(dto.publishedAt));
    }

    private static void validateAuthority(ApiModels.ApkRelease dto) {
        URI apk = URI.create(dto.apkUrl);
        URI release = URI.create(dto.githubReleaseUrl);
        String tag = "v" + dto.version;
        String prefix = "/Captainpax/littleorbit/releases/download/" + tag + "/";
        boolean validApk = canonicalGithub(apk)
                && apk.getPath().startsWith(prefix)
                && apk.getPath().endsWith(".apk");
        boolean validRelease = canonicalGithub(release)
                && release.getPath().equals("/Captainpax/littleorbit/releases/tag/" + tag);
        if (!validApk || !validRelease
                || !EXPECTED_PACKAGE.equals(dto.packageName)
                || !EXPECTED_SIGNER.equals(dto.signerSha256)) {
            throw new ReleaseCheckException("release_metadata_invalid");
        }
    }

    private static boolean canonicalGithub(URI uri) {
        return "https".equals(uri.getScheme())
                && "github.com".equals(uri.getHost())
                && uri.getRawQuery() == null
                && uri.getRawFragment() == null
                && uri.getUserInfo() == null;
    }

    private void write(ReleaseUpdate release, long checkedAt) {
        preferences.edit()
                .putString("version", release.version())
                .putInt("version_code", release.versionCode())
                .putString("apk_url", release.apkUrl())
                .putString("github_url", release.githubReleaseUrl())
                .putString("sha256", release.sha256())
                .putLong("size", release.sizeBytes())
                .putString("package", release.packageName())
                .putString("signer", release.signerSha256())
                .putInt("minimum_android", release.minimumAndroid())
                .putInt("floor", release.minimumSupportedVersionCode())
                .putString(
                        "required_after",
                        release.requiredAfter() == null ? "" : release.requiredAfter().toString())
                .putString("notes", release.releaseNotes())
                .putString("published_at", release.publishedAt().toString())
                .putLong("checked_at", checkedAt)
                .apply();
    }

    private ReleaseUpdate read() {
        String required = preferences.getString("required_after", "");
        return new ReleaseUpdate(
                required("version"),
                preferences.getInt("version_code", 0),
                required("apk_url"),
                required("github_url"),
                required("sha256"),
                preferences.getLong("size", 0),
                required("package"),
                required("signer"),
                preferences.getInt("minimum_android", 0),
                preferences.getInt("floor", 0),
                required == null || required.isEmpty() ? null : Instant.parse(required),
                required("notes"),
                Instant.parse(required("published_at")));
    }

    private String required(String key) {
        String value = preferences.getString(key, null);
        if (value == null || value.isEmpty()) throw new ReleaseCheckException("release_cache_invalid");
        return value;
    }

    /** Stable failure without URL, response body, or local path disclosure. */
    public static final class ReleaseCheckException extends RuntimeException {
        /** Creates a sanitized release failure. */
        public ReleaseCheckException(String code) { super(code); }
        /** Creates a sanitized release transport failure. */
        public ReleaseCheckException(String code, Throwable cause) { super(code, cause); }
    }
}
