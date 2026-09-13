package com.littleorbit.mobile;

import android.graphics.Typeface;
import android.text.Editable;
import android.text.TextWatcher;
import android.view.View;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;
import com.google.android.material.card.MaterialCardView;
import com.littleorbit.data.remote.NoteApiModels;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/** Renders and filters the Our Space document library without owning network work. */
public final class SpaceLibraryViews {
    private final NotesActivity activity;
    private final LinearLayout activeContainer;
    private final LinearLayout archiveContainer;
    private final EditText search;
    private final OpenNote openNote;
    private final RestoreNote restoreNote;
    private List<NoteApiModels.Note> notes = List.of();

    /** Creates a library presenter with explicit selection and restore actions. */
    public SpaceLibraryViews(
            NotesActivity activity,
            LinearLayout activeContainer,
            LinearLayout archiveContainer,
            EditText search,
            OpenNote openNote,
            RestoreNote restoreNote) {
        this.activity = activity;
        this.activeContainer = activeContainer;
        this.archiveContainer = archiveContainer;
        this.search = search;
        this.openNote = openNote;
        this.restoreNote = restoreNote;
        search.addTextChangedListener(new TextWatcher() {
            @Override public void beforeTextChanged(
                    CharSequence value, int start, int count, int after) {}
            @Override public void onTextChanged(
                    CharSequence value, int start, int before, int count) {}
            @Override public void afterTextChanged(Editable value) {
                renderActive();
            }
        });
    }

    /** Replaces the current active-note snapshot and reapplies the search. */
    public void setNotes(List<NoteApiModels.Note> value) {
        notes = List.copyOf(value);
        renderActive();
    }

    /** Inserts a new server snapshot or replaces its existing card. */
    public void upsert(NoteApiModels.Note replacement) {
        List<NoteApiModels.Note> updated = new ArrayList<>(notes);
        updated.removeIf(note -> note.id.equals(replacement.id));
        updated.add(0, replacement);
        setNotes(updated);
    }

    /** Removes an archived document from the active library immediately. */
    public void remove(String noteId) {
        List<NoteApiModels.Note> remaining = new ArrayList<>();
        for (NoteApiModels.Note note : notes) {
            if (!note.id.equals(noteId)) remaining.add(note);
        }
        setNotes(remaining);
    }

    /** Renders notes still inside their seven-day restore window. */
    public void showArchived(List<NoteApiModels.Note> archived) {
        archiveContainer.removeAllViews();
        for (NoteApiModels.Note note : archived) {
            TextView restore = text(
                    activity.getString(R.string.restore_note_named, note.title),
                    15, R.color.lavender_soft);
            restore.setPadding(dp(12), dp(12), dp(12), dp(12));
            restore.setOnClickListener(view -> restoreNote.restore(note));
            archiveContainer.addView(restore);
        }
    }

    private void renderActive() {
        activeContainer.removeAllViews();
        String query = search.getText().toString().trim().toLowerCase(Locale.ROOT);
        List<NoteApiModels.Note> visible = new ArrayList<>();
        for (NoteApiModels.Note note : notes) {
            if (matches(note, query)) visible.add(note);
        }
        if (visible.isEmpty()) {
            TextView empty = text(
                    activity.getString(notes.isEmpty()
                            ? R.string.no_notes : R.string.no_search_results),
                    14, R.color.muted);
            empty.setPadding(0, dp(16), 0, dp(8));
            activeContainer.addView(empty);
            return;
        }
        for (NoteApiModels.Note note : visible) activeContainer.addView(card(note));
    }

    private static boolean matches(NoteApiModels.Note note, String query) {
        return query.isEmpty()
                || note.title.toLowerCase(Locale.ROOT).contains(query)
                || note.body.toLowerCase(Locale.ROOT).contains(query);
    }

    private View card(NoteApiModels.Note note) {
        MaterialCardView card = new MaterialCardView(activity);
        card.setCardBackgroundColor(activity.getColor(R.color.navy_surface));
        card.setStrokeColor(activity.getColor(R.color.orbit_border));
        card.setStrokeWidth(1);
        card.setRadius(dp(22));
        LinearLayout content = new LinearLayout(activity);
        content.setOrientation(LinearLayout.VERTICAL);
        content.setPadding(dp(18), dp(16), dp(18), dp(16));
        content.addView(text(note.title, 19, R.color.cloud));
        TextView preview = text(preview(note.body), 14, R.color.muted);
        preview.setPadding(0, dp(7), 0, 0);
        content.addView(preview);
        card.addView(content);
        card.setOnClickListener(view -> openNote.open(note));
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        params.bottomMargin = dp(10);
        card.setLayoutParams(params);
        return card;
    }

    private String preview(String body) {
        if (body.isBlank()) return activity.getString(R.string.empty_space_document);
        String value = body.replace('\n', ' ').strip();
        return value.length() > 100 ? value.substring(0, 100) + "…" : value;
    }

    private TextView text(String value, int size, int color) {
        TextView text = new TextView(activity);
        text.setText(value);
        text.setTextSize(size);
        text.setTextColor(activity.getColor(color));
        if (size >= 19) text.setTypeface(text.getTypeface(), Typeface.BOLD);
        return text;
    }

    private int dp(int value) {
        return Math.round(value * activity.getResources().getDisplayMetrics().density);
    }

    /** Selection callback owned by NotesActivity. */
    public interface OpenNote {
        /** Opens a focused editor. */
        void open(NoteApiModels.Note note);
    }

    /** Archive recovery callback owned by NotesActivity. */
    public interface RestoreNote {
        /** Restores one current-couple note. */
        void restore(NoteApiModels.Note note);
    }
}
