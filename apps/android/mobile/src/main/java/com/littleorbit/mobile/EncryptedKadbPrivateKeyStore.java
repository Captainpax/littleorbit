package com.littleorbit.mobile;

import android.content.Context;
import android.content.SharedPreferences;
import android.util.Base64;
import com.littleorbit.data.security.SessionStore;
import dagger.hilt.android.qualifiers.ApplicationContext;
import javax.inject.Inject;
import javax.inject.Singleton;

/** Persists the wireless-ADB private key encrypted by Android Keystore. */
@Singleton
public final class EncryptedKadbPrivateKeyStore {
    private final SharedPreferences values;
    private final SessionStore crypto;

    /** Creates an app-private ADB identity store. */
    @Inject
    public EncryptedKadbPrivateKeyStore(
            @ApplicationContext Context context, SessionStore crypto) {
        values = context.getSharedPreferences("little-orbit-wear-adb", Context.MODE_PRIVATE);
        this.crypto = crypto;
    }

    public synchronized byte[] readPrivateKeyPem() {
        String sealed = values.getString("private_key", null);
        if (sealed == null) return null;
        return crypto.open(sealed).map(value -> Base64.decode(value, Base64.NO_WRAP)).orElse(null);
    }

    public synchronized void writePrivateKeyPemAtomic(byte[] value) {
        String encoded = Base64.encodeToString(value, Base64.NO_WRAP);
        if (!values.edit().putString("private_key", crypto.seal(encoded)).commit()) {
            throw new IllegalStateException("Could not persist watch authorization");
        }
    }

    public synchronized void clear() {
        if (!values.edit().clear().commit()) {
            throw new IllegalStateException("Could not clear watch authorization");
        }
    }

    /** Returns whether a reusable authorized identity exists locally. */
    public synchronized boolean isRemembered() { return values.contains("private_key"); }
}
