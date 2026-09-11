package com.littleorbit.mobile;

import android.content.Context;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import com.littleorbit.data.repository.NetworkReleaseRepository;
import com.littleorbit.domain.ReleaseUpdate;
import dagger.hilt.android.qualifiers.ApplicationContext;
import java.io.File;
import java.io.FileInputStream;
import java.security.MessageDigest;
import java.util.Locale;
import javax.inject.Inject;
import javax.inject.Singleton;

/** Inspects downloaded APK bytes without starting Android's installer. */
@Singleton
public final class ApkVerifier {
    private final Context context;

    /** Creates an inspector around the application package manager. */
    @Inject
    public ApkVerifier(@ApplicationContext Context context) {
        this.context = context;
    }

    /** Returns a sanitized failure code, or {@code null} when every trust check passes. */
    public String verify(ReleaseUpdate release, File apk) {
        try {
            if (!apk.isFile() || apk.length() != release.sizeBytes()) return "apk_size_mismatch";
            if (!release.sha256().equals(sha256(apk))) return "apk_hash_mismatch";
            PackageInfo archive = context.getPackageManager().getPackageArchiveInfo(
                    apk.getAbsolutePath(), PackageManager.GET_SIGNING_CERTIFICATES);
            if (archive == null || !release.packageName().equals(archive.packageName)) {
                return "apk_package_mismatch";
            }
            if (versionCode(archive) != release.versionCode()
                    || release.versionCode() <= installedVersionCode()) return "apk_version_mismatch";
            if (!hasSigner(archive, release.signerSha256())
                    || !release.signerSha256().equals(NetworkReleaseRepository.EXPECTED_SIGNER)) {
                return "apk_signer_mismatch";
            }
            return null;
        } catch (Exception invalid) {
            return "apk_validation_failed";
        }
    }

    /** Returns the installed package's monotonic Android version code. */
    public long installedVersionCode() {
        try {
            PackageInfo info = context.getPackageManager().getPackageInfo(
                    context.getPackageName(), PackageManager.GET_SIGNING_CERTIFICATES);
            return versionCode(info);
        } catch (PackageManager.NameNotFoundException impossible) {
            return BuildConfig.VERSION_CODE;
        }
    }

    private static long versionCode(PackageInfo info) {
        return info.getLongVersionCode();
    }

    private static boolean hasSigner(PackageInfo info, String expected) throws Exception {
        if (info.signingInfo == null) return false;
        android.content.pm.Signature[] values = info.signingInfo.hasMultipleSigners()
                ? info.signingInfo.getApkContentsSigners()
                : info.signingInfo.getSigningCertificateHistory();
        for (android.content.pm.Signature value : values) {
            byte[] certificate = value.toByteArray();
            if (expected.equals(hex(MessageDigest.getInstance("SHA-256").digest(certificate)))) {
                return true;
            }
        }
        return false;
    }

    private static String sha256(File file) throws Exception {
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        try (FileInputStream input = new FileInputStream(file)) {
            byte[] buffer = new byte[64 * 1024];
            int count;
            while ((count = input.read(buffer)) >= 0) digest.update(buffer, 0, count);
        }
        return hex(digest.digest());
    }

    private static String hex(byte[] bytes) {
        StringBuilder result = new StringBuilder(bytes.length * 2);
        for (byte value : bytes) result.append(String.format(Locale.ROOT, "%02x", value));
        return result.toString();
    }
}
