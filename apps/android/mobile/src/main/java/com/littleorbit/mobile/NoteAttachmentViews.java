package com.littleorbit.mobile;

import android.view.View;
import android.widget.LinearLayout;
import android.widget.TextView;
import com.google.android.material.button.MaterialButton;
import com.google.android.material.card.MaterialCardView;
import com.littleorbit.data.remote.NoteApiModels;
import com.littleorbit.data.repository.OrbitRepository;
import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.StandardCopyOption;
import java.util.Collection;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.UUID;

/** Builds private attachment tray cards and bounded on-device previews. */
public final class NoteAttachmentViews {
    private final NotesActivity activity;
    private final OrbitRepository orbit;
    private final LinearLayout container;
    private final TextView status;
    private final Removed removed;
    private final Inserted inserted;
    private final ChooseAgain chooseAgain;
    private final PrivateAttachmentPreview previewer;

    /** Creates an attachment presenter owned by one Our Space editor. */
    public NoteAttachmentViews(
            NotesActivity activity, OrbitRepository orbit,
            LinearLayout container, TextView status, Removed removed,
            Inserted inserted, ChooseAgain chooseAgain) {
        this.activity = activity;
        this.orbit = orbit;
        this.container = container;
        this.status = status;
        this.removed = removed;
        this.inserted = inserted;
        this.chooseAgain = chooseAgain;
        this.previewer = new PrivateAttachmentPreview(activity);
    }

    /** Replaces tray state with authorized server metadata. */
    public void show(String noteId, List<NoteApiModels.Attachment> attachments) {
        removeStaleOfflineCopies(noteId, attachments);
        container.removeAllViews();
        if (attachments.isEmpty()) {
            TextView empty = text(activity.getString(R.string.no_attachments));
            empty.setTextColor(activity.getColor(R.color.muted));
            container.addView(empty);
            return;
        }
        for (NoteApiModels.Attachment attachment : attachments) {
            container.addView(card(noteId, attachment));
        }
    }

    /** Removes app-private copies whose note has left both active and recoverable lists. */
    public void retainOfflineNotes(Collection<String> authorizedNoteIds) {
        Set<String> retained = new HashSet<>();
        for (String noteId : authorizedNoteIds) retained.add(safeUuid(noteId));
        removeUnknownNoteDirectories(
                new File(activity.getFilesDir(), "kept-space"), retained);
    }

    /** Opens a verified attachment from an inline Markdown image link. */
    public void previewFull(String noteId, NoteApiModels.Attachment attachment) {
        status.setText(R.string.loading_preview);
        orbit.downloadNoteAttachment(noteId, attachment).whenComplete((file, failure) ->
                activity.runOnUiThread(() -> {
                    if (failure != null) {
                        status.setText(R.string.attachment_preview_failed);
                        return;
                    }
                    status.setText(R.string.note_ready);
                    previewer.show(file, attachment);
                }));
    }

    private View card(String noteId, NoteApiModels.Attachment attachment) {
        MaterialCardView card = new MaterialCardView(activity);
        card.setCardBackgroundColor(activity.getColor(R.color.navy_surface_muted));
        card.setStrokeColor(activity.getColor(R.color.orbit_border));
        card.setStrokeWidth(1);
        card.setRadius(dp(18));
        LinearLayout content = new LinearLayout(activity);
        content.setOrientation(LinearLayout.VERTICAL);
        content.setPadding(dp(14), dp(12), dp(14), dp(12));
        TextView title = text(attachment.fileName);
        title.setTextColor(activity.getColor(R.color.cloud));
        title.setTextSize(16);
        content.addView(title);
        TextView detail = text(detail(attachment));
        detail.setTextColor(activity.getColor(R.color.muted));
        content.addView(detail);
        if ("available".equals(attachment.status)) {
            addAvailableActions(content, noteId, attachment);
        } else if ("rejected".equals(attachment.status)) {
            addRejectedActions(content, noteId, attachment);
        }
        card.addView(content);
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        params.bottomMargin = dp(8);
        card.setLayoutParams(params);
        return card;
    }

    private void addAvailableActions(
            LinearLayout content, String noteId, NoteApiModels.Attachment attachment) {
        LinearLayout actions = new LinearLayout(activity);
        actions.setOrientation(LinearLayout.HORIZONTAL);
        MaterialButton insert = button(R.string.insert_attachment);
        insert.setOnClickListener(view -> inserted.completed(attachment));
        MaterialButton preview = button(R.string.preview_attachment);
        preview.setOnClickListener(view -> preview(noteId, attachment));
        MaterialButton delete = button(R.string.delete_attachment);
        delete.setOnClickListener(view -> confirmDelete(noteId, attachment));
        actions.addView(insert, weighted());
        actions.addView(preview, weighted());
        actions.addView(delete, weighted());
        content.addView(actions);
        MaterialButton keep = button(
                pinned(noteId, attachment) ? R.string.remove_offline : R.string.keep_offline);
        keep.setOnClickListener(view -> togglePin(noteId, attachment, keep));
        content.addView(keep, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, dp(44)));
    }

    private void addRejectedActions(
            LinearLayout content, String noteId, NoteApiModels.Attachment attachment) {
        LinearLayout actions = new LinearLayout(activity);
        actions.setOrientation(LinearLayout.HORIZONTAL);
        MaterialButton retry = button(R.string.choose_again);
        retry.setOnClickListener(view -> chooseAgain.completed(attachment));
        MaterialButton remove = button(R.string.remove_attachment_card);
        remove.setOnClickListener(view -> delete(noteId, attachment));
        actions.addView(retry, weighted());
        actions.addView(remove, weighted());
        content.addView(actions);
    }

    private void confirmDelete(String noteId, NoteApiModels.Attachment attachment) {
        new com.google.android.material.dialog.MaterialAlertDialogBuilder(activity)
                .setTitle(R.string.delete_attachment)
                .setMessage(activity.getString(
                        R.string.delete_attachment_explanation, attachment.fileName))
                .setNegativeButton(android.R.string.cancel, null)
                .setPositiveButton(R.string.delete_action,
                        (dialog, which) -> delete(noteId, attachment))
                .show();
    }

    private void delete(String noteId, NoteApiModels.Attachment attachment) {
        status.setText(R.string.deleting_attachment);
        orbit.deleteNoteAttachment(noteId, attachment.id).whenComplete((unused, failure) ->
                activity.runOnUiThread(() -> {
                    if (failure != null) {
                        status.setText(R.string.attachment_delete_failed);
                        return;
                    }
                    offlineFile(noteId, attachment).delete();
                    status.setText(R.string.attachment_deleted);
                    removed.completed(noteId);
                }));
    }

    private void preview(String noteId, NoteApiModels.Attachment attachment) {
        File offline = verifiedOfflineFile(noteId, attachment);
        if (offline != null) {
            showPreview(attachment, offline);
            status.setText(R.string.note_ready);
            return;
        }
        status.setText(R.string.loading_preview);
        orbit.downloadNoteAttachment(noteId, attachment).whenComplete((file, failure) ->
                activity.runOnUiThread(() -> {
                    if (failure != null) {
                        status.setText(R.string.attachment_preview_failed);
                        return;
                    }
                    status.setText(R.string.note_ready);
                    showPreview(attachment, file);
                }));
    }

    private void showPreview(NoteApiModels.Attachment attachment, File file) {
        previewer.show(file, attachment);
    }

    private void togglePin(
            String noteId, NoteApiModels.Attachment attachment, MaterialButton button) {
        if (pinned(noteId, attachment)) {
            offlineFile(noteId, attachment).delete();
            button.setText(R.string.keep_offline);
            return;
        }
        status.setText(R.string.saving_offline);
        orbit.downloadNoteAttachment(noteId, attachment).whenComplete((file, failure) ->
                activity.runOnUiThread(() -> {
                    if (failure != null || !copyOffline(noteId, file, attachment)) {
                        status.setText(R.string.attachment_preview_failed);
                        return;
                    }
                    button.setText(R.string.remove_offline);
                    status.setText(R.string.saved_offline);
                }));
    }

    private boolean copyOffline(
            String noteId, File source, NoteApiModels.Attachment attachment) {
        File target = offlineFile(noteId, attachment);
        File parent = target.getParentFile();
        try {
            if (parent != null && !parent.isDirectory() && !parent.mkdirs()) return false;
            Files.copy(source.toPath(), target.toPath(), StandardCopyOption.REPLACE_EXISTING);
            if (AttachmentFileIntegrity.matches(target, attachment.sha256)) return true;
            target.delete();
            return false;
        } catch (IOException error) {
            return false;
        }
    }

    private boolean pinned(String noteId, NoteApiModels.Attachment attachment) {
        return verifiedOfflineFile(noteId, attachment) != null;
    }

    private File verifiedOfflineFile(
            String noteId, NoteApiModels.Attachment attachment) {
        File file = offlineFile(noteId, attachment);
        if (AttachmentFileIntegrity.matches(file, attachment.sha256)) return file;
        if (file.isFile()) file.delete();
        return null;
    }

    private void removeStaleOfflineCopies(
            String noteId, List<NoteApiModels.Attachment> attachments) {
        Set<String> currentIds = new HashSet<>();
        for (NoteApiModels.Attachment item : attachments) {
            currentIds.add(safeUuid(item.id));
        }
        File root = new File(activity.getFilesDir(), "kept-space");
        removeLegacyUnscopedFiles(root);
        File directory = new File(root, safeUuid(noteId));
        File[] files = directory.listFiles(File::isFile);
        if (files == null) return;
        for (File file : files) {
            if (!currentIds.contains(file.getName())) file.delete();
        }
    }

    private void removeLegacyUnscopedFiles(File root) {
        File[] legacy = root.listFiles(File::isFile);
        if (legacy == null) return;
        for (File file : legacy) file.delete();
    }

    static void removeUnknownNoteDirectories(File root, Set<String> retained) {
        File[] entries = root.listFiles();
        if (entries == null) return;
        for (File entry : entries) {
            if (entry.isFile()) {
                entry.delete();
            } else if (entry.isDirectory() && !retained.contains(entry.getName())) {
                deleteTree(entry);
            }
        }
    }

    private static void deleteTree(File target) {
        File[] children = target.listFiles();
        if (children != null) {
            for (File child : children) deleteTree(child);
        }
        target.delete();
    }

    private File offlineFile(String noteId, NoteApiModels.Attachment attachment) {
        File root = new File(activity.getFilesDir(), "kept-space");
        return new File(new File(root, safeUuid(noteId)), safeUuid(attachment.id));
    }

    private static String safeUuid(String value) {
        try {
            return UUID.fromString(value).toString();
        } catch (IllegalArgumentException | NullPointerException failure) {
            return "invalid";
        }
    }

    private MaterialButton button(int label) {
        MaterialButton button = new MaterialButton(
                activity, null, com.google.android.material.R.attr.materialButtonOutlinedStyle);
        button.setText(label);
        button.setTextColor(activity.getColor(R.color.lavender_soft));
        return button;
    }

    private TextView text(String value) {
        TextView text = new TextView(activity);
        text.setText(value);
        return text;
    }

    private LinearLayout.LayoutParams weighted() {
        return new LinearLayout.LayoutParams(0, dp(48), 1);
    }

    private String detail(NoteApiModels.Attachment attachment) {
        String size = android.text.format.Formatter.formatShortFileSize(
                activity, attachment.sizeBytes);
        return switch (attachment.status) {
            case "uploading" -> activity.getString(R.string.attachment_uploading,
                    android.text.format.Formatter.formatShortFileSize(
                            activity, attachment.uploadedBytes), size);
            case "pending_scan", "scanning" ->
                    activity.getString(R.string.attachment_scanning, size);
            case "rejected" -> rejectionDetail(attachment.rejectionReason);
            default -> attachment.mediaType + " · " + size;
        };
    }

    private String rejectionDetail(String reason) {
        if ("malware_detected".equals(reason)) {
            return activity.getString(R.string.attachment_rejected_malware);
        }
        if ("couple_quota_exceeded_after_sanitization".equals(reason)) {
            return activity.getString(R.string.attachment_rejected_quota);
        }
        if ("sanitized_file_too_large".equals(reason)) {
            return activity.getString(R.string.attachment_too_large);
        }
        return activity.getString(R.string.attachment_rejected);
    }

    private int dp(int value) {
        return Math.round(value * activity.getResources().getDisplayMetrics().density);
    }

    /** Callback used to refresh the current attachment tray after deletion. */
    public interface Removed {
        /** Reports the note whose authorized attachment list changed. */
        void completed(String noteId);
    }

    /** Callback that inserts an available attachment at the live editor cursor. */
    public interface Inserted {
        /** Inserts a reference only after the private scan completed. */
        void completed(NoteApiModels.Attachment attachment);
    }

    /** Callback that opens the system picker after a terminal rejection. */
    public interface ChooseAgain {
        /** Starts a new, independently scanned selection. */
        void completed(NoteApiModels.Attachment attachment);
    }
}
