package com.littleorbit.mobile;

import android.text.format.Formatter;
import android.view.View;
import android.widget.LinearLayout;
import android.widget.TextView;
import androidx.core.view.ViewCompat;
import com.google.android.material.button.MaterialButton;
import com.google.android.material.card.MaterialCardView;
import com.littleorbit.data.remote.ApiModels;
import com.littleorbit.data.remote.NoteApiModels;
import com.littleorbit.data.repository.OrbitRepository;

/** Renders a former pairing as readable, immutable cards with private file previews. */
final class ArchiveContentView {
    private final ArchivesActivity activity;
    private final OrbitRepository orbit;
    private final LinearLayout container;
    private final TextView status;
    private final PrivateAttachmentPreview previewer;

    ArchiveContentView(
            ArchivesActivity activity,
            OrbitRepository orbit,
            LinearLayout container,
            TextView status) {
        this.activity = activity;
        this.orbit = orbit;
        this.container = container;
        this.status = status;
        previewer = new PrivateAttachmentPreview(activity);
    }

    void show(ApiModels.ArchiveDetail archive) {
        container.removeAllViews();
        if (archive.notes.isEmpty()) {
            container.addView(body(activity.getString(R.string.archive_no_notes)));
        } else {
            addHeading(R.string.archive_notes_heading);
            for (ApiModels.ArchiveNote note : archive.notes) addNote(archive.archiveId, note);
        }
        addSummary(
                R.plurals.archive_countdowns_summary,
                archive.countdowns.size(),
                R.color.amber);
        addSummary(
                R.plurals.archive_quiz_summary,
                archive.quizAnswers.size(),
                R.color.lavender);
        addSummary(
                R.plurals.archive_smooch_summary,
                archive.smooches.size(),
                R.color.coral);
        status.setText(R.string.archive_read_only);
    }

    private void addNote(String archiveId, ApiModels.ArchiveNote note) {
        MaterialCardView card = card();
        LinearLayout content = column();
        content.setPadding(dp(20), dp(16), dp(20), dp(16));
        TextView title = heading(note.title);
        content.addView(title);
        TextView markdown = body("");
        markdown.setPadding(0, dp(8), 0, 0);
        content.addView(markdown);
        MarkdownRenderer renderer = new MarkdownRenderer(
                activity,
                orbit,
                attachment -> preview(archiveId, note.id, attachment));
        renderer.setArchiveAttachments(archiveId, note.id, note.attachments);
        renderer.render(markdown, note.body);
        if (!note.attachments.isEmpty()) {
            TextView files = body(activity.getResources().getQuantityString(
                    R.plurals.archive_attachment_count,
                    note.attachments.size(),
                    note.attachments.size()));
            files.setTextColor(activity.getColor(R.color.sky));
            files.setPadding(0, dp(16), 0, dp(4));
            content.addView(files);
            for (NoteApiModels.Attachment attachment : note.attachments) {
                content.addView(attachmentButton(archiveId, note.id, attachment));
            }
        }
        card.addView(content);
        container.addView(card);
    }

    private View attachmentButton(
            String archiveId, String noteId, NoteApiModels.Attachment attachment) {
        MaterialButton button = new MaterialButton(
                activity, null, com.google.android.material.R.attr.materialButtonOutlinedStyle);
        String size = Formatter.formatShortFileSize(activity, attachment.sizeBytes);
        button.setText(activity.getString(
                R.string.archive_attachment_label, attachment.fileName, size));
        button.setContentDescription(activity.getString(
                R.string.archive_attachment_preview_description, attachment.fileName));
        button.setMinHeight(dp(48));
        button.setOnClickListener(ignored -> preview(archiveId, noteId, attachment));
        return button;
    }

    private void preview(
            String archiveId, String noteId, NoteApiModels.Attachment attachment) {
        status.setText(R.string.loading_preview);
        orbit.downloadArchiveAttachment(archiveId, noteId, attachment)
                .whenComplete((file, failure) -> activity.runOnUiThread(() -> {
                    if (activity.isFinishing() || activity.isDestroyed()) return;
                    if (failure != null) {
                        status.setText(R.string.attachment_preview_failed);
                        return;
                    }
                    status.setText(R.string.archive_read_only);
                    previewer.show(file, attachment);
                }));
    }

    private void addHeading(int stringId) {
        TextView heading = heading(activity.getString(stringId));
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT);
        params.topMargin = dp(20);
        params.bottomMargin = dp(8);
        heading.setLayoutParams(params);
        container.addView(heading);
    }

    private void addSummary(int pluralId, int count, int colorId) {
        MaterialCardView card = card();
        TextView text = body(activity.getResources().getQuantityString(
                pluralId, count, count));
        text.setTextColor(activity.getColor(colorId));
        text.setPadding(dp(20), dp(16), dp(20), dp(16));
        card.addView(text);
        container.addView(card);
    }

    private MaterialCardView card() {
        MaterialCardView card = new MaterialCardView(activity);
        card.setCardBackgroundColor(activity.getColor(R.color.navy_surface_muted));
        card.setStrokeColor(activity.getColor(R.color.orbit_border));
        card.setStrokeWidth(dp(1));
        card.setRadius(dp(20));
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT);
        params.bottomMargin = dp(12);
        card.setLayoutParams(params);
        return card;
    }

    private LinearLayout column() {
        LinearLayout layout = new LinearLayout(activity);
        layout.setOrientation(LinearLayout.VERTICAL);
        return layout;
    }

    private TextView heading(String value) {
        TextView text = body(value);
        text.setTextSize(20);
        text.setTextColor(activity.getColor(R.color.cloud));
        text.setTypeface(text.getTypeface(), android.graphics.Typeface.BOLD);
        ViewCompat.setAccessibilityHeading(text, true);
        return text;
    }

    private TextView body(String value) {
        TextView text = new TextView(activity);
        text.setText(value);
        text.setTextColor(activity.getColor(R.color.muted));
        text.setTextSize(16);
        text.setLineSpacing(0, 1.12f);
        return text;
    }

    private int dp(int value) {
        return Math.round(value * activity.getResources().getDisplayMetrics().density);
    }
}
