package com.littleorbit.data.repository;

import android.content.Context;
import android.content.SharedPreferences;
import com.littleorbit.data.security.SessionStore;
import dagger.hilt.android.qualifiers.ApplicationContext;
import java.util.ArrayList;
import java.util.List;
import javax.inject.Inject;
import javax.inject.Singleton;
import org.json.JSONArray;
import org.json.JSONObject;

/** Small Keystore-encrypted outbox for Smooches that expire after fifteen minutes. */
@Singleton
public final class SmoochOutbox {
    private static final String KEY = "encrypted_pending_smooches";
    private static final long LIFETIME_MILLIS = 15L * 60 * 1000;
    private final SharedPreferences preferences;
    private final SessionStore cipher;

    /** Creates the private outbox. */
    @Inject
    public SmoochOutbox(@ApplicationContext Context context, SessionStore cipher) {
        preferences = context.getSharedPreferences("little-orbit-smooches", Context.MODE_PRIVATE);
        this.cipher = cipher;
    }

    /** Adds one retry-safe send without extending its expiry on later retries. */
    public synchronized void enqueue(String operationId, String emoji, long createdAt) {
        List<Pending> values = pending(createdAt);
        if (values.stream().noneMatch(item -> item.operationId.equals(operationId))) {
            values.add(new Pending(operationId, emoji, createdAt));
        }
        while (values.size() > 5) values.remove(0);
        write(values);
    }

    /** Returns only sends still within the short user-expected delivery window. */
    public synchronized List<Pending> pending(long now) {
        List<Pending> values = read();
        List<Pending> current = values.stream()
                .filter(item -> item.createdAt + LIFETIME_MILLIS > now)
                .toList();
        if (current.size() != values.size()) write(current);
        return new ArrayList<>(current);
    }

    /** Removes one acknowledged or permanently rejected operation. */
    public synchronized void remove(String operationId) {
        List<Pending> values = read();
        values.removeIf(item -> item.operationId.equals(operationId));
        write(values);
    }

    /** Clears queued affection immediately when sign-out or unpair removes authority. */
    public synchronized void clear() { preferences.edit().remove(KEY).apply(); }

    private List<Pending> read() {
        String encrypted = preferences.getString(KEY, null);
        String value = encrypted == null ? null : cipher.open(encrypted).orElse(null);
        if (value == null) return new ArrayList<>();
        try {
            JSONArray array = new JSONArray(value);
            List<Pending> result = new ArrayList<>();
            for (int index = 0; index < array.length(); index++) {
                JSONObject item = array.getJSONObject(index);
                result.add(new Pending(item.getString("id"), item.getString("emoji"),
                        item.getLong("created")));
            }
            return result;
        } catch (Exception invalid) {
            clear();
            return new ArrayList<>();
        }
    }

    private void write(List<Pending> values) {
        try {
            JSONArray array = new JSONArray();
            for (Pending item : values) {
                array.put(new JSONObject()
                        .put("id", item.operationId)
                        .put("emoji", item.emoji)
                        .put("created", item.createdAt));
            }
            preferences.edit().putString(KEY, cipher.seal(array.toString())).apply();
        } catch (Exception invalid) {
            throw new IllegalStateException("Could not protect the Smooch outbox", invalid);
        }
    }

    /** One immutable pending send with its original creation time. */
    public record Pending(String operationId, String emoji, long createdAt) {}
}
