package com.littleorbit.mobile;

import android.content.Context;
import android.content.SharedPreferences;
import com.littleorbit.data.security.SessionStore;
import dagger.hilt.android.qualifiers.ApplicationContext;
import java.time.Instant;
import java.util.UUID;
import javax.inject.Inject;
import javax.inject.Singleton;

/** Persists a random install identifier and content-free delivery diagnostics. */
@Singleton
public final class NotificationDeviceStore {
    private static final String ID = "device_id";
    private static final String LEGACY_PUSH_TOKEN = "push_token";
    private static final String SEALED_PUSH_TOKEN = "push_token_sealed_v1";
    private static final String REJECTED_PUSH_DIGEST = "rejected_push_digest_v1";
    private static final String PUSH_RECOVERY_ATTEMPTED = "push_recovery_attempted_v1";
    private final SharedPreferences values;
    private final SessionStore secrets;

    /** Opens installation-local state that contains no hardware identifiers or event content. */
    @Inject
    public NotificationDeviceStore(
            @ApplicationContext Context context,
            SessionStore secrets) {
        values = context.getSharedPreferences("notification-device", Context.MODE_PRIVATE);
        this.secrets = secrets;
        migrateLegacyPushToken();
    }

    /** Opens the same protected store from Android-owned service callbacks. */
    public NotificationDeviceStore(Context context) {
        this(context.getApplicationContext(), new SessionStore(context.getApplicationContext()));
    }

    /** Returns the stable random identifier for this application installation. */
    public synchronized String id() {
        String existing = values.getString(ID, null);
        if (existing != null) return existing;
        String created = UUID.randomUUID().toString();
        values.edit().putString(ID, created).commit();
        return created;
    }

    /** Returns the latest private FCM address, or null when polling is in use. */
    public synchronized String pushToken() {
        String stored = values.getString(SEALED_PUSH_TOKEN, null);
        if (stored == null) return null;
        String token = secrets.open(stored).orElse(null);
        if (token == null) values.edit().remove(SEALED_PUSH_TOKEN).commit();
        return token;
    }

    /** Saves an FCM address encrypted by Android Keystore and reports acceptance. */
    public synchronized boolean savePushToken(String token) {
        if (token == null || token.isBlank()) return false;
        String rejected = values.getString(REJECTED_PUSH_DIGEST, null);
        if (PushTokenRecovery.matches(rejected, token)) {
            values.edit().remove(LEGACY_PUSH_TOKEN).remove(SEALED_PUSH_TOKEN).commit();
            return false;
        }
        try {
            values.edit()
                    .putString(SEALED_PUSH_TOKEN, secrets.seal(token))
                    .remove(LEGACY_PUSH_TOKEN)
                    .remove(REJECTED_PUSH_DIGEST)
                    .commit();
            return true;
        } catch (IllegalStateException unavailableKeystore) {
            clearPushToken();
            return false;
        }
    }

    /** Quarantines a rejected address and permits one automatic Firebase rotation. */
    public synchronized boolean rejectPushToken(String token) {
        if (token == null || token.isBlank()) return false;
        String digest = PushTokenRecovery.digest(token);
        boolean attempted = values.getBoolean(PUSH_RECOVERY_ATTEMPTED, false);
        String prior = values.getString(REJECTED_PUSH_DIGEST, null);
        values.edit()
                .remove(LEGACY_PUSH_TOKEN)
                .remove(SEALED_PUSH_TOKEN)
                .putString(REJECTED_PUSH_DIGEST, digest)
                .putBoolean(PUSH_RECOVERY_ATTEMPTED, true)
                .commit();
        return PushTokenRecovery.shouldRotate(attempted, prior, token);
    }

    /** Clears one-shot recovery state after the server accepts the current address. */
    public synchronized void pushTokenAccepted() {
        values.edit()
                .remove(REJECTED_PUSH_DIGEST)
                .remove(PUSH_RECOVERY_ATTEMPTED)
                .apply();
    }

    /** Removes the local FCM address when Firebase invalidates this installation. */
    public synchronized void clearPushToken() {
        values.edit()
                .remove(LEGACY_PUSH_TOKEN)
                .remove(SEALED_PUSH_TOKEN)
                .remove(REJECTED_PUSH_DIGEST)
                .remove(PUSH_RECOVERY_ATTEMPTED)
                .commit();
    }

    /** Rotates delivery scope and removes cached status after an account change. */
    public synchronized void clearForAccountChange() {
        values.edit().clear().commit();
    }

    /** Records the latest successful check without storing notification content. */
    public void checked(int delivered) {
        values.edit()
                .putString("last_check", Instant.now().toString())
                .putString("last_result", delivered == 0 ? "No alerts waiting" : "Delivered " + delivered)
                .putInt("last_count", delivered)
                .apply();
    }

    /** Records a sanitized delivery state for user-visible diagnostics. */
    public void failed(String result) {
        values.edit()
                .putString("last_check", Instant.now().toString())
                .putString("last_result", result)
                .apply();
    }

    /** Returns concise diagnostics that never include event or account content. */
    public String diagnostics() {
        String check = values.getString("last_check", "Never checked");
        String result = values.getString("last_result", "Waiting for first check");
        return result + "\nLast check: " + check;
    }

    private synchronized void migrateLegacyPushToken() {
        String legacy = values.getString(LEGACY_PUSH_TOKEN, null);
        if (legacy == null) return;
        if (!legacy.isBlank() && values.getString(SEALED_PUSH_TOKEN, null) == null) {
            savePushToken(legacy);
        } else {
            values.edit().remove(LEGACY_PUSH_TOKEN).commit();
        }
    }
}
