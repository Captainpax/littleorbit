package com.littleorbit.mobile;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNull;

import android.content.Context;
import androidx.test.core.app.ApplicationProvider;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import org.junit.Test;
import org.junit.runner.RunWith;

@RunWith(AndroidJUnit4.class)
public final class WearArtifactVerifierInstrumentedTest {
    @Test public void embeddedArtifactRejectsEveryMutatedAuthorityField() throws Exception {
        Context context = ApplicationProvider.getApplicationContext();
        WearReleaseClient source = new WearReleaseClient(null, null, context);
        WearReleaseMetadata trusted = source.metadata();
        File apk = source.download(trusted);
        WearApkVerifier verifier = new WearApkVerifier(context);

        assertNull(verifier.verify(trusted, apk));
        assertEquals("wear_size_mismatch", verifier.verify(copy(trusted,
                trusted.sizeBytes() + 1, trusted.sha256(), trusted.packageName(),
                trusted.versionCode(), trusted.signerSha256()), apk));
        assertEquals("wear_hash_mismatch", verifier.verify(copy(trusted,
                trusted.sizeBytes(), "00", trusted.packageName(),
                trusted.versionCode(), trusted.signerSha256()), apk));
        assertEquals("wear_package_mismatch", verifier.verify(copy(trusted,
                trusted.sizeBytes(), trusted.sha256(), "invalid.package",
                trusted.versionCode(), trusted.signerSha256()), apk));
        assertEquals("wear_version_mismatch", verifier.verify(copy(trusted,
                trusted.sizeBytes(), trusted.sha256(), trusted.packageName(),
                trusted.versionCode() + 1, trusted.signerSha256()), apk));
        assertEquals("wear_signer_mismatch", verifier.verify(copy(trusted,
                trusted.sizeBytes(), trusted.sha256(), trusted.packageName(),
                trusted.versionCode(), "00"), apk));
        assertEquals("wear_size_mismatch", verifier.verify(trusted, truncated(context, apk)));
    }

    private static WearReleaseMetadata copy(
            WearReleaseMetadata value,
            long size,
            String hash,
            String packageName,
            int versionCode,
            String signer) {
        return new WearReleaseMetadata(
                value.version(), versionCode, value.apkUrl(), hash, size,
                packageName, signer, value.minimumAndroid(), false);
    }

    private static File truncated(Context context, File source) throws Exception {
        File target = new File(context.getCacheDir(), "truncated-wear.apk");
        try (FileInputStream input = new FileInputStream(source);
                FileOutputStream output = new FileOutputStream(target, false)) {
            byte[] bytes = new byte[128];
            int count = input.read(bytes);
            if (count > 0) output.write(bytes, 0, count);
        }
        return target;
    }
}
