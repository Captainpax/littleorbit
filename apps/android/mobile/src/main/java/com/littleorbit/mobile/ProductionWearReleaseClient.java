package com.littleorbit.mobile;

import android.content.Context;
import com.littleorbit.data.remote.ApiModels;
import com.littleorbit.data.remote.LittleOrbitApi;
import com.littleorbit.data.repository.NetworkReleaseRepository;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.net.URI;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.Response;
import okhttp3.ResponseBody;

/** Immutable HTTPS-backed Wear source shared by non-QA phone variants. */
class ProductionWearReleaseClient implements TrustedWearArtifactSource {
    private final LittleOrbitApi api;
    private final OkHttpClient http;
    private final Context context;

    protected ProductionWearReleaseClient(
            LittleOrbitApi api, OkHttpClient http, Context context) {
        this.api = api;
        this.http = http;
        this.context = context;
    }

    @Override public WearReleaseMetadata metadata() throws IOException {
        retrofit2.Response<ApiModels.ApkRelease> response = api.currentRelease().execute();
        ApiModels.ApkRelease value = response.body();
        if (!response.isSuccessful() || value == null) throw new IOException("Metadata unavailable");
        if (value.wearApkUrl == null || value.wearSha256 == null
                || value.wearSizeBytes == null || value.wearPackageName == null
                || value.wearVersionCode == null || value.wearMinimumAndroid == null) {
            throw new IOException("Wear metadata unavailable");
        }
        URI uri = URI.create(value.wearApkUrl);
        String expected = "/api/v1/releases/" + value.version + "/wear-apk";
        if (!"https".equals(uri.getScheme()) || !"lil-orb.pax-kun.com".equals(uri.getHost())
                || !expected.equals(uri.getPath()) || uri.getQuery() != null || uri.getFragment() != null
                || !NetworkReleaseRepository.EXPECTED_PACKAGE.equals(value.wearPackageName)
                || !NetworkReleaseRepository.EXPECTED_SIGNER.equals(value.signerSha256)) {
            throw new IOException("Wear metadata authority failed");
        }
        return new WearReleaseMetadata(
                value.version, value.wearVersionCode, value.wearApkUrl, value.wearSha256,
                value.wearSizeBytes, value.wearPackageName, value.signerSha256,
                value.wearMinimumAndroid);
    }

    @Override public File download(WearReleaseMetadata release) throws IOException {
        if (!release.productionAuthority()) throw new IOException("Wear authority is unavailable");
        File directory = new File(context.getCacheDir(), "wear-installer");
        if (!directory.isDirectory() && !directory.mkdirs()) {
            throw new IOException("Cache unavailable");
        }
        File pending = new File(directory, release.version() + ".pending");
        File target = new File(directory, release.version() + ".apk");
        Request request = new Request.Builder().url(release.apkUrl()).get().build();
        try (Response response = http.newCall(request).execute()) {
            ResponseBody body = response.body();
            if (!response.isSuccessful() || body == null) throw new IOException("Download failed");
            copyBounded(body, pending, release.sizeBytes());
        }
        if (pending.length() != release.sizeBytes()
                || (!pending.renameTo(target) && !replace(pending, target))) {
            throw new IOException("Download length mismatch");
        }
        return target;
    }

    private static void copyBounded(ResponseBody body, File target, long expected)
            throws IOException {
        try (java.io.InputStream input = body.byteStream();
                FileOutputStream output = new FileOutputStream(target, false)) {
            byte[] buffer = new byte[64 * 1024];
            long total = 0;
            int count;
            while ((count = input.read(buffer)) >= 0) {
                total += count;
                if (total > expected) throw new IOException("Download exceeds metadata");
                output.write(buffer, 0, count);
            }
        }
    }

    private static boolean replace(File source, File target) {
        if (target.exists() && !target.delete()) return false;
        return source.renameTo(target);
    }
}
