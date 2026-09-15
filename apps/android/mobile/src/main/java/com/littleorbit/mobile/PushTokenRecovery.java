package com.littleorbit.mobile;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;

/** Privacy-safe policy for quarantining and rotating an FCM registration address. */
final class PushTokenRecovery {
    private PushTokenRecovery() {}

    /** Returns a non-reversible local comparison value for a high-entropy token. */
    static String digest(String token) {
        try {
            MessageDigest hash = MessageDigest.getInstance("SHA-256");
            return toHex(hash.digest(token.getBytes(StandardCharsets.UTF_8)));
        } catch (NoSuchAlgorithmException impossible) {
            throw new IllegalStateException("SHA-256 is unavailable", impossible);
        }
    }

    /** Reports whether a token matches the locally quarantined address. */
    static boolean matches(String rejectedDigest, String token) {
        return rejectedDigest != null
                && MessageDigest.isEqual(
                        rejectedDigest.getBytes(StandardCharsets.US_ASCII),
                        digest(token).getBytes(StandardCharsets.US_ASCII));
    }

    /** Allows only the first rotation attempt until an address is accepted. */
    static boolean shouldRotate(boolean alreadyAttempted, String rejectedDigest, String token) {
        return !alreadyAttempted && !matches(rejectedDigest, token);
    }

    private static String toHex(byte[] value) {
        char[] output = new char[value.length * 2];
        char[] alphabet = "0123456789abcdef".toCharArray();
        for (int index = 0; index < value.length; index++) {
            int current = value[index] & 0xff;
            output[index * 2] = alphabet[current >>> 4];
            output[index * 2 + 1] = alphabet[current & 0x0f];
        }
        return new String(output);
    }
}
