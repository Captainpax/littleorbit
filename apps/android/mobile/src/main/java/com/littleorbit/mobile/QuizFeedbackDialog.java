package com.littleorbit.mobile;

import android.view.LayoutInflater;
import android.view.View;
import android.widget.RatingBar;
import android.widget.TextView;
import androidx.appcompat.app.AlertDialog;
import androidx.appcompat.app.AppCompatActivity;
import com.google.android.material.chip.Chip;
import com.google.android.material.chip.ChipGroup;
import com.google.android.material.dialog.MaterialAlertDialogBuilder;
import com.google.android.material.textfield.TextInputEditText;
import com.littleorbit.data.remote.QuizApiModels;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Accessible post-reveal rating editor with a strict three-tag boundary. */
public final class QuizFeedbackDialog {
    private static final int MAX_TAGS = 3;
    private final AppCompatActivity activity;

    /** Creates a dialog renderer scoped to one activity. */
    public QuizFeedbackDialog(AppCompatActivity activity) {
        this.activity = activity;
    }

    /** Shows current private feedback without ever exposing the partner's rating. */
    public void show(QuizApiModels.Question question, Listener listener) {
        View content = LayoutInflater.from(activity).inflate(R.layout.dialog_quiz_feedback, null);
        TextView prompt = content.findViewById(R.id.feedbackPrompt);
        RatingBar rating = content.findViewById(R.id.feedbackRating);
        ChipGroup tags = content.findViewById(R.id.feedbackTags);
        TextView tagError = content.findViewById(R.id.feedbackTagError);
        TextInputEditText review = content.findViewById(R.id.feedbackReview);
        com.google.android.material.checkbox.MaterialCheckBox consent =
                content.findViewById(R.id.feedbackConsent);
        prompt.setText(QuizTypography.inline(question.prompt));
        Map<Integer, String> tagValues = addTags(tags, question.myFeedback);
        restore(question.myFeedback, rating, review, consent);
        tags.setOnCheckedStateChangeListener((group, checkedIds) -> {
            boolean valid = checkedIds.size() <= MAX_TAGS;
            tagError.setVisibility(valid ? View.GONE : View.VISIBLE);
            tagError.setText(valid ? "" : activity.getString(R.string.quiz_feedback_tag_limit));
        });
        MaterialAlertDialogBuilder builder = new MaterialAlertDialogBuilder(activity)
                .setTitle(question.myFeedback == null
                        ? R.string.quiz_feedback_title
                        : R.string.quiz_feedback_edit_title)
                .setView(content)
                .setNegativeButton(R.string.cancel, null)
                .setPositiveButton(R.string.quiz_feedback_save, null);
        if (question.myFeedback != null) {
            builder.setNeutralButton(R.string.quiz_feedback_delete, null);
        }
        AlertDialog dialog = builder.create();
        dialog.setOnShowListener(ignored -> {
            dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(view -> {
                List<String> selected = selectedTags(tags, tagValues);
                String text = review.getText() == null
                        ? null : review.getText().toString().trim();
                if (rating.getRating() < 1 || selected.size() > MAX_TAGS) {
                    tagError.setVisibility(View.VISIBLE);
                    tagError.setText(rating.getRating() < 1
                            ? R.string.quiz_feedback_rating_required
                            : R.string.quiz_feedback_tag_limit);
                    return;
                }
                if (text != null && !text.isEmpty() && !consent.isChecked()) {
                    tagError.setVisibility(View.VISIBLE);
                    tagError.setText(R.string.quiz_feedback_consent_required);
                    return;
                }
                listener.save(
                        question,
                        Math.round(rating.getRating()),
                        selected,
                        text == null || text.isEmpty() ? null : text,
                        consent.isChecked());
                dialog.dismiss();
            });
            if (question.myFeedback != null) {
                dialog.getButton(AlertDialog.BUTTON_NEUTRAL).setOnClickListener(view -> {
                    listener.delete(question);
                    dialog.dismiss();
                });
            }
        });
        dialog.show();
    }

    private Map<Integer, String> addTags(
            ChipGroup group, QuizApiModels.Feedback feedback) {
        LinkedHashMap<String, Integer> choices = new LinkedHashMap<>();
        choices.put("fun", R.string.quiz_feedback_tag_fun);
        choices.put("meaningful", R.string.quiz_feedback_tag_meaningful);
        choices.put("surprising", R.string.quiz_feedback_tag_surprising);
        choices.put("clear", R.string.quiz_feedback_tag_clear);
        choices.put("sparked_conversation", R.string.quiz_feedback_tag_conversation);
        choices.put("repeated", R.string.quiz_feedback_tag_repeated);
        choices.put("too_shallow", R.string.quiz_feedback_tag_shallow);
        choices.put("too_intense", R.string.quiz_feedback_tag_intense);
        choices.put("awkward", R.string.quiz_feedback_tag_awkward);
        choices.put("irrelevant", R.string.quiz_feedback_tag_irrelevant);
        choices.put("unclear", R.string.quiz_feedback_tag_unclear);
        Map<Integer, String> values = new LinkedHashMap<>();
        for (Map.Entry<String, Integer> choice : choices.entrySet()) {
            Chip chip = new Chip(activity);
            chip.setId(View.generateViewId());
            chip.setText(choice.getValue());
            chip.setCheckable(true);
            chip.setMinHeight(dp(48));
            chip.setChecked(feedback != null && feedback.tags.contains(choice.getKey()));
            group.addView(chip);
            values.put(chip.getId(), choice.getKey());
        }
        return values;
    }

    private static void restore(
            QuizApiModels.Feedback feedback,
            RatingBar rating,
            TextInputEditText review,
            com.google.android.material.checkbox.MaterialCheckBox consent) {
        if (feedback == null) return;
        rating.setRating(feedback.stars);
        review.setText(feedback.review);
        consent.setChecked("accepted".equals(feedback.reviewStatus));
    }

    private static List<String> selectedTags(
            ChipGroup group, Map<Integer, String> values) {
        List<String> selected = new ArrayList<>();
        for (Integer id : group.getCheckedChipIds()) {
            String value = values.get(id);
            if (value != null) selected.add(value);
        }
        return selected;
    }

    private int dp(int value) {
        return Math.round(value * activity.getResources().getDisplayMetrics().density);
    }

    /** Receives a validated local edit or deliberate deletion. */
    public interface Listener {
        /** Saves one private rating. */
        void save(
                QuizApiModels.Question question,
                int stars,
                List<String> tags,
                String review,
                boolean consent);

        /** Deletes the caller's current private rating. */
        void delete(QuizApiModels.Question question);
    }
}
