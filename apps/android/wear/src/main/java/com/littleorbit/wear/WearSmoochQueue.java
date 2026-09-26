package com.littleorbit.wear;

import android.content.Context;
import android.content.SharedPreferences;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;
import java.nio.charset.StandardCharsets;
import java.security.KeyStore;
import java.util.ArrayList;
import java.util.List;
import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;
import org.json.JSONArray;
import org.json.JSONObject;

/** Five-item, fifteen-minute encrypted queue for watch-origin Smooch requests. */
final class WearSmoochQueue {
    private static final String KEY_ALIAS = "little-orbit-watch-smooch-v1";
    private static final String PREFERENCES = "little_orbit_watch_smooch_v1";
    private static final String VALUE = "sealed_queue";
    private WearSmoochQueue() {}

    static synchronized void enqueue(
            Context context,
            String operationId,
            String emoji,
            long createdAt,
            String relationshipId,
            long relationshipGeneration,
            long watchGeneration) {
        long now = System.currentTimeMillis();
        List<Pending> values = WearSmoochQueuePolicy.enqueue(
                pending(context, now),
                new Pending(operationId, emoji, createdAt, relationshipId,
                        relationshipGeneration, watchGeneration), now);
        write(context, values);
    }

    static synchronized List<Pending> pending(Context context, long now) {
        List<Pending> values = read(context);
        List<Pending> current = WearSmoochQueuePolicy.current(values, now);
        if (current.size() != values.size()) write(context, current);
        return List.copyOf(current);
    }

    static synchronized void remove(Context context, String operationId) {
        List<Pending> values = read(context);
        values.removeIf(item -> item.operationId().equals(operationId));
        write(context, values);
    }

    static synchronized int count(Context context) {
        return pending(context, System.currentTimeMillis()).size();
    }

    static synchronized void clear(Context context) {
        preferences(context).edit().remove(VALUE).apply();
    }

    private static List<Pending> read(Context context) {
        String sealed = preferences(context).getString(VALUE, null);
        if (sealed == null) return new ArrayList<>();
        try {
            JSONArray array = new JSONArray(open(sealed));
            List<Pending> result = new ArrayList<>();
            for (int index = 0; index < array.length(); index++) {
                JSONObject item = array.getJSONObject(index);
                result.add(new Pending(
                        item.getString("id"), item.getString("emoji"), item.getLong("created"),
                        item.getString("relationship_id"), item.getLong("relationship_generation"),
                        item.getLong("watch_generation")));
            }
            return result;
        } catch (Exception invalid) {
            clear(context);
            return new ArrayList<>();
        }
    }

    private static void write(Context context, List<Pending> values) {
        try {
            JSONArray array = new JSONArray();
            for (Pending item : values) {
                array.put(new JSONObject()
                        .put("id", item.operationId()).put("emoji", item.emoji())
                        .put("created", item.createdAt())
                        .put("relationship_id", item.relationshipId())
                        .put("relationship_generation", item.relationshipGeneration())
                        .put("watch_generation", item.watchGeneration()));
            }
            preferences(context).edit().putString(VALUE, seal(array.toString())).apply();
        } catch (Exception invalid) {
            throw new IllegalStateException("Could not protect watch Smooch queue", invalid);
        }
    }

    private static String seal(String value) throws Exception {
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.ENCRYPT_MODE, key());
        byte[] encrypted = cipher.doFinal(value.getBytes(StandardCharsets.UTF_8));
        return Base64.encodeToString(cipher.getIV(), Base64.NO_WRAP) + "."
                + Base64.encodeToString(encrypted, Base64.NO_WRAP);
    }

    private static String open(String value) throws Exception {
        String[] pieces = value.split("\\.", 2);
        if (pieces.length != 2) throw new IllegalArgumentException("sealed value");
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.DECRYPT_MODE, key(),
                new GCMParameterSpec(128, Base64.decode(pieces[0], Base64.NO_WRAP)));
        return new String(cipher.doFinal(Base64.decode(pieces[1], Base64.NO_WRAP)),
                StandardCharsets.UTF_8);
    }

    private static SecretKey key() throws Exception {
        KeyStore store = KeyStore.getInstance("AndroidKeyStore");
        store.load(null);
        java.security.Key existing = store.getKey(KEY_ALIAS, null);
        if (existing instanceof SecretKey secret) return secret;
        KeyGenerator generator = KeyGenerator.getInstance(
                KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore");
        generator.init(new KeyGenParameterSpec.Builder(
                KEY_ALIAS, KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build());
        return generator.generateKey();
    }

    private static SharedPreferences preferences(Context context) {
        return context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE);
    }

    record Pending(
            String operationId,
            String emoji,
            long createdAt,
            String relationshipId,
            long relationshipGeneration,
            long watchGeneration) {}
}
