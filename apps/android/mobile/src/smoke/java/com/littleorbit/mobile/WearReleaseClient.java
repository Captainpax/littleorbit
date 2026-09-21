package com.littleorbit.mobile;

import android.content.Context;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import com.littleorbit.data.remote.LittleOrbitApi;
import dagger.hilt.android.qualifiers.ApplicationContext;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.security.MessageDigest;
import java.util.Locale;
import javax.inject.Inject;
import javax.inject.Singleton;
import okhttp3.OkHttpClient;

/** Fixed bundled Wear source available only inside the side-by-side QA phone variant. */
@Singleton
public final class WearReleaseClient implements TrustedWearArtifactSource {
    private static final String ASSET = "little-orbit-wear-smoke.apk";
    private final Context context;

    @Inject
    public WearReleaseClient(
            LittleOrbitApi ignoredApi,
            OkHttpClient ignoredHttp,
            @ApplicationContext Context context) {
        this.context = context;
    }

    @Override public WearReleaseMetadata metadata() throws IOException {
        File apk = artifact();
        PackageInfo info = context.getPackageManager().getPackageArchiveInfo(
                apk.getPath(), PackageManager.GET_SIGNING_CERTIFICATES);
        if (info == null || !BuildConfig.APPLICATION_ID.equals(info.packageName)
                || info.signingInfo == null) throw new IOException("QA Wear artifact invalid");
        try {
            String signer = singleSigner(info);
            PackageInfo phone = context.getPackageManager().getPackageInfo(
                    context.getPackageName(), PackageManager.GET_SIGNING_CERTIFICATES);
            if (!signer.equals(singleSigner(phone))) {
                throw new IOException("QA Wear signer does not match QA phone");
            }
            return new WearReleaseMetadata(
                    info.versionName,
                    (int) info.getLongVersionCode(),
                    "asset://" + ASSET,
                    fileSha256(apk),
                    apk.length(),
                    info.packageName,
                    signer,
                    30,
                    false);
        } catch (PackageManager.NameNotFoundException invalid) {
            throw new IOException("QA phone identity unavailable", invalid);
        } catch (java.security.GeneralSecurityException invalid) {
            throw new IOException("QA Wear digest unavailable", invalid);
        }
    }

    @Override public File download(WearReleaseMetadata release) throws IOException {
        if (release.productionAuthority()) throw new IOException("QA Wear authority failed");
        return artifact();
    }

    private File artifact() throws IOException {
        File directory = new File(context.getCacheDir(), "wear-installer");
        if (!directory.isDirectory() && !directory.mkdirs()) {
            throw new IOException("Cache unavailable");
        }
        File target = new File(directory, ASSET);
        try (java.io.InputStream input = context.getAssets().open(ASSET);
                FileOutputStream output = new FileOutputStream(target, false)) {
            byte[] buffer = new byte[64 * 1024];
            int count;
            while ((count = input.read(buffer)) >= 0) output.write(buffer, 0, count);
        }
        return target;
    }

    private static String singleSigner(PackageInfo info)
            throws IOException, java.security.GeneralSecurityException {
        if (info.signingInfo == null) throw new IOException("QA signer unavailable");
        android.content.pm.Signature[] signers = info.signingInfo.hasMultipleSigners()
                ? info.signingInfo.getApkContentsSigners()
                : info.signingInfo.getSigningCertificateHistory();
        if (signers.length != 1) throw new IOException("QA signer invalid");
        return hex(MessageDigest.getInstance("SHA-256").digest(signers[0].toByteArray()));
    }

    private static String fileSha256(File file) throws IOException {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            try (java.io.InputStream input = new java.io.FileInputStream(file)) {
                byte[] buffer = new byte[64 * 1024];
                int count;
                while ((count = input.read(buffer)) >= 0) digest.update(buffer, 0, count);
            }
            return hex(digest.digest());
        } catch (java.security.GeneralSecurityException invalid) {
            throw new IOException("QA Wear digest unavailable", invalid);
        }
    }

    private static String hex(byte[] value) {
        StringBuilder result = new StringBuilder(value.length * 2);
        for (byte item : value) result.append(String.format(Locale.ROOT, "%02x", item));
        return result.toString();
    }
}
