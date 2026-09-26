package com.littleorbit.mobile;

import android.net.Uri;
import androidx.activity.result.ActivityResultLauncher;
import com.littleorbit.data.remote.NoteApiModels;
import com.littleorbit.data.repository.OrbitRepository;
import com.littleorbit.mobile.databinding.ActivityNotesBinding;
import java.util.Collection;
import java.util.List;
import java.util.function.BooleanSupplier;
import java.util.function.Supplier;

/** Owns private attachment loading, insertion, preview, and scan polling. */
final class NoteAttachmentController {
    private final NotesActivity activity;
    private final OrbitRepository orbit;
    private final ActivityNotesBinding binding;
    private final ActivityResultLauncher<String[]> picker;
    private final Supplier<NoteApiModels.Note> current;
    private final BooleanSupplier previewMode;
    private final Runnable renderPreview;
    private final MarkdownRenderer markdown;
    private final MarkdownEditorTools editor;
    private final NoteAttachmentViews views;
    private final NoteAttachmentUploadCoordinator uploads;
    private List<NoteApiModels.Attachment> attachments = List.of();
    private int polls;

    NoteAttachmentController(
            NotesActivity activity, OrbitRepository orbit, ActivityNotesBinding binding,
            ActivityResultLauncher<String[]> picker, Supplier<NoteApiModels.Note> current,
            BooleanSupplier previewMode, Runnable renderPreview, MarkdownRenderer markdown,
            MarkdownEditorTools editor) {
        this.activity = activity;
        this.orbit = orbit;
        this.binding = binding;
        this.picker = picker;
        this.current = current;
        this.previewMode = previewMode;
        this.renderPreview = renderPreview;
        this.markdown = markdown;
        this.editor = editor;
        this.views = new NoteAttachmentViews(
                activity, orbit, binding.attachmentContainer, binding.statusText,
                this::reload, this::insertLink, ignored -> choose());
        this.uploads = new NoteAttachmentUploadCoordinator(activity, orbit, binding.statusText);
    }

    void reset(NoteApiModels.Note note) {
        attachments = List.of();
        polls = 0;
        binding.attachmentRecoveryCard.setVisibility(android.view.View.GONE);
        markdown.setAttachments(note.id, attachments);
        load(note.id);
    }

    void clear() {
        attachments = List.of();
        polls = 0;
        markdown.clearAttachments();
        binding.attachmentRecoveryCard.setVisibility(android.view.View.GONE);
        binding.attachmentContainer.removeAllViews();
    }

    void retainOfflineNotes(Collection<String> authorizedNoteIds) {
        views.retainOfflineNotes(authorizedNoteIds);
    }

    void choose() {
        if (current.get() == null) {
            binding.statusText.setText(R.string.save_before_attaching);
            return;
        }
        picker.launch(NoteAttachmentUploadCoordinator.TYPES);
    }

    void chosen(Uri uri) {
        NoteApiModels.Note note = current.get();
        if (uri == null || note == null) return;
        uploads.upload(uri, note, this::uploaded);
    }

    void openPreview(NoteApiModels.Attachment attachment) {
        NoteApiModels.Note note = current.get();
        if (note == null || !attachments.contains(attachment)) return;
        views.previewFull(note.id, attachment);
    }

    private void uploaded(String noteId, NoteApiModels.Attachment attachment) {
        NoteApiModels.Note note = current.get();
        if (note == null || !noteId.equals(note.id)) return;
        binding.statusText.setText(R.string.attachment_scanning_status);
        polls = 0;
        load(noteId);
    }

    private void insertLink(NoteApiModels.Attachment attachment) {
        String safeName = attachment.fileName
                .replace("\\", "")
                .replace("]", "")
                .replace("\n", " ")
                .replace("\r", " ");
        String link = attachment.mediaType.startsWith("image/")
                ? "![" + safeName + "](attachment://" + attachment.id + ")"
                : "[" + safeName + "](attachment://" + attachment.id + ")";
        editor.insert((binding.bodyInput.length() == 0 ? "" : "\n") + link + "\n");
    }

    private void load(String noteId) {
        orbit.noteAttachments(noteId).thenAccept(items -> activity.runOnUiThread(() -> {
            NoteApiModels.Note note = current.get();
            if (note == null || !noteId.equals(note.id)) return;
            attachments = List.copyOf(items);
            binding.attachmentRecoveryCard.setVisibility(android.view.View.GONE);
            markdown.setAttachments(noteId, attachments);
            views.show(noteId, items);
            if (previewMode.getAsBoolean()) renderPreview.run();
            if (isProcessing(items) && polls++ < 20) {
                binding.getRoot().postDelayed(() -> load(noteId), 3000);
            }
        })).exceptionally(failure -> {
            activity.runOnUiThread(() -> showLoadFailure(noteId));
            return null;
        });
    }

    private static boolean isProcessing(List<NoteApiModels.Attachment> items) {
        return items.stream().anyMatch(item ->
                "uploading".equals(item.status)
                        || "pending_scan".equals(item.status)
                        || "scanning".equals(item.status));
    }

    private void reload(String noteId) {
        NoteApiModels.Note note = current.get();
        if (note == null || !noteId.equals(note.id)) return;
        polls = 0;
        load(noteId);
    }

    private void showLoadFailure(String noteId) {
        NoteApiModels.Note note = current.get();
        if (note == null || !noteId.equals(note.id)) return;
        binding.attachmentRetryButton.setOnClickListener(ignored -> reload(noteId));
        binding.attachmentRecoveryCard.setVisibility(android.view.View.VISIBLE);
    }
}
