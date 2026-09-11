package com.littleorbit.data.security;

import android.content.Context;
import android.content.SharedPreferences;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;
import dagger.hilt.android.qualifiers.ApplicationContext;
import java.nio.charset.StandardCharsets;
import java.security.GeneralSecurityException;
import java.security.KeyStore;
import java.util.Optional;
import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;
import javax.inject.Inject;
import javax.inject.Singleton;

/** Stores the opaque session encrypted by an Android Keystore key. */
@Singleton
public final class SessionStore {
    private static final String KEY_ALIAS = "little-orbit-session";
    private static final String VALUE_KEY = "encrypted-session";
    private static final String TRANSFORMATION = "AES/GCM/NoPadding";
    private final SharedPreferences preferences;

    /** Creates a store whose preferences never contain a plaintext token. */
    @Inject
    public SessionStore(@ApplicationContext Context context) {
        preferences = context.getSharedPreferences("little-orbit-secure", Context.MODE_PRIVATE);
    }

    /** Encrypts and replaces the active token. */
    public synchronized void save(String token) {
        preferences.edit().putString(VALUE_KEY, seal(token)).apply();
    }

    /** Decrypts the active token or fails closed after invalidation. */
    public synchronized Optional<String> read() {
        String stored = preferences.getString(VALUE_KEY, null);
        Optional<String> result = stored == null ? Optional.empty() : open(stored);
        if (stored != null && result.isEmpty()) {
            clear();
        }
        return result;
    }

    /** Encrypts a private local payload for another data repository. */
    public synchronized String seal(String plaintext) {
        try {
            Cipher cipher = Cipher.getInstance(TRANSFORMATION);
            cipher.init(Cipher.ENCRYPT_MODE, key());
            byte[] ciphertext = cipher.doFinal(plaintext.getBytes(StandardCharsets.UTF_8));
            byte[] encoded = new byte[cipher.getIV().length + ciphertext.length];
            System.arraycopy(cipher.getIV(), 0, encoded, 0, cipher.getIV().length);
            System.arraycopy(ciphertext, 0, encoded, cipher.getIV().length, ciphertext.length);
            return Base64.encodeToString(encoded, Base64.NO_WRAP);
        } catch (GeneralSecurityException | java.io.IOException exception) {
            throw new IllegalStateException("Android Keystore could not protect the session", exception);
        }
    }

    /** Decrypts a private local payload and returns empty after key invalidation. */
    public synchronized Optional<String> open(String stored) {
        try {
            byte[] encoded = Base64.decode(stored, Base64.NO_WRAP);
            if (encoded.length <= 12) {
                throw new GeneralSecurityException("Encrypted session is truncated");
            }
            byte[] iv = java.util.Arrays.copyOfRange(encoded, 0, 12);
            byte[] ciphertext = java.util.Arrays.copyOfRange(encoded, 12, encoded.length);
            Cipher cipher = Cipher.getInstance(TRANSFORMATION);
            cipher.init(Cipher.DECRYPT_MODE, key(), new GCMParameterSpec(128, iv));
            return Optional.of(new String(cipher.doFinal(ciphertext), StandardCharsets.UTF_8));
        } catch (GeneralSecurityException | java.io.IOException | IllegalArgumentException exception) {
            return Optional.empty();
        }
    }

    /** Removes the only local copy of the session. */
    public synchronized void clear() {
        preferences.edit().remove(VALUE_KEY).apply();
    }

    private SecretKey key() throws GeneralSecurityException, java.io.IOException {
        KeyStore store = KeyStore.getInstance("AndroidKeyStore");
        store.load(null);
        SecretKey existing = (SecretKey) store.getKey(KEY_ALIAS, null);
        if (existing != null) {
            return existing;
        }
        KeyGenerator generator = KeyGenerator.getInstance(
                KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore");
        generator.init(new KeyGenParameterSpec.Builder(
                KEY_ALIAS, KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .build());
        return generator.generateKey();
    }
}
