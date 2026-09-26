package com.littleorbit.mobile;

import android.content.Context;
import android.content.SharedPreferences;
import android.util.AtomicFile;
import com.littleorbit.data.remote.DiagnosticApiModels;
import dagger.hilt.android.qualifiers.ApplicationContext;
import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import javax.inject.Inject;
import javax.inject.Singleton;

/** Stores at most one explicitly enabled, content-free crash report in app-private storage. */
@Singleton
public final class CrashDiagnosticStore {
    private static final int FORMAT = 1;
    private static final String ENABLED = "enabled";
    private final SharedPreferences preferences;
    private final AtomicFile pending;

    /** Creates the installation-local opt-in and pending-report store. */
    @Inject
    public CrashDiagnosticStore(@ApplicationContext Context context) {
        preferences = context.getSharedPreferences("crash-diagnostics", Context.MODE_PRIVATE);
        pending = new AtomicFile(new File(context.getFilesDir(), "content-free-crash.bin"));
    }

    /** Returns true only after a person explicitly enabled diagnostics. */
    public boolean enabled() {
        return preferences.getBoolean(ENABLED, false);
    }

    /** Changes future collection and erases a pending report when disabled. */
    public synchronized void setEnabled(boolean enabled) {
        preferences.edit().putBoolean(ENABLED, enabled).commit();
        if (!enabled) pending.delete();
    }

    /** Captures only allowlisted code identifiers before delegating to Android's crash handler. */
    public synchronized void capture(Throwable failure, int versionCode, String versionName) {
        if (!enabled()) return;
        CrashDiagnosticPolicy.Snapshot value = CrashDiagnosticPolicy.capture(
                failure, versionCode, versionName, Instant.now());
        if (!CrashDiagnosticPolicy.valid(value)) return;
        write(value);
    }

    /** Loads a report ready for authenticated delivery, or null after corruption. */
    public synchronized DiagnosticApiModels.Report load(String installationId) {
        CrashDiagnosticPolicy.Snapshot value = read();
        if (value == null || !CrashDiagnosticPolicy.valid(value)) {
            pending.delete();
            return null;
        }
        return new DiagnosticApiModels.Report(
                installationId,
                value.versionCode(),
                value.versionName(),
                value.exceptionChain(),
                value.frames(),
                value.occurredAt());
    }

    /** Deletes exactly the delivered report while preserving a newer crash. */
    public synchronized void clearIfCurrent(String occurredAt) {
        CrashDiagnosticPolicy.Snapshot value = read();
        if (value != null && value.occurredAt().equals(occurredAt)) pending.delete();
    }

    /** Clears consent and pending identifiers when an account or relationship is invalidated. */
    public synchronized void clearForAccountChange() {
        preferences.edit().clear().commit();
        pending.delete();
    }

    private void write(CrashDiagnosticPolicy.Snapshot value) {
        FileOutputStream stream = null;
        try {
            stream = pending.startWrite();
            DataOutputStream output = new DataOutputStream(stream);
            output.writeInt(FORMAT);
            output.writeInt(value.versionCode());
            output.writeUTF(value.versionName());
            output.writeUTF(value.occurredAt());
            writeStrings(output, value.exceptionChain());
            output.writeInt(value.frames().size());
            for (DiagnosticApiModels.Frame frame : value.frames()) {
                output.writeUTF(frame.className);
                output.writeUTF(frame.methodName);
                output.writeInt(frame.lineNumber == null ? 0 : frame.lineNumber);
            }
            output.flush();
            pending.finishWrite(stream);
        } catch (Exception failure) {
            if (stream != null) pending.failWrite(stream);
        }
    }

    private CrashDiagnosticPolicy.Snapshot read() {
        if (!pending.getBaseFile().isFile()) return null;
        try (DataInputStream input = new DataInputStream(new FileInputStream(pending.getBaseFile()))) {
            if (input.readInt() != FORMAT) return null;
            int versionCode = input.readInt();
            String versionName = input.readUTF();
            String occurredAt = input.readUTF();
            List<String> causes = readStrings(input, 8);
            int frameCount = boundedCount(input.readInt(), 64);
            List<DiagnosticApiModels.Frame> frames = new ArrayList<>(frameCount);
            for (int index = 0; index < frameCount; index++) {
                String className = input.readUTF();
                String methodName = input.readUTF();
                int line = input.readInt();
                frames.add(new DiagnosticApiModels.Frame(
                        className, methodName, line == 0 ? null : line));
            }
            if (input.read() != -1) return null;
            return new CrashDiagnosticPolicy.Snapshot(
                    versionCode, versionName, causes, List.copyOf(frames), occurredAt);
        } catch (Exception invalid) {
            return null;
        }
    }

    private static void writeStrings(DataOutputStream output, List<String> values)
            throws java.io.IOException {
        output.writeInt(values.size());
        for (String value : values) output.writeUTF(value);
    }

    private static List<String> readStrings(DataInputStream input, int maximum)
            throws java.io.IOException {
        int count = boundedCount(input.readInt(), maximum);
        List<String> values = new ArrayList<>(count);
        for (int index = 0; index < count; index++) values.add(input.readUTF());
        return List.copyOf(values);
    }

    private static int boundedCount(int count, int maximum) throws java.io.IOException {
        if (count < 1 || count > maximum) throw new java.io.IOException("Invalid diagnostic count");
        return count;
    }
}
