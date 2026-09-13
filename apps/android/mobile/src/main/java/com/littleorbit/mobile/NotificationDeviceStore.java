package com.littleorbit.mobile;

import android.content.Context;
import android.content.SharedPreferences;
import dagger.hilt.android.qualifiers.ApplicationContext;
import java.time.Instant;
import java.util.UUID;
import javax.inject.Inject;
import javax.inject.Singleton;

/** Persists a random install identifier and content-free delivery diagnostics. */
@Singleton
public final class NotificationDeviceStore {
    private static final String ID = "device_id";
    private final SharedPreferences values;

    /** Opens installation-local state that contains no hardware identifiers or event content. */
    @Inject
    public NotificationDeviceStore(@ApplicationContext Context context) {
        values = context.getSharedPreferences("notification-device", Context.MODE_PRIVATE);
    }

    /** Returns the stable random identifier for this application installation. */
    public synchronized String id() {
        String existing = values.getString(ID, null);
        if (existing != null) return existing;
        String created = UUID.randomUUID().toString();
        values.edit().putString(ID, created).commit();
        return created;
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
}
