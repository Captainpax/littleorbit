package com.littleorbit.mobile;

import android.app.DownloadManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageInstaller;
import android.os.Build;
import android.os.Environment;
import android.os.Handler;
import android.os.Looper;
import androidx.annotation.Nullable;
import com.littleorbit.data.repository.ReleaseRepository;
import com.littleorbit.domain.ReleaseUpdate;
import com.littleorbit.domain.UpdatePolicy;
import com.littleorbit.domain.UpdaterStateMachine;
import dagger.hilt.android.qualifiers.ApplicationContext;
import java.io.File;
import java.io.FileInputStream;
import java.io.OutputStream;
import java.time.Duration;
import java.time.Instant;
import java.util.Arrays;
import java.util.Optional;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import javax.inject.Inject;
import javax.inject.Singleton;

/** Persistent DownloadManager and PackageInstaller coordinator for verified phone updates. */
@Singleton
public final class AndroidUpdateCoordinator {
    private static final String STORE = "little-orbit-updater-state";
    private static final Duration FOREGROUND_CHECK_INTERVAL = Duration.ofHours(12);
    private static final Duration OPTIONAL_SNOOZE = Duration.ofHours(24);
    private final Context context;
    private final ReleaseRepository releases;
    private final ApkVerifier verifier;
    private final SharedPreferences preferences;
    private final Handler main = new Handler(Looper.getMainLooper());
    private final ExecutorService executor = Executors.newSingleThreadExecutor(runnable -> {
        Thread thread = new Thread(runnable, "little-orbit-apk-update");
        thread.setDaemon(true);
        return thread;
    });
    private @Nullable Listener listener;
    private boolean pollScheduled;

    /** Creates the updater using application-scoped Android services and release discovery. */
    @Inject
    public AndroidUpdateCoordinator(
            @ApplicationContext Context context,
            ReleaseRepository releases,
            ApkVerifier verifier) {
        this.context = context;
        this.releases = releases;
        this.verifier = verifier;
        preferences = context.getSharedPreferences(STORE, Context.MODE_PRIVATE);
    }

    /** Receives lifecycle-safe presentation snapshots on the main thread. */
    public interface Listener {
        /** Renders one sanitized updater snapshot. */
        void onUpdateState(UpdatePresentation presentation);
    }

    /** Checks immediately or uses a recent validated response, then reconciles Android services. */
    public void check(boolean force, Listener observer) {
        listener = observer;
        long age = System.currentTimeMillis() - releases.lastCheckedAtMillis();
        Optional<ReleaseUpdate> cached = releases.cached();
        if (!force && cached.isPresent() && age >= 0
                && age < FOREGROUND_CHECK_INTERVAL.toMillis()) {
            select(cached.get(), false);
            reconcile();
            return;
        }
        if (!machine().hasResumableWork()) persist(machine().checking());
        releases.refresh().whenComplete((release, failure) -> {
            ReleaseUpdate selected = failure == null ? release : releases.cached().orElse(null);
            if (selected == null) {
                persist(machine().failed("release_check_unavailable"));
                dispatch();
                return;
            }
            select(selected, force);
            reconcile();
        });
    }

    /** Stops activity callbacks while leaving Android-owned work and persisted state intact. */
    public void stopObserving(Listener observer) {
        if (listener == observer) listener = null;
        pollScheduled = false;
        main.removeCallbacks(this::reconcile);
    }

    /** Defers only an optional release for one day. */
    public void deferOptional() {
        ReleaseUpdate release = releases.cached().orElse(null);
        if (release == null) return;
        UpdatePolicy.Decision decision = decision(release);
        if (decision == UpdatePolicy.Decision.OPTIONAL) {
            releases.defer(
                    release.releaseId(), System.currentTimeMillis() + OPTIONAL_SNOOZE.toMillis());
            persist(machine().deferred());
            dispatch();
        }
    }

    /** Starts one Android-owned download, or reuses already verified bytes for install retry. */
    public void startUpdate() {
        ReleaseUpdate release = releases.cached().orElse(null);
        if (release == null) return;
        File apk = apkFile(release);
        long generation = nextOperationGeneration();
        if (isVerifiedPhase(machine().snapshot().phase()) && apk.isFile()) {
            requestInstall(release, apk, generation);
            return;
        }
        executor.execute(() -> enqueueDownload(release, apk, generation));
    }

    /** Removes Android-owned download work and its partial bytes. */
    public void cancelDownload() {
        invalidateOperation();
        long id = preferences.getLong("download_id", -1);
        if (id >= 0) downloadManager().remove(id);
        abandonInstallSession();
        ReleaseUpdate release = releases.cached().orElse(null);
        if (release != null) deleteFile(apkFile(release));
        preferences.edit().remove("download_id").remove("session_id").apply();
        if (release != null) persist(machine().available(decision(release) == UpdatePolicy.Decision.REQUIRED));
        dispatch();
    }

    /** Continues after the user returns from Android's unknown-app-source settings. */
    public void resumeInstallAfterPermission() {
        ReleaseUpdate release = releases.cached().orElse(null);
        if (release == null) return;
        File apk = apkFile(release);
        long generation = nextOperationGeneration();
        if (canInstallPackages() && apk.isFile()) requestInstall(release, apk, generation);
        else {
            persist(machine().permissionRequired(apk.isFile() ? apk.length() : 0));
            dispatch();
        }
    }

    /** Reconciles the persisted phase with DownloadManager and installed package state. */
    public void reconcile() {
        ReleaseUpdate release = releases.cached().orElse(null);
        if (release == null) {
            dispatch();
            return;
        }
        if (verifier.installedVersionCode() >= release.versionCode()) {
            persist(machine().installed(release.sizeBytes()));
            dispatch();
            return;
        }
        String phase = machine().snapshot().phase();
        if (UpdaterStateMachine.DOWNLOADING.equals(phase)
                || UpdaterStateMachine.PAUSED.equals(phase)
                || UpdaterStateMachine.VERIFYING.equals(phase)) {
            long generation = preferences.getLong("operation_generation", 0);
            executor.execute(() -> inspectDownload(release, generation));
            return;
        }
        dispatch();
    }

    private void select(ReleaseUpdate release, boolean force) {
        UpdatePolicy.Decision decision = decision(release);
        if (decision == UpdatePolicy.Decision.CURRENT) {
            persist(machine().installed(release.sizeBytes()));
            return;
        }
        if (decision == UpdatePolicy.Decision.DEVICE_INCOMPATIBLE) {
            persist(machine().failed("device_incompatible"));
            return;
        }
        UpdaterStateMachine selected = machine();
        boolean sameRelease = release.releaseId().equals(selected.snapshot().releaseId());
        if (sameRelease && selected.hasResumableWork()) {
            persist(selected.selectPreservingWork(
                    release.releaseId(), decision == UpdatePolicy.Decision.REQUIRED));
            return;
        }
        if (!sameRelease && selected.hasResumableWork()) removeObsoleteWork();
        boolean deferred = !force
                && decision == UpdatePolicy.Decision.OPTIONAL
                && releases.isDeferred(release.releaseId(), System.currentTimeMillis());
        selected.select(release.releaseId(), decision == UpdatePolicy.Decision.REQUIRED);
        persist(deferred ? selected.deferred() : selected.snapshot());
    }

    private void removeObsoleteWork() {
        invalidateOperation();
        long downloadId = preferences.getLong("download_id", -1);
        if (downloadId >= 0) downloadManager().remove(downloadId);
        abandonInstallSession();
        preferences.edit().remove("download_id").remove("session_id").apply();
        deleteUpdateFiles();
    }

    private void deleteUpdateFiles() {
        File directory = updateDirectory();
        File[] files = directory.listFiles();
        if (files == null) return;
        for (File file : files) deleteFile(file);
    }

    private void enqueueDownload(ReleaseUpdate release, File apk, long generation) {
        try {
            if (!ownsOperation(generation)) return;
            deleteFile(apk);
            DownloadManager.Request request = new DownloadManager.Request(
                    android.net.Uri.parse(release.apkUrl()))
                    .setTitle("Little Orbit " + release.version())
                    .setDescription("Downloading signed update")
                    .setMimeType("application/vnd.android.package-archive")
                    .setNotificationVisibility(
                            DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
                    .setDestinationInExternalFilesDir(
                            context,
                            Environment.DIRECTORY_DOWNLOADS,
                            "updates/" + apk.getName());
            long id = downloadManager().enqueue(request);
            if (!ownsOperation(generation)) {
                downloadManager().remove(id);
                return;
            }
            preferences.edit().putLong("download_id", id).apply();
            persist(machine().downloading(0, release.sizeBytes()));
            dispatchAndPoll();
        } catch (RuntimeException failure) {
            if (ownsOperation(generation)) {
                persist(machine().retryDownload("download_start_failed", 0, release.sizeBytes()));
                dispatch();
            }
        }
    }

    private void inspectDownload(ReleaseUpdate release, long generation) {
        if (!ownsOperation(generation)) return;
        long id = preferences.getLong("download_id", -1);
        if (id < 0) {
            persist(machine().retryDownload("download_missing", 0, release.sizeBytes()));
            dispatch();
            return;
        }
        DownloadManager.Query query = new DownloadManager.Query().setFilterById(id);
        try (android.database.Cursor cursor = downloadManager().query(query)) {
            if (cursor == null || !cursor.moveToFirst()) {
                persist(machine().retryDownload("download_missing", 0, release.sizeBytes()));
                dispatch();
                return;
            }
            int status = columnInt(cursor, DownloadManager.COLUMN_STATUS);
            long bytes = Math.max(0, columnLong(
                    cursor, DownloadManager.COLUMN_BYTES_DOWNLOADED_SO_FAR));
            long total = Math.max(release.sizeBytes(), columnLong(
                    cursor, DownloadManager.COLUMN_TOTAL_SIZE_BYTES));
            if (!ownsOperation(generation)) return;
            if (status == DownloadManager.STATUS_SUCCESSFUL) {
                persist(machine().verifying(bytes));
                dispatch();
                verifyAndInstall(release, apkFile(release), generation);
            } else if (status == DownloadManager.STATUS_FAILED) {
                persist(machine().retryDownload(downloadFailure(cursor), bytes, total));
                dispatch();
            } else if (status == DownloadManager.STATUS_PAUSED) {
                persist(machine().paused("download_paused", bytes, total));
                dispatchAndPoll();
            } else {
                persist(machine().downloading(bytes, total));
                dispatchAndPoll();
            }
        } catch (RuntimeException unavailable) {
            if (ownsOperation(generation)) {
                persist(machine().retryDownload(
                        "download_state_unavailable", 0, release.sizeBytes()));
                dispatch();
            }
        }
    }

    private void verifyAndInstall(ReleaseUpdate release, File apk, long generation) {
        String failure = verifier.verify(release, apk);
        if (!ownsOperation(generation)) return;
        if (failure != null) {
            deleteFile(apk);
            persist(machine().retryDownload(failure, 0, release.sizeBytes()));
            dispatch();
            return;
        }
        requestInstall(release, apk, generation);
    }

    private void requestInstall(ReleaseUpdate release, File apk, long generation) {
        if (!ownsOperation(generation)) return;
        if (!canInstallPackages()) {
            persist(machine().permissionRequired(apk.length()));
            dispatch();
            return;
        }
        executor.execute(() -> installVerifiedApk(release, apk, generation));
    }

    private void installVerifiedApk(ReleaseUpdate release, File apk, long generation) {
        if (!ownsOperation(generation)) return;
        PackageInstaller installer = context.getPackageManager().getPackageInstaller();
        int sessionId = -1;
        try {
            persist(machine().installing(apk.length()));
            PackageInstaller.SessionParams params = new PackageInstaller.SessionParams(
                    PackageInstaller.SessionParams.MODE_FULL_INSTALL);
            params.setAppPackageName(release.packageName());
            params.setSize(apk.length());
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                params.setRequireUserAction(PackageInstaller.SessionParams.USER_ACTION_REQUIRED);
            }
            sessionId = installer.createSession(params);
            if (!ownsOperation(generation)) {
                installer.abandonSession(sessionId);
                return;
            }
            preferences.edit().putInt("session_id", sessionId).apply();
            try (PackageInstaller.Session session = installer.openSession(sessionId);
                    FileInputStream input = new FileInputStream(apk);
                    OutputStream output = session.openWrite("little-orbit.apk", 0, apk.length())) {
                copy(input, output);
                session.fsync(output);
                if (!ownsOperation(generation)) {
                    session.abandon();
                    return;
                }
                Intent result = new Intent(context, UpdateInstallReceiver.class)
                        .setAction(UpdateInstallReceiver.ACTION_INSTALL_RESULT);
                PendingIntent callback = PendingIntent.getBroadcast(
                        context,
                        sessionId,
                        result,
                        PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_MUTABLE);
                session.commit(callback.getIntentSender());
            }
            if (ownsOperation(generation)) {
                persist(machine().awaitingConfirmation(apk.length()));
                dispatch();
            }
        } catch (Exception failure) {
            safelyAbandon(installer, sessionId);
            if (ownsOperation(generation)) {
                persist(machine().retryInstall("install_session_failed", apk.length()));
                dispatch();
            }
        }
    }

    private UpdatePolicy.Decision decision(ReleaseUpdate release) {
        return UpdatePolicy.evaluate(
                release, (int) verifier.installedVersionCode(), Build.VERSION.SDK_INT, Instant.now());
    }

    private void dispatchAndPoll() {
        dispatch();
        main.post(() -> {
            if (listener == null || pollScheduled) return;
            pollScheduled = true;
            main.postDelayed(() -> {
                pollScheduled = false;
                reconcile();
            }, 800);
        });
    }

    private void dispatch() {
        ReleaseUpdate release = releases.cached().orElse(null);
        if (release == null) return;
        UpdatePresentation presentation = new UpdatePresentation(
                release, decision(release), machine().snapshot());
        main.post(() -> {
            Listener current = listener;
            if (current != null) current.onUpdateState(presentation);
        });
    }

    private UpdaterStateMachine machine() {
        return new UpdaterStateMachine(new UpdaterStateMachine.Snapshot(
                preferences.getString("phase", UpdaterStateMachine.IDLE),
                preferences.getString("release_id", ""),
                preferences.getString("failure", ""),
                preferences.getLong("bytes", 0),
                preferences.getLong("total", 0),
                preferences.getBoolean("required", false)));
    }

    private void persist(UpdaterStateMachine.Snapshot state) {
        preferences.edit()
                .putString("phase", state.phase())
                .putString("release_id", state.releaseId())
                .putString("failure", state.failureCode())
                .putLong("bytes", state.downloadedBytes())
                .putLong("total", state.totalBytes())
                .putBoolean("required", state.required())
                .apply();
    }

    private synchronized long nextOperationGeneration() {
        long generation = preferences.getLong("operation_generation", 0) + 1;
        preferences.edit().putLong("operation_generation", generation).apply();
        return generation;
    }

    private synchronized void invalidateOperation() {
        nextOperationGeneration();
    }

    private boolean ownsOperation(long generation) {
        return generation > 0
                && preferences.getLong("operation_generation", 0) == generation;
    }

    private void abandonInstallSession() {
        int sessionId = preferences.getInt("session_id", -1);
        safelyAbandon(context.getPackageManager().getPackageInstaller(), sessionId);
    }

    private static void safelyAbandon(PackageInstaller installer, int sessionId) {
        if (sessionId < 0) return;
        try {
            installer.abandonSession(sessionId);
        } catch (RuntimeException ignored) {
            // A committed or completed Android session can no longer be abandoned.
        }
    }

    private boolean canInstallPackages() {
        return context.getPackageManager().canRequestPackageInstalls();
    }

    private DownloadManager downloadManager() {
        DownloadManager manager = context.getSystemService(DownloadManager.class);
        if (manager == null) throw new IllegalStateException("download service unavailable");
        return manager;
    }

    private File apkFile(ReleaseUpdate release) {
        return new File(updateDirectory(), "little-orbit-" + release.versionCode() + ".apk");
    }

    private File updateDirectory() {
        File root = context.getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS);
        if (root == null) root = context.getFilesDir();
        return new File(root, "updates");
    }

    private static void copy(FileInputStream input, OutputStream output) throws Exception {
        byte[] buffer = new byte[64 * 1024];
        int count;
        while ((count = input.read(buffer)) >= 0) output.write(buffer, 0, count);
    }

    private static int columnInt(android.database.Cursor cursor, String name) {
        return cursor.getInt(cursor.getColumnIndexOrThrow(name));
    }

    private static long columnLong(android.database.Cursor cursor, String name) {
        return cursor.getLong(cursor.getColumnIndexOrThrow(name));
    }

    private static String downloadFailure(android.database.Cursor cursor) {
        int reason = columnInt(cursor, DownloadManager.COLUMN_REASON);
        if (reason == DownloadManager.ERROR_INSUFFICIENT_SPACE) return "download_storage";
        if (Arrays.asList(
                DownloadManager.ERROR_HTTP_DATA_ERROR,
                DownloadManager.ERROR_TOO_MANY_REDIRECTS,
                DownloadManager.ERROR_UNHANDLED_HTTP_CODE).contains(reason)) {
            return "download_http";
        }
        return "download_failed";
    }

    private static boolean isVerifiedPhase(String phase) {
        return UpdaterStateMachine.PERMISSION_REQUIRED.equals(phase)
                || UpdaterStateMachine.RETRY_INSTALL.equals(phase)
                || UpdaterStateMachine.AWAITING_CONFIRMATION.equals(phase);
    }

    private static void deleteFile(File file) {
        if (file.exists() && !file.delete()) file.deleteOnExit();
    }
}
