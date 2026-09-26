package com.littleorbit.mobile;

import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;

/** Verifies retained attachment bytes before any offline preview uses them. */
final class AttachmentFileIntegrity {
    private AttachmentFileIntegrity() {}

    static boolean matches(File file, String expectedSha256) {
        if (!file.isFile() || expectedSha256 == null) return false;
        try (InputStream input = new FileInputStream(file)) {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] buffer = new byte[64 * 1024];
            for (int count; (count = input.read(buffer)) >= 0; ) {
                if (count > 0) digest.update(buffer, 0, count);
            }
            return expectedSha256.equals(lowerHex(digest.digest()));
        } catch (IOException | NoSuchAlgorithmException failure) {
            return false;
        }
    }

    private static String lowerHex(byte[] bytes) {
        char[] result = new char[bytes.length * 2];
        char[] digits = "0123456789abcdef".toCharArray();
        for (int index = 0; index < bytes.length; index++) {
            int value = bytes[index] & 0xff;
            result[index * 2] = digits[value >>> 4];
            result[index * 2 + 1] = digits[value & 0x0f];
        }
        return new String(result);
    }
}
