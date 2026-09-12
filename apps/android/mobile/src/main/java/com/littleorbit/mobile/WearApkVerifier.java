package com.littleorbit.mobile;

import android.content.Context;
import android.content.pm.FeatureInfo;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import com.littleorbit.data.repository.NetworkReleaseRepository;
import dagger.hilt.android.qualifiers.ApplicationContext;
import java.io.File;
import java.io.FileInputStream;
import java.security.MessageDigest;
import java.util.Locale;
import javax.inject.Inject;
import javax.inject.Singleton;

/** Verifies the Wear APK without comparing it to the phone app's installed version. */
@Singleton
public final class WearApkVerifier {
    private final Context context;

    /** Creates an archive verifier. */
    @Inject public WearApkVerifier(@ApplicationContext Context context) { this.context = context; }

    /** Returns null only when bytes, package, version, watch feature, and signer all match. */
    public String verify(WearReleaseMetadata release, File apk) {
        try {
            if (!apk.isFile() || apk.length() != release.sizeBytes()) return "wear_size_mismatch";
            if (!release.sha256().equals(sha256(apk))) return "wear_hash_mismatch";
            PackageInfo info = context.getPackageManager().getPackageArchiveInfo(
                    apk.getPath(), PackageManager.GET_SIGNING_CERTIFICATES
                            | PackageManager.GET_CONFIGURATIONS);
            if (info == null || !release.packageName().equals(info.packageName)) {
                return "wear_package_mismatch";
            }
            if (info.getLongVersionCode() != release.versionCode()) return "wear_version_mismatch";
            if (!requiresWatch(info)) return "wear_feature_missing";
            if (!NetworkReleaseRepository.EXPECTED_SIGNER.equals(release.signerSha256())
                    || !hasSigner(info, release.signerSha256())) return "wear_signer_mismatch";
            return null;
        } catch (Exception invalid) { return "wear_validation_failed"; }
    }

    private static boolean requiresWatch(PackageInfo info) {
        if (info.reqFeatures == null) return false;
        for (FeatureInfo feature : info.reqFeatures) {
            if ("android.hardware.type.watch".equals(feature.name)) return true;
        }
        return false;
    }

    private static boolean hasSigner(PackageInfo info, String expected) throws Exception {
        if (info.signingInfo == null) return false;
        android.content.pm.Signature[] signers = info.signingInfo.hasMultipleSigners()
                ? info.signingInfo.getApkContentsSigners()
                : info.signingInfo.getSigningCertificateHistory();
        for (android.content.pm.Signature signer : signers) {
            if (expected.equals(hex(MessageDigest.getInstance("SHA-256")
                    .digest(signer.toByteArray())))) return true;
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

    private static String hex(byte[] value) {
        StringBuilder result = new StringBuilder(value.length * 2);
        for (byte item : value) result.append(String.format(Locale.ROOT, "%02x", item));
        return result.toString();
    }
}
