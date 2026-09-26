package com.littleorbit.data.repository;

import android.content.Context;
import android.content.SharedPreferences;
import android.util.Base64;
import com.littleorbit.data.security.SessionStore;
import dagger.hilt.android.qualifiers.ApplicationContext;
import java.util.Optional;
import javax.inject.Inject;
import javax.inject.Singleton;

/** Stores only small thumbnails, encrypted by the app's Android Keystore key. */
@Singleton
final class ProfilePhotoStore {
    private static final String EMPTY = "";
    private final SharedPreferences values;
    private final SessionStore crypto;

    @Inject
    ProfilePhotoStore(@ApplicationContext Context context, SessionStore crypto) {
        this.values = context.getSharedPreferences("little-orbit-profile", Context.MODE_PRIVATE);
        this.crypto = crypto;
    }

    synchronized ProfileRepository.State read() {
        return new ProfileRepository.State(
                values.getString("my_name", "You"), openBytes("my_photo"),
                emptyToNull(values.getString("partner_name", EMPTY)), openBytes("partner_photo"),
                values.getInt("my_name_revision", 0),
                values.getBoolean("my_name_assigned", false),
                values.getInt("partner_name_revision", 0),
                values.getBoolean("partner_name_assigned", false));
    }

    synchronized int revision(boolean partner) {
        return values.getInt(partner ? "partner_revision" : "my_revision", 0);
    }

    synchronized String hash(boolean partner) {
        return values.getString(partner ? "partner_hash" : "my_hash", "");
    }

    synchronized void save(
            String myName, int myRevision, String myHash, byte[] myPhoto,
            String partnerName, int partnerRevision, String partnerHash, byte[] partnerPhoto,
            int myNameRevision, boolean myNameAssigned,
            int partnerNameRevision, boolean partnerNameAssigned) {
        SharedPreferences.Editor edit = values.edit()
                .putString("my_name", myName)
                .putInt("my_revision", myRevision)
                .putString("my_hash", myHash == null ? EMPTY : myHash)
                .putString("partner_name", partnerName == null ? EMPTY : partnerName)
                .putInt("partner_revision", partnerRevision)
                .putString("partner_hash", partnerHash == null ? EMPTY : partnerHash)
                .putInt("my_name_revision", myNameRevision)
                .putBoolean("my_name_assigned", myNameAssigned)
                .putInt("partner_name_revision", partnerNameRevision)
                .putBoolean("partner_name_assigned", partnerNameAssigned);
        putBytes(edit, "my_photo", myPhoto);
        putBytes(edit, "partner_photo", partnerPhoto);
        edit.apply();
    }

    synchronized void clearPartner() {
        values.edit()
                .remove("my_name").remove("my_revision").remove("my_hash").remove("my_photo")
                .remove("my_name_revision").remove("my_name_assigned")
                .remove("partner_name").remove("partner_revision").remove("partner_hash")
                .remove("partner_name_revision").remove("partner_name_assigned")
                .remove("partner_photo")
                .remove("pending_name_action").remove("pending_name_operation")
                .remove("pending_name_revision").remove("pending_name_value").apply();
    }

    synchronized void clearAll() { values.edit().clear().apply(); }

    synchronized PendingName pendingName() {
        String action = values.getString("pending_name_action", EMPTY);
        String operation = values.getString("pending_name_operation", EMPTY);
        if (action.isBlank() || operation.isBlank()) return null;
        String name = null;
        String sealed = values.getString("pending_name_value", null);
        if (sealed != null) name = crypto.open(sealed).orElse(null);
        if ("set".equals(action) && name == null) {
            clearPendingName();
            return null;
        }
        return new PendingName(
                action,
                operation,
                values.getInt("pending_name_revision", 0),
                name);
    }

    synchronized void savePendingName(PendingName pending) {
        SharedPreferences.Editor edit = values.edit()
                .putString("pending_name_action", pending.action())
                .putString("pending_name_operation", pending.operationId())
                .putInt("pending_name_revision", pending.expectedRevision());
        if (pending.displayName() == null) edit.remove("pending_name_value");
        else edit.putString("pending_name_value", crypto.seal(pending.displayName()));
        edit.commit();
    }

    synchronized void clearPendingName() {
        values.edit()
                .remove("pending_name_action")
                .remove("pending_name_operation")
                .remove("pending_name_revision")
                .remove("pending_name_value")
                .commit();
    }

    record PendingName(
            String action, String operationId, int expectedRevision, String displayName) {}

    private void putBytes(SharedPreferences.Editor edit, String key, byte[] bytes) {
        if (bytes == null || bytes.length == 0) edit.remove(key);
        else edit.putString(key, crypto.seal(Base64.encodeToString(bytes, Base64.NO_WRAP)));
    }

    private byte[] openBytes(String key) {
        String sealed = values.getString(key, null);
        if (sealed == null) return null;
        Optional<String> value = crypto.open(sealed);
        if (value.isEmpty()) return null;
        try { return Base64.decode(value.get(), Base64.NO_WRAP); }
        catch (IllegalArgumentException invalid) { return null; }
    }

    private static String emptyToNull(String value) {
        return value == null || value.isBlank() ? null : value;
    }
}
