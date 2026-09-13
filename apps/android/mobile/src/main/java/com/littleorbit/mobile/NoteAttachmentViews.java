package com.littleorbit.mobile;

import android.content.Intent;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.pdf.PdfRenderer;
import android.net.Uri;
import android.os.ParcelFileDescriptor;
import android.view.View;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextView;
import androidx.core.content.FileProvider;
import com.google.android.material.button.MaterialButton;
import com.google.android.material.card.MaterialCardView;
import com.littleorbit.data.remote.NoteApiModels;
import com.littleorbit.data.repository.OrbitRepository;
import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.StandardCopyOption;
import java.util.List;
import java.util.HashSet;
import java.util.Set;

/** Builds private attachment tray cards and bounded on-device previews. */
public final class NoteAttachmentViews {
    private static final int PREVIEW_TEXT_BYTES = 64 * 1024;
    private final NotesActivity activity;
    private final OrbitRepository orbit;
    private final LinearLayout container;
    private final TextView status;
    private final Removed removed;
    private final Inserted inserted;
    private final ChooseAgain chooseAgain;

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
    }

    /** Replaces tray state with authorized server metadata. */
    public void show(String noteId, List<NoteApiModels.Attachment> attachments) {
        removeStaleOfflineCopies(attachments);
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
                    openExternal(file, attachment.mediaType);
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
        preview.setOnClickListener(view -> preview(noteId, attachment, content));
        MaterialButton delete = button(R.string.delete_attachment);
        delete.setOnClickListener(view -> confirmDelete(noteId, attachment));
        actions.addView(insert, weighted());
        actions.addView(preview, weighted());
        actions.addView(delete, weighted());
        content.addView(actions);
        MaterialButton keep = button(
                pinned(attachment) ? R.string.remove_offline : R.string.keep_offline);
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
                    offlineFile(attachment).delete();
                    status.setText(R.string.attachment_deleted);
                    removed.completed(noteId);
                }));
    }

    private void preview(
            String noteId, NoteApiModels.Attachment attachment, LinearLayout content) {
        File offline = offlineFile(attachment);
        if (offline.isFile()) {
            showPreview(content, attachment, offline);
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
                    showPreview(content, attachment, file);
                }));
    }

    private void showPreview(
            LinearLayout content, NoteApiModels.Attachment attachment, File file) {
        View prior = content.findViewWithTag("attachment-preview");
        if (prior != null) content.removeView(prior);
        View preview;
        if (attachment.mediaType.startsWith("image/")) {
            preview = imagePreview(file);
        } else if ("application/pdf".equals(attachment.mediaType)) {
            preview = pdfPreview(file);
        } else if (attachment.mediaType.startsWith("text/")) {
            preview = textPreview(file);
        } else {
            openExternal(file, attachment.mediaType);
            return;
        }
        preview.setTag("attachment-preview");
        content.addView(preview);
    }

    private ImageView imagePreview(File file) {
        Bitmap bitmap = BitmapFactory.decodeFile(file.getAbsolutePath());
        ImageView image = new ImageView(activity);
        image.setAdjustViewBounds(true);
        image.setMaxHeight(dp(320));
        image.setScaleType(ImageView.ScaleType.CENTER_CROP);
        image.setImageBitmap(bitmap);
        return image;
    }

    private View pdfPreview(File file) {
        try (ParcelFileDescriptor descriptor =
                        ParcelFileDescriptor.open(file, ParcelFileDescriptor.MODE_READ_ONLY);
                PdfRenderer renderer = new PdfRenderer(descriptor);
                PdfRenderer.Page page = renderer.openPage(0)) {
            Bitmap bitmap = Bitmap.createBitmap(
                    Math.max(page.getWidth(), 1), Math.max(page.getHeight(), 1),
                    Bitmap.Config.ARGB_8888);
            bitmap.eraseColor(activity.getColor(android.R.color.white));
            page.render(bitmap, null, null, PdfRenderer.Page.RENDER_MODE_FOR_DISPLAY);
            ImageView image = new ImageView(activity);
            image.setAdjustViewBounds(true);
            image.setMaxHeight(dp(360));
            image.setImageBitmap(bitmap);
            return image;
        } catch (IOException | RuntimeException error) {
            return text(activity.getString(R.string.attachment_preview_failed));
        }
    }

    private TextView textPreview(File file) {
        try {
            byte[] bytes = Files.readAllBytes(file.toPath());
            int length = Math.min(bytes.length, PREVIEW_TEXT_BYTES);
            TextView preview = text(new String(bytes, 0, length, StandardCharsets.UTF_8));
            preview.setTextColor(activity.getColor(R.color.cloud));
            preview.setPadding(0, dp(10), 0, 0);
            return preview;
        } catch (IOException error) {
            return text(activity.getString(R.string.attachment_preview_failed));
        }
    }

    private void openExternal(File file, String mediaType) {
        Uri uri = FileProvider.getUriForFile(
                activity, activity.getPackageName() + ".files", file);
        Intent intent = new Intent(Intent.ACTION_VIEW)
                .setDataAndType(uri, mediaType)
                .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
        try {
            activity.startActivity(Intent.createChooser(
                    intent, activity.getString(R.string.preview_attachment)));
        } catch (RuntimeException error) {
            status.setText(R.string.no_preview_app);
        }
    }

    private void togglePin(
            String noteId, NoteApiModels.Attachment attachment, MaterialButton button) {
        if (pinned(attachment)) {
            offlineFile(attachment).delete();
            button.setText(R.string.keep_offline);
            return;
        }
        status.setText(R.string.saving_offline);
        orbit.downloadNoteAttachment(noteId, attachment).whenComplete((file, failure) ->
                activity.runOnUiThread(() -> {
                    if (failure != null || !copyOffline(file, attachment)) {
                        status.setText(R.string.attachment_preview_failed);
                        return;
                    }
                    button.setText(R.string.remove_offline);
                    status.setText(R.string.saved_offline);
                }));
    }

    private boolean copyOffline(File source, NoteApiModels.Attachment attachment) {
        File target = offlineFile(attachment);
        File parent = target.getParentFile();
        try {
            if (parent != null && !parent.isDirectory() && !parent.mkdirs()) return false;
            Files.copy(source.toPath(), target.toPath(), StandardCopyOption.REPLACE_EXISTING);
            return true;
        } catch (IOException error) {
            return false;
        }
    }

    private boolean pinned(NoteApiModels.Attachment attachment) {
        return offlineFile(attachment).isFile();
    }

    private void removeStaleOfflineCopies(List<NoteApiModels.Attachment> attachments) {
        Set<String> currentIds = new HashSet<>();
        for (NoteApiModels.Attachment item : attachments) currentIds.add(item.id);
        File directory = new File(activity.getFilesDir(), "kept-space");
        File[] files = directory.listFiles(File::isFile);
        if (files == null) return;
        for (File file : files) {
            if (!currentIds.contains(file.getName())) file.delete();
        }
    }

    private File offlineFile(NoteApiModels.Attachment attachment) {
        return new File(new File(activity.getFilesDir(), "kept-space"), attachment.id);
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
            case "uploading" -> activity.getString(
                    R.string.attachment_uploading, attachment.uploadedBytes, attachment.sizeBytes);
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
