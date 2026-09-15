package com.littleorbit.mobile;

import android.text.Editable;
import android.text.Selection;
import android.view.View;
import com.littleorbit.domain.MarkdownPrivacy;
import com.littleorbit.domain.TextPatch;
import com.littleorbit.mobile.databinding.ActivityNotesBinding;

/** Renders one Our Space document without owning network or persistence behavior. */
final class NoteEditorView {
    private final ActivityNotesBinding binding;
    private final MarkdownRenderer markdown;
    private boolean previewing;
    private boolean editorVisible;
    private boolean rendering;

    NoteEditorView(ActivityNotesBinding binding, MarkdownRenderer markdown) {
        this.binding = binding;
        this.markdown = markdown;
        binding.modeButton.setOnClickListener(ignored -> toggleMode());
    }

    boolean isRendering() {
        return rendering;
    }

    boolean isPreviewing() {
        return previewing;
    }

    boolean isEditorVisible() {
        return editorVisible;
    }

    void renderInitial(String title, String body, int selectionStart, int selectionEnd) {
        rendering = true;
        binding.titleInput.setText(title);
        binding.bodyInput.setText(body);
        int start = clamp(selectionStart, body.length());
        int end = Math.max(start, clamp(selectionEnd, body.length()));
        Selection.setSelection(binding.bodyInput.getText(), start, end);
        rendering = false;
    }

    void patchBody(String body) {
        Editable editable = binding.bodyInput.getText();
        TextPatch patch = TextPatch.between(editable.toString(), body);
        if (patch.isEmpty()) return;
        int start = Math.max(binding.bodyInput.getSelectionStart(), 0);
        int end = Math.max(binding.bodyInput.getSelectionEnd(), start);
        rendering = true;
        editable.replace(patch.start(), patch.end(), patch.replacement());
        Selection.setSelection(editable, patch.mapOffset(start), patch.mapOffset(end));
        rendering = false;
        if (previewing) renderPreview();
    }

    void setTitle(String title) {
        rendering = true;
        binding.titleInput.setText(title);
        binding.previewTitle.setText(title);
        rendering = false;
    }

    void showDocument(boolean preview) {
        editorVisible = true;
        binding.libraryScroll.setVisibility(View.GONE);
        binding.editorScroll.setVisibility(View.VISIBLE);
        if (preview) showPreview();
        else showEdit();
    }

    void showLibrary() {
        editorVisible = false;
        binding.editorScroll.setVisibility(View.GONE);
        binding.formattingScroll.setVisibility(View.GONE);
        binding.libraryScroll.setVisibility(View.VISIBLE);
    }

    void renderPreview() {
        String body = binding.bodyInput.getText().toString();
        binding.previewTitle.setText(binding.titleInput.getText().toString());
        markdown.render(binding.previewText, body);
        binding.remoteImageNotice.setVisibility(hasRemoteImage(body) ? View.VISIBLE : View.GONE);
        binding.rawHtmlNotice.setVisibility(
                MarkdownPrivacy.containsRawHtml(body) ? View.VISIBLE : View.GONE);
    }

    void showConflict(String serverVersion) {
        boolean visible = serverVersion != null;
        binding.conflictCard.setVisibility(visible ? View.VISIBLE : View.GONE);
        if (visible) binding.serverVersionText.setText(serverVersion);
    }

    void showLibraryFailure() {
        binding.libraryRecoveryText.setText(R.string.space_library_unavailable);
        binding.libraryRetryButton.setText(R.string.retry);
        binding.libraryRecoveryCard.setVisibility(View.VISIBLE);
    }

    void showLibraryRecovery(int message, int action, Runnable next) {
        binding.libraryRecoveryText.setText(message);
        binding.libraryRetryButton.setText(action);
        binding.libraryRetryButton.setOnClickListener(ignored -> next.run());
        binding.libraryRecoveryCard.setVisibility(View.VISIBLE);
    }

    void showLoadFailure(boolean restoring, Runnable retry) {
        if (restoring && editorVisible) {
            showRecovery(R.string.note_draft_preserved, R.string.space_retry_document, retry);
            binding.statusText.setText(R.string.note_draft_preserved);
            return;
        }
        showLibraryFailure();
        binding.libraryPresenceText.setText(R.string.request_failed);
    }

    void showRenameFailure(Runnable retry) {
        binding.statusText.setText(R.string.remote_change_conflict);
        showRecovery(R.string.remote_change_conflict, R.string.space_retry_document, retry);
    }

    void showInactiveRelationship(Runnable pair) {
        renderInitial("", "", 0, 0);
        showConflict(null);
        clearPreview();
        hideRecovery();
        showLibrary();
        binding.libraryPresenceText.setText(R.string.space_relationship_inactive);
        showLibraryRecovery(
                R.string.space_relationship_inactive, R.string.pair_with_your_partner, pair);
    }

    void hideLibraryFailure() {
        binding.libraryRecoveryCard.setVisibility(View.GONE);
    }

    void showRecovery(int message, int action, Runnable retry) {
        binding.editorRecoveryText.setText(message);
        binding.editorRetryButton.setText(action);
        binding.editorRetryButton.setOnClickListener(ignored -> retry.run());
        binding.editorRecoveryCard.setVisibility(View.VISIBLE);
    }

    void hideRecovery() {
        binding.editorRecoveryCard.setVisibility(View.GONE);
    }

    void clearPreview() {
        markdown.clear(binding.previewText);
    }

    private void toggleMode() {
        if (previewing) showEdit();
        else showPreview();
    }

    private void showEdit() {
        previewing = false;
        clearPreview();
        binding.previewTitle.setVisibility(View.GONE);
        binding.titleInput.setVisibility(View.VISIBLE);
        binding.bodyInput.setVisibility(View.VISIBLE);
        binding.formattingScroll.setVisibility(View.VISIBLE);
        binding.previewText.setVisibility(View.GONE);
        binding.remoteImageNotice.setVisibility(View.GONE);
        binding.rawHtmlNotice.setVisibility(View.GONE);
        binding.syncButton.setVisibility(View.VISIBLE);
        binding.modeButton.setText(R.string.space_preview);
        binding.modeButton.setContentDescription(
                binding.getRoot().getContext().getString(R.string.space_preview));
        OrbitMotion.reveal(binding.bodyInput);
    }

    private void showPreview() {
        previewing = true;
        renderPreview();
        binding.titleInput.setVisibility(View.GONE);
        binding.previewTitle.setVisibility(View.VISIBLE);
        binding.bodyInput.setVisibility(View.GONE);
        binding.formattingScroll.setVisibility(View.GONE);
        binding.previewText.setVisibility(View.VISIBLE);
        binding.syncButton.setVisibility(View.GONE);
        binding.modeButton.setText(R.string.edit_markdown);
        binding.modeButton.setContentDescription(
                binding.getRoot().getContext().getString(R.string.edit_markdown));
        OrbitMotion.reveal(binding.previewText);
    }

    private static boolean hasRemoteImage(String body) {
        return body.matches("(?s).*?!\\[[^]]*]\\(https?://.*");
    }

    private static int clamp(int value, int length) {
        return Math.max(0, Math.min(value, length));
    }
}
