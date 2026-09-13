package com.littleorbit.mobile;

import android.content.Context;
import android.text.Editable;
import android.text.Selection;
import android.view.View;
import android.widget.EditText;
import android.widget.PopupMenu;

/** Applies small, cursor-safe Markdown edits without owning document state. */
final class MarkdownEditorTools {
    private final Context context;
    private final EditText editor;

    MarkdownEditorTools(Context context, EditText editor) {
        this.context = context;
        this.editor = editor;
    }

    void showMore(View anchor) {
        PopupMenu menu = new PopupMenu(context, anchor);
        menu.getMenu().add(0, 1, 0, R.string.format_numbered_list);
        menu.getMenu().add(0, 2, 1, R.string.format_quote);
        menu.getMenu().add(0, 3, 2, R.string.format_code);
        menu.getMenu().add(0, 4, 3, R.string.format_table);
        menu.getMenu().add(0, 5, 4, R.string.format_strikethrough);
        menu.getMenu().add(0, 6, 5, R.string.format_divider);
        menu.setOnMenuItemClickListener(item -> applyExtra(item.getItemId()));
        menu.show();
    }

    private boolean applyExtra(int itemId) {
        switch (itemId) {
            case 1 -> insert("1. ");
            case 2 -> insert("> ");
            case 3 -> wrap("`", "`");
            case 4 -> insert("| Column | Column |\n| --- | --- |\n|  |  |\n");
            case 5 -> wrap("~~", "~~");
            case 6 -> insert("\n---\n");
            default -> { return false; }
        }
        return true;
    }

    void wrap(String before, String after) {
        Editable text = editor.getText();
        int start = Math.max(editor.getSelectionStart(), 0);
        int end = Math.max(editor.getSelectionEnd(), start);
        String selected = text.subSequence(start, end).toString();
        text.replace(start, end, before + selected + after);
        Selection.setSelection(text, start + before.length(),
                start + before.length() + selected.length());
    }

    void insert(String value) {
        Editable text = editor.getText();
        int position = Math.max(editor.getSelectionStart(), 0);
        text.insert(position, value);
        Selection.setSelection(text, position + value.length());
    }
}
