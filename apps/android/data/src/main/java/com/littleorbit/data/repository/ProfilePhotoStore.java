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
                emptyToNull(values.getString("partner_name", EMPTY)), openBytes("partner_photo"));
    }

    synchronized int revision(boolean partner) {
        return values.getInt(partner ? "partner_revision" : "my_revision", 0);
    }

    synchronized String hash(boolean partner) {
        return values.getString(partner ? "partner_hash" : "my_hash", "");
    }

    synchronized void save(
            String myName, int myRevision, String myHash, byte[] myPhoto,
            String partnerName, int partnerRevision, String partnerHash, byte[] partnerPhoto) {
        SharedPreferences.Editor edit = values.edit()
                .putString("my_name", myName)
                .putInt("my_revision", myRevision)
                .putString("my_hash", myHash == null ? EMPTY : myHash)
                .putString("partner_name", partnerName == null ? EMPTY : partnerName)
                .putInt("partner_revision", partnerRevision)
                .putString("partner_hash", partnerHash == null ? EMPTY : partnerHash);
        putBytes(edit, "my_photo", myPhoto);
        putBytes(edit, "partner_photo", partnerPhoto);
        edit.apply();
    }

    synchronized void clearPartner() {
        values.edit()
                .remove("my_revision").remove("my_hash").remove("my_photo")
                .remove("partner_name").remove("partner_revision").remove("partner_hash")
                .remove("partner_photo").apply();
    }

    synchronized void clearAll() { values.edit().clear().apply(); }

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
