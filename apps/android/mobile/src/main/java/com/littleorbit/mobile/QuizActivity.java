package com.littleorbit.mobile;

import android.content.Intent;
import android.graphics.drawable.GradientDrawable;
import android.os.Bundle;
import android.view.Gravity;
import android.view.View;
import android.widget.LinearLayout;
import android.widget.TextView;
import androidx.appcompat.app.AlertDialog;
import androidx.appcompat.app.AppCompatActivity;
import androidx.lifecycle.ViewModelProvider;
import com.littleorbit.data.remote.QuizApiModels;
import com.littleorbit.mobile.databinding.ActivityQuizBinding;
import dagger.hilt.android.AndroidEntryPoint;
import java.util.List;
import java.util.Map;

/** Focused five-question flow with private drafts, review, and atomic reveal. */
@AndroidEntryPoint
public final class QuizActivity extends InsetAwareActivity {
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
        model.state().observe(this, this::render);
        model.load(getIntent().getStringExtra(EXTRA_QUIZ_DATE));
    }

    private void bindActions() {
        binding.backButton.setOnClickListener(view -> finish());
        binding.navHome.setOnClickListener(view -> open(MainActivity.class));
        binding.navQuiz.setOnClickListener(view -> model.load(null));
        binding.navNotes.setOnClickListener(view -> open(NotesActivity.class));
        binding.navMore.setOnClickListener(view -> open(MainActivity.class));
        binding.historyButton.setOnClickListener(view -> open(QuizHistoryActivity.class));
        binding.customButton.setOnClickListener(view -> open(CustomQuestionActivity.class));
        binding.previousButton.setOnClickListener(view -> model.previous());
        binding.nextButton.setOnClickListener(view -> model.next());
        binding.primaryButton.setOnClickListener(view -> primaryAction());
        binding.reportButton.setOnClickListener(view -> showReportReasons());
    }

    private void render(QuizScreenState state) {
        rendered = state;
        binding.statusText.setText(state.error == null ? "" : state.error);
        setContentVisible(!state.loading && state.day != null);
        if (state.loading || state.day == null) {
            binding.statusText.setText(state.error == null ? getString(R.string.loading) : state.error);
            return;
        }
        renderProgress(state);
        if (state.day.revealed) {
            renderReveal(state.day);
        } else if (state.day.myFinished) {
            renderWaiting(state.day);
        } else if (state.reviewing) {
            renderReview(state.day);
        } else {
            renderQuestion(state);
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
    }

    private void renderQuestion(QuizScreenState state) {
        QuizApiModels.Question question = state.day.questions.get(state.questionIndex);
        binding.categoryChip.setText(categoryLabel(question));
        binding.questionText.setText(question.prompt);
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
        for (View view : List.of(binding.questionCard, binding.answerContainer)) {
            view.animate().cancel();
            view.setAlpha(0.72f);
            view.setTranslationY(dp(8));
            view.animate().alpha(1f).translationY(0f).setDuration(180).start();
        }
    }

    private void renderReview(QuizApiModels.Day day) {
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
        TextView row = contentText((index + 1) + ". " + question.prompt + "\n"
                + answerLabel(question, question.myAnswer));
        row.setBackgroundResource(R.drawable.card_background_muted);
        row.setPadding(dp(16), dp(14), dp(16), dp(14));
        row.setOnClickListener(view -> model.editQuestion(index));
        LinearLayout.LayoutParams params = matchParams();
        params.bottomMargin = dp(10);
        binding.answerContainer.addView(row, params);
    }

    private void renderWaiting(QuizApiModels.Day day) {
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
        binding.primaryButton.setText(R.string.back);
    }

    private void addRevealRow(QuizApiModels.Question question) {
        LinearLayout card = new LinearLayout(this);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setPadding(dp(16), dp(14), dp(16), dp(14));
        card.setBackgroundResource(R.drawable.card_background_muted);
        TextView prompt = contentText(question.prompt);
        prompt.setTextColor(getColor(R.color.cloud));
        prompt.setTextSize(17);
        card.addView(prompt);
        card.addView(contentText(getString(R.string.you_label) + "  ·  "
                + answerLabel(question, question.myAnswer)));
        card.addView(contentText(getString(R.string.partner_label) + "  ·  "
                + answerLabel(question, question.partnerAnswer)));
        if ("partner_guess".equals(question.kind)) {
            card.addView(contentText(guessLabel(question)));
        }
        LinearLayout.LayoutParams params = matchParams();
        params.bottomMargin = dp(12);
        binding.answerContainer.addView(card, params);
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
        new AlertDialog.Builder(this)
                .setTitle(R.string.report_dialog_title)
                .setItems(labels, (dialog, which) -> model.report(codes[which], labels[which]))
                .setNegativeButton(R.string.cancel, null)
                .show();
    }

    private void renderProgress(QuizScreenState state) {
        binding.progressContainer.removeAllViews();
        int total = state.day.questions.size();
        int completed = (int) state.day.questions.stream().filter(item -> item.myAnswer != null).count();
        binding.progressText.setText(state.reviewing
                ? getString(R.string.review_answers)
                : getString(R.string.question_progress, state.questionIndex + 1, total));
        for (int index = 0; index < total; index++) {
            View segment = new View(this);
            GradientDrawable bar = new GradientDrawable();
            bar.setCornerRadius(dp(4));
            bar.setColor(getColor(index < completed ? R.color.coral : R.color.orbit_border));
            segment.setBackground(bar);
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
        view.setGravity(Gravity.START);
        view.setPadding(0, dp(7), 0, dp(3));
        return view;
    }

    private static String categoryLabel(QuizApiModels.Question question) {
        String label = question.category.replace('_', ' ');
        return (question.intimacy ? "MUTUAL · " : "") + label.toUpperCase();
    }

    private static String answerLabel(
            QuizApiModels.Question question, Map<String, Object> answer) {
        if (answer == null) return "Not answered";
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
                    .map(option -> option.label + ": " + ratings.get(option.id))
                    .collect(java.util.stream.Collectors.joining("  ·  "));
        }
        if (answer.containsKey("self_option_id")) {
            return optionLabel(question, String.valueOf(answer.get("self_option_id")))
                    + " · guessed "
                    + optionLabel(question, String.valueOf(answer.get("guess_option_id")));
        }
        if (answer.containsKey("rating")) return answer.get("rating") + " of 5";
        return String.valueOf(answer);
    }

    private static String optionLabel(QuizApiModels.Question question, String optionId) {
        return question.options.stream()
                .filter(option -> option.id.equals(optionId))
                .map(option -> option.label)
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
}
