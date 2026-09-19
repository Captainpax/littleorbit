package com.littleorbit.mobile;

import com.google.android.material.dialog.MaterialAlertDialogBuilder;

/** Small themed decisions shared by the note workspace flow. */
final class NoteDialogs {
    private NoteDialogs() {}

    static void showUntitled(NotesActivity activity, Runnable discard) {
        new MaterialAlertDialogBuilder(activity)
                .setTitle(R.string.space_untitled_draft)
                .setMessage(R.string.space_untitled_draft_message)
                .setNegativeButton(R.string.keep_editing, null)
                .setPositiveButton(R.string.discard_draft, (dialog, which) -> discard.run())
                .show();
    }
}
