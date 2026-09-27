package com.littleorbit.data;

import android.content.Context;
import android.content.SharedPreferences;
import dagger.hilt.android.qualifiers.ApplicationContext;
import javax.inject.Inject;
import javax.inject.Singleton;

/** App-private state for the one explicitly managed Wear node. */
@Singleton
public final class ManagedWatchStore {
    public static final String DESTINATION_TOGETHER = "together";
    public static final String DESTINATION_COUNTDOWN = "countdown";
    public static final String DESTINATION_SMOOCH = "smooch";
    private static final String PREFERENCES = "little-orbit-managed-watch-v1";
    private final SharedPreferences values;

    /** Creates the durable phone-side watch preference boundary. */
    @Inject
    public ManagedWatchStore(@ApplicationContext Context context) {
        values = context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE);
    }

    /** Selects one watch and advances the monotonic target generation when it changes. */
    public synchronized Snapshot select(String nodeId, String displayName) {
        if (nodeId == null || nodeId.isBlank()) throw new IllegalArgumentException("nodeId");
        Snapshot current = read();
        long generation = current.nodeId().equals(nodeId)
                ? current.generation() : nextGeneration(current.generation());
        Snapshot selected = new Snapshot(
                nodeId, safeName(displayName), generation, true,
                current.showPhotos(), current.showCountdownTitles(), current.smoochEnabled(),
                current.updateAlerts(), validDestination(current.defaultDestination()),
                current.nodeId().equals(nodeId) ? current.versionName() : "",
                current.nodeId().equals(nodeId) ? current.versionCode() : 0,
                current.nodeId().equals(nodeId) ? current.protocolVersion() : 0,
                current.nodeId().equals(nodeId) ? current.queuedActions() : 0,
                current.nodeId().equals(nodeId) ? current.lastSeenAt() : 0);
        persist(selected);
        return selected;
    }

    /** Disables synchronization and forgets the selected watch after private removal. */
    public synchronized Snapshot clearTarget() {
        Snapshot current = read();
        Snapshot cleared = new Snapshot(
                "", "", nextGeneration(current.generation()), false,
                true, true, true, true, DESTINATION_TOGETHER,
                "", 0, 0, 0, 0);
        persist(cleared);
        return cleared;
    }

    /** Updates the curated preferences without changing target authority. */
    public synchronized Snapshot updatePreferences(
            boolean photos,
            boolean countdownTitles,
            boolean smooches,
            boolean updateAlerts,
            String destination) {
        Snapshot current = read();
        String resolved = resolveDestination(destination, smooches);
        Snapshot updated = new Snapshot(
                current.nodeId(), current.displayName(), current.generation(), current.enabled(),
                photos, countdownTitles, smooches, updateAlerts, resolved,
                current.versionName(), current.versionCode(), current.protocolVersion(),
                current.queuedActions(), current.lastSeenAt());
        persist(updated);
        return updated;
    }

    /** Stores content-free status only when it came from the selected node. */
    public synchronized boolean recordStatus(
            String nodeId,
            String versionName,
            int versionCode,
            int protocolVersion,
            int queuedActions,
            long observedAt) {
        Snapshot current = read();
        if (!current.enabled() || !current.nodeId().equals(nodeId)) return false;
        Snapshot updated = new Snapshot(
                current.nodeId(), current.displayName(), current.generation(), true,
                current.showPhotos(), current.showCountdownTitles(), current.smoochEnabled(),
                current.updateAlerts(), current.defaultDestination(),
                safeName(versionName), Math.max(0, versionCode), Math.max(0, protocolVersion),
                Math.max(0, queuedActions), Math.max(0, observedAt));
        persist(updated);
        return true;
    }

    /** Returns current watch selection, preferences, and status metadata. */
    public synchronized Snapshot read() {
        return new Snapshot(
                values.getString("node_id", ""), values.getString("display_name", ""),
                values.getLong("generation", 0), values.getBoolean("enabled", false),
                values.getBoolean("show_photos", true),
                values.getBoolean("show_countdown_titles", true),
                values.getBoolean("smooch_enabled", true),
                values.getBoolean("update_alerts", true),
                validDestination(values.getString("default_destination", DESTINATION_TOGETHER)),
                values.getString("version_name", ""), values.getInt("version_code", 0),
                values.getInt("protocol_version", 0), values.getInt("queued_actions", 0),
                values.getLong("last_seen_at", 0));
    }

    /** Returns true only for the current selected node. */
    public synchronized boolean authorizes(String nodeId) {
        Snapshot current = read();
        return current.enabled() && current.nodeId().equals(nodeId);
    }

    private void persist(Snapshot state) {
        boolean stored = values.edit()
                .putString("node_id", state.nodeId()).putString("display_name", state.displayName())
                .putLong("generation", state.generation()).putBoolean("enabled", state.enabled())
                .putBoolean("show_photos", state.showPhotos())
                .putBoolean("show_countdown_titles", state.showCountdownTitles())
                .putBoolean("smooch_enabled", state.smoochEnabled())
                .putBoolean("update_alerts", state.updateAlerts())
                .putString("default_destination", state.defaultDestination())
                .putString("version_name", state.versionName())
                .putInt("version_code", state.versionCode())
                .putInt("protocol_version", state.protocolVersion())
                .putInt("queued_actions", state.queuedActions())
                .putLong("last_seen_at", state.lastSeenAt()).commit();
        if (!stored) throw new IllegalStateException("Could not persist managed watch state");
    }

    private static long nextGeneration(long current) {
        if (current == Long.MAX_VALUE) return Long.MAX_VALUE;
        return Math.max(current + 1, Math.max(1, System.currentTimeMillis()));
    }

    private static String safeName(String value) {
        return value == null ? "" : value.trim();
    }

    static String resolveDestination(String value, boolean smooches) {
        String resolved = validDestination(value);
        return !smooches && DESTINATION_SMOOCH.equals(resolved)
                ? DESTINATION_TOGETHER : resolved;
    }

    private static String validDestination(String value) {
        if (DESTINATION_COUNTDOWN.equals(value) || DESTINATION_SMOOCH.equals(value)) return value;
        return DESTINATION_TOGETHER;
    }

    /** Content-free managed-watch state. Node identifiers never leave app-private storage. */
    public record Snapshot(
            String nodeId,
            String displayName,
            long generation,
            boolean enabled,
            boolean showPhotos,
            boolean showCountdownTitles,
            boolean smoochEnabled,
            boolean updateAlerts,
            String defaultDestination,
            String versionName,
            int versionCode,
            int protocolVersion,
            int queuedActions,
            long lastSeenAt) {}
}
