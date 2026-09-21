package com.littleorbit.mobile;

import android.content.Intent;
import android.animation.ValueAnimator;
import android.content.res.ColorStateList;
import android.graphics.drawable.GradientDrawable;
import android.os.Bundle;
import android.view.Gravity;
import android.view.View;
import android.widget.LinearLayout;
import android.widget.TextView;
import com.google.android.material.dialog.MaterialAlertDialogBuilder;
import com.google.android.material.button.MaterialButton;
import androidx.lifecycle.ViewModelProvider;
import com.littleorbit.data.remote.QuizApiModels;
import com.littleorbit.mobile.databinding.ActivityQuizBinding;
import dagger.hilt.android.AndroidEntryPoint;
import java.util.List;
import java.util.Map;

/** Focused five-question flow with private drafts, review, and atomic reveal. */
@AndroidEntryPoint
public final class QuizActivity extends OrbitShellActivity {
    public static final String EXTRA_QUIZ_DATE = "quiz_date";
    private ActivityQuizBinding binding;
    private QuizViewModel model;
    private QuizAnswerRenderer answerRenderer;
    private QuizScreenState rendered;
    private String lastQuestionId;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        binding = ActivityQuizBinding.inflate(getLayoutInflater());
        setContentView(binding.getRoot());
        model = new ViewModelProvider(this).get(QuizViewModel.class);
        answerRenderer = new QuizAnswerRenderer(this, binding.answerContainer);
        bindActions();
        setOrbitContextActions(List.of(
                new ContextAction(getString(R.string.today_orbit), () -> model.load(null)),
                new ContextAction(getString(R.string.quiz_history),
                        () -> open(QuizHistoryActivity.class)),
                new ContextAction(getString(R.string.create_custom_question),
                        () -> open(CustomQuestionActivity.class))));
        model.state().observe(this, this::render);
        model.load(getIntent().getStringExtra(EXTRA_QUIZ_DATE));
    }

    private void bindActions() {
        binding.previousButton.setOnClickListener(view -> model.previous());
        binding.nextButton.setOnClickListener(view -> model.next());
        binding.primaryButton.setOnClickListener(view -> primaryAction());
        binding.resultDoneButton.setOnClickListener(view -> returnHome());
        binding.reportButton.setOnClickListener(view -> showReportReasons());
        binding.retryButton.setOnClickListener(view ->
                model.load(getIntent().getStringExtra(EXTRA_QUIZ_DATE)));
    }

    @Override
    protected OrbitDestination orbitDestination() {
        return OrbitDestination.QUIZ;
    }

    private void render(QuizScreenState state) {
        rendered = state;
        binding.statusText.setText(state.error == null ? "" : state.error);
        binding.retryButton.setVisibility(state.error == null ? View.GONE : View.VISIBLE);
        QuizScreenState.Mode mode = state.mode();
        setContentVisible(mode != QuizScreenState.Mode.LOADING
                && mode != QuizScreenState.Mode.EMPTY);
        if (mode == QuizScreenState.Mode.LOADING) {
            binding.statusText.setText(state.error == null ? getString(R.string.loading) : state.error);
            return;
        }
        if (mode == QuizScreenState.Mode.EMPTY) {
            binding.statusText.setText(R.string.rc14_quiz_unavailable);
            binding.retryButton.setVisibility(View.VISIBLE);
            return;
        }
        renderProgress(state);
        switch (mode) {
            case REVEALED -> renderReveal(state.day);
            case WAITING -> renderWaiting(state.day);
            case REVIEW -> renderReview(state.day);
            case QUESTION -> renderQuestion(state);
            case EMPTY -> throw new IllegalStateException("Empty handled before render");
            case LOADING -> throw new IllegalStateException("Loading handled before render");
        }
    }

    private void setContentVisible(boolean visible) {
        int value = visible ? View.VISIBLE : View.INVISIBLE;
        binding.questionCard.setVisibility(value);
        binding.categoryChip.setVisibility(value);
        binding.answerContainer.setVisibility(value);
        binding.previousButton.setVisibility(value);
        binding.nextButton.setVisibility(value);
        binding.primaryButton.setVisibility(value);
        binding.reportButton.setVisibility(value);
        binding.resultDoneButton.setVisibility(View.GONE);
    }

    private void renderQuestion(QuizScreenState state) {
        binding.resultDoneButton.setVisibility(View.GONE);
        QuizApiModels.Question question = state.day.questions.get(state.questionIndex);
        binding.categoryChip.setText(categoryLabel(question));
        binding.questionText.setText(QuizTypography.inline(question.prompt));
        binding.questionHint.setText(R.string.question_private);
        binding.answerContainer.setVisibility(View.VISIBLE);
        answerRenderer.bind(question);
        binding.previousButton.setVisibility(View.VISIBLE);
        binding.nextButton.setVisibility(View.VISIBLE);
        binding.previousButton.setEnabled(state.questionIndex > 0);
        binding.nextButton.setEnabled(state.questionIndex < state.day.questions.size() - 1
                || state.allAnswered());
        binding.primaryButton.setText(state.questionIndex == state.day.questions.size() - 1
                ? R.string.review_answers : R.string.save_answer);
        binding.reportButton.setVisibility(View.VISIBLE);
        animateQuestionChange(question.id);
    }

    private void animateQuestionChange(String questionId) {
        if (questionId.equals(lastQuestionId)) return;
        lastQuestionId = questionId;
        if (!ValueAnimator.areAnimatorsEnabled()) return;
        for (View view : List.of(binding.questionCard, binding.answerContainer)) {
            view.animate().cancel();
            view.setAlpha(0.72f);
            view.setTranslationY(dp(8));
            view.animate().alpha(1f).translationY(0f).setDuration(180).start();
        }
    }

    private void renderReview(QuizApiModels.Day day) {
        binding.resultDoneButton.setVisibility(View.GONE);
        binding.categoryChip.setText(R.string.review_answers);
        binding.questionText.setText(R.string.review_answers);
        binding.questionHint.setText(R.string.quiz_review_hint);
        binding.answerContainer.setVisibility(View.VISIBLE);
        binding.answerContainer.removeAllViews();
        for (int index = 0; index < day.questions.size(); index++) {
            addReviewRow(day.questions.get(index), index);
        }
        hideSecondaryActions();
        binding.primaryButton.setText(R.string.finish_answers);
    }

    private void addReviewRow(QuizApiModels.Question question, int index) {
        TextView row = contentText((index + 1) + ". "
                + QuizTypography.inline(question.prompt) + "\n"
                + answerLabel(question, question.myAnswer));
        row.setBackgroundResource(R.drawable.card_background_muted);
        row.setPadding(dp(16), dp(14), dp(16), dp(14));
        row.setOnClickListener(view -> model.editQuestion(index));
        row.setFocusable(true);
        row.setContentDescription(getString(
                R.string.rc14_edit_answer_description, index + 1, row.getText()));
        LinearLayout.LayoutParams params = matchParams();
        params.bottomMargin = dp(10);
        binding.answerContainer.addView(row, params);
    }

    private void renderWaiting(QuizApiModels.Day day) {
        binding.resultDoneButton.setVisibility(View.GONE);
        binding.categoryChip.setText(R.string.answers_ready);
        binding.questionText.setText(R.string.waiting_for_answers);
        binding.questionHint.setText(R.string.quiz_utc_hint);
        binding.answerContainer.setVisibility(View.GONE);
        hideSecondaryActions();
        binding.primaryButton.setText(R.string.edit_answers);
    }

    private void renderReveal(QuizApiModels.Day day) {
        binding.categoryChip.setText(R.string.answers_ready);
        binding.questionText.setText(R.string.answers_ready);
        binding.questionHint.setText(day.quizDate);
        binding.answerContainer.setVisibility(View.VISIBLE);
        binding.answerContainer.removeAllViews();
        for (QuizApiModels.Question question : day.questions) {
            addRevealRow(question);
        }
        hideSecondaryActions();
        binding.primaryButton.setVisibility(View.GONE);
        binding.resultDoneButton.setVisibility(View.VISIBLE);
    }

    private void addRevealRow(QuizApiModels.Question question) {
        LinearLayout card = new LinearLayout(this);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setPadding(dp(16), dp(14), dp(16), dp(14));
        card.setBackgroundResource(R.drawable.card_background_muted);
        TextView prompt = contentText(QuizTypography.inline(question.prompt));
        prompt.setTextColor(getColor(R.color.cloud));
        prompt.setTextSize(17);
        card.addView(prompt);
        card.addView(contentText(getString(R.string.you_label) + " · "
                + answerLabel(question, question.myAnswer)));
        card.addView(contentText(getString(R.string.partner_label) + " · "
                + answerLabel(question, question.partnerAnswer)));
        if ("partner_guess".equals(question.kind)) {
            card.addView(contentText(guessLabel(question)));
        }
        if (question.myFeedback != null) {
            TextView summary = contentText(getString(
                    R.string.quiz_feedback_saved_summary, question.myFeedback.stars));
            summary.setTextColor(getColor(R.color.lavender_soft));
            summary.setContentDescription(summary.getText());
            card.addView(summary);
        }
        if (question.feedbackEligible) {
            MaterialButton feedback = new MaterialButton(this);
            feedback.setText(question.myFeedback == null
                    ? getString(R.string.quiz_feedback_rate_action)
                    : getString(R.string.quiz_feedback_edit_action, question.myFeedback.stars));
            feedback.setMinHeight(dp(48));
            feedback.setTextColor(getColor(R.color.lavender_soft));
            feedback.setStrokeColor(ColorStateList.valueOf(getColor(R.color.orbit_border)));
            feedback.setStrokeWidth(dp(1));
            feedback.setOnClickListener(view -> showFeedback(question));
            LinearLayout.LayoutParams feedbackParams = matchParams();
            feedbackParams.topMargin = dp(10);
            card.addView(feedback, feedbackParams);
        }
        LinearLayout.LayoutParams params = matchParams();
        params.bottomMargin = dp(12);
        binding.answerContainer.addView(card, params);
    }

    private void showFeedback(QuizApiModels.Question question) {
        new QuizFeedbackDialog(this).show(question, new QuizFeedbackDialog.Listener() {
            @Override
            public void save(
                    QuizApiModels.Question selected,
                    int stars,
                    List<String> tags,
                    String review,
                    boolean consent) {
                model.saveFeedback(selected, stars, tags, review, consent);
            }

            @Override
            public void delete(QuizApiModels.Question selected) {
                model.deleteFeedback(selected);
            }
        });
    }

    private String guessLabel(QuizApiModels.Question question) {
        Object guess = value(question.myAnswer, "guess_option_id");
        Object actual = value(question.partnerAnswer, "self_option_id");
        return getString(guess != null && guess.equals(actual)
                ? R.string.partner_guess_match : R.string.partner_guess_miss);
    }

    private void hideSecondaryActions() {
        binding.previousButton.setVisibility(View.GONE);
        binding.nextButton.setVisibility(View.GONE);
        binding.reportButton.setVisibility(View.GONE);
    }

    private void primaryAction() {
        if (rendered == null || rendered.day == null || rendered.loading) return;
        if (rendered.day.revealed) {
            finish();
        } else if (rendered.day.myFinished) {
            model.reopen();
        } else if (rendered.reviewing) {
            model.finish();
        } else {
            saveCurrent();
        }
    }

    private void saveCurrent() {
        try {
            model.save(answerRenderer.answer());
        } catch (IllegalStateException failure) {
            binding.statusText.setText(failure.getMessage() == null
                    ? getString(R.string.quiz_answer_required) : failure.getMessage());
        }
    }

    private void showReportReasons() {
        String[] labels = {
            getString(R.string.report_unsafe), getString(R.string.report_personal),
            getString(R.string.report_duplicate), getString(R.string.report_other)
        };
        String[] codes = {"unsafe", "irrelevant", "repeated", "other"};
        new MaterialAlertDialogBuilder(this)
                .setTitle(R.string.report_dialog_title)
                .setItems(labels, (dialog, which) -> model.report(codes[which], labels[which]))
                .setNegativeButton(R.string.cancel, null)
                .show();
    }

    private void renderProgress(QuizScreenState state) {
        binding.progressContainer.removeAllViews();
        int total = state.day.questions.size();
        int completed = (int) state.day.questions.stream().filter(item -> item.myAnswer != null).count();
        binding.progressText.setText(state.day.revealed
                ? getString(R.string.quiz_complete)
                : state.reviewing
                        ? getString(R.string.review_answers)
                        : getString(R.string.question_progress, state.questionIndex + 1, total));
        binding.progressContainer.setImportantForAccessibility(
                View.IMPORTANT_FOR_ACCESSIBILITY_NO);
        for (int index = 0; index < total; index++) {
            View segment = new View(this);
            GradientDrawable bar = new GradientDrawable();
            bar.setCornerRadius(dp(4));
            bar.setColor(getColor(state.day.revealed || index < completed
                    ? R.color.coral : R.color.orbit_border));
            segment.setBackground(bar);
            segment.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
            LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(0, dp(5), 1);
            if (index > 0) params.leftMargin = dp(5);
            binding.progressContainer.addView(segment, params);
        }
    }

    private TextView contentText(String text) {
        TextView view = new TextView(this);
        view.setText(text);
        view.setTextColor(getColor(R.color.muted));
        view.setTextSize(15);
        view.setLineSpacing(0, 1.12f);
        view.setGravity(Gravity.START);
        view.setPadding(0, dp(7), 0, dp(3));
        return view;
    }

    private static String categoryLabel(QuizApiModels.Question question) {
        return QuizTypography.category(question.category, question.intimacy);
    }

    private String answerLabel(
            QuizApiModels.Question question, Map<String, Object> answer) {
        if (answer == null) return getString(R.string.rc14_not_answered);
        if (answer.containsKey("text")) return String.valueOf(answer.get("text"));
        if (answer.containsKey("selected_option_id")) {
            return optionLabel(question, String.valueOf(answer.get("selected_option_id")));
        }
        if (answer.get("selected_option_ids") instanceof List<?> selected) {
            return selected.stream()
                    .map(id -> optionLabel(question, String.valueOf(id)))
                    .collect(java.util.stream.Collectors.joining(", "));
        }
        if (answer.get("ratings") instanceof Map<?, ?> ratings) {
            return question.options.stream()
                    .map(option -> getString(
                            R.string.rc14_weighted_answer,
                            QuizTypography.inline(option.label),
                            String.valueOf(ratings.get(option.id))))
                    .collect(java.util.stream.Collectors.joining(" · "));
        }
        if (answer.containsKey("self_option_id")) {
            return getString(
                    R.string.rc14_guess_answer,
                    optionLabel(question, String.valueOf(answer.get("self_option_id"))),
                    optionLabel(question, String.valueOf(answer.get("guess_option_id"))));
        }
        if (answer.containsKey("rating")) {
            return getString(R.string.rc14_rating_answer, String.valueOf(answer.get("rating")));
        }
        return String.valueOf(answer);
    }

    private static String optionLabel(QuizApiModels.Question question, String optionId) {
        return question.options.stream()
                .filter(option -> option.id.equals(optionId))
                .map(option -> QuizTypography.inline(option.label))
                .findFirst()
                .orElse(optionId);
    }

    private static Object value(Map<String, Object> answer, String key) {
        return answer == null ? null : answer.get(key);
    }

    private LinearLayout.LayoutParams matchParams() {
        return new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    private void open(Class<?> activity) {
        startActivity(new Intent(this, activity));
    }

    private void returnHome() {
        Intent intent = new Intent(this, MainActivity.class)
                .addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_SINGLE_TOP);
        startActivity(intent);
        finish();
    }
}
