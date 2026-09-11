package com.littleorbit.mobile;

import android.os.Bundle;
import android.view.View;
import android.widget.ArrayAdapter;
import androidx.appcompat.app.AppCompatActivity;
import com.littleorbit.data.remote.ApiModels;
import com.littleorbit.data.repository.OrbitRepository;
import com.littleorbit.mobile.databinding.ActivityQuizBinding;
import dagger.hilt.android.AndroidEntryPoint;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import javax.inject.Inject;

/** Daily quiz renderer that keeps answers hidden until the server marks both submitted. */
@AndroidEntryPoint
public final class QuizActivity extends AppCompatActivity {
    private static final List<String> QUESTION_KINDS = List.of(
            "single_choice", "multiple_choice", "free_text", "partner_guess", "weighted_scale");
    private static final List<String> CATEGORIES = List.of(
            "everyday", "memories", "dreams", "values", "playful", "connection", "intimacy");
    @Inject OrbitRepository orbit;
    private ActivityQuizBinding binding;
    private List<ApiModels.Question> questions = List.of();
    private int currentIndex;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        binding = ActivityQuizBinding.inflate(getLayoutInflater());
        setContentView(binding.getRoot());
        binding.submitButton.setOnClickListener(view -> submit());
        binding.nextButton.setOnClickListener(view -> showNext());
        binding.reportButton.setOnClickListener(view -> report());
        binding.customCreateButton.setOnClickListener(view -> createCustom());
        binding.customKindInput.setAdapter(new ArrayAdapter<>(
                this, android.R.layout.simple_spinner_dropdown_item, QUESTION_KINDS));
        binding.customCategoryInput.setAdapter(new ArrayAdapter<>(
                this, android.R.layout.simple_spinner_dropdown_item, CATEGORIES));
        load();
    }

    private void load() {
        binding.statusText.setText(R.string.loading);
        AsyncUi.observe(
                this,
                orbit.dailyQuestions(LocalDate.now().toString()),
                binding.statusText,
                result -> {
                    questions = new ArrayList<>(result);
                    currentIndex = 0;
                    render();
                });
    }

    private void render() {
        if (questions.isEmpty()) {
            binding.statusText.setText(R.string.questions_preparing);
            return;
        }
        ApiModels.Question question = questions.get(currentIndex);
        binding.questionText.setText(question.prompt);
        binding.progressText.setText(
                getString(R.string.question_progress, currentIndex + 1, questions.size()));
        boolean weighted = "weighted_scale".equals(question.kind);
        boolean freeText = "free_text".equals(question.kind);
        boolean multiple = "multiple_choice".equals(question.kind);
        binding.ratingInput.setVisibility(weighted ? View.VISIBLE : View.GONE);
        binding.answerInput.setVisibility(freeText || multiple ? View.VISIBLE : View.GONE);
        binding.optionInput.setVisibility(freeText || multiple || weighted ? View.GONE : View.VISIBLE);
        binding.answerInput.setHint(multiple ? R.string.multiple_choice_hint : R.string.your_answer);
        binding.optionInput.setAdapter(new ArrayAdapter<>(
                this, android.R.layout.simple_spinner_dropdown_item, question.options));
        if (question.submittedByMe && !question.bothSubmitted) {
            binding.statusText.setText(R.string.answer_waiting);
        } else if (question.bothSubmitted) {
            binding.statusText.setText(getString(
                    R.string.answers_revealed,
                    String.valueOf(question.myAnswer),
                    String.valueOf(question.partnerAnswer)));
        }
    }

    private void submit() {
        if (questions.isEmpty()) {
            return;
        }
        ApiModels.Question question = questions.get(currentIndex);
        Map<String, Object> answer = buildAnswer(question);
        binding.statusText.setText(R.string.submitting);
        AsyncUi.observe(
                this,
                orbit.submitAnswer(question.id, new ApiModels.AnswerRequest(answer)),
                binding.statusText,
                result -> {
                    questions.set(currentIndex, result.get(0));
                    render();
                });
    }

    private Map<String, Object> buildAnswer(ApiModels.Question question) {
        Map<String, Object> answer = new HashMap<>();
        if ("free_text".equals(question.kind)) {
            answer.put("text", binding.answerInput.getText().toString());
        } else if ("weighted_scale".equals(question.kind)) {
            answer.put("rating", binding.ratingInput.getProgress() + 1);
        } else if ("multiple_choice".equals(question.kind)) {
            List<String> values = new ArrayList<>();
            for (String rawValue : binding.answerInput.getText().toString().split(",")) {
                String value = rawValue.trim();
                if (!value.isEmpty()) {
                    values.add(value);
                }
            }
            answer.put("values", values);
        } else {
            answer.put("values", List.of(String.valueOf(binding.optionInput.getSelectedItem())));
        }
        return answer;
    }

    private void showNext() {
        if (!questions.isEmpty()) {
            currentIndex = (currentIndex + 1) % questions.size();
            render();
        }
    }

    private void report() {
        if (questions.isEmpty()) {
            return;
        }
        String reason = binding.reportReasonInput.getText().toString().trim();
        if (reason.length() < 3) {
            binding.statusText.setText(R.string.report_reason_required);
            return;
        }
        ApiModels.Question question = questions.get(currentIndex);
        AsyncUi.observe(
                this,
                orbit.reportQuestion(question.id, new ApiModels.QuestionReportRequest(reason)),
                binding.statusText,
                ignored -> {
                    questions.remove(currentIndex);
                    currentIndex = questions.isEmpty() ? 0 : currentIndex % questions.size();
                    binding.reportReasonInput.setText("");
                    binding.statusText.setText(R.string.question_reported);
                    render();
                });
    }

    private void createCustom() {
        String prompt = binding.customPromptInput.getText().toString().trim();
        String kind = String.valueOf(binding.customKindInput.getSelectedItem());
        String category = String.valueOf(binding.customCategoryInput.getSelectedItem());
        List<String> options = parseOptions();
        boolean choice = List.of("single_choice", "multiple_choice", "partner_guess").contains(kind);
        if (prompt.length() < 12 || (choice && options.size() < 2)) {
            binding.statusText.setText(R.string.complete_required_fields);
            return;
        }
        if (!choice) {
            options = List.of();
        }
        ApiModels.CustomQuestionRequest request = new ApiModels.CustomQuestionRequest(
                LocalDate.now().toString(),
                kind,
                prompt,
                category,
                "intimacy".equals(category),
                options);
        AsyncUi.observe(this, orbit.createCustomQuestion(request), binding.statusText, result -> {
            questions.add(0, result);
            currentIndex = 0;
            binding.customPromptInput.setText("");
            binding.customOptionsInput.setText("");
            binding.statusText.setText(R.string.custom_question_added);
            render();
        });
    }

    private List<String> parseOptions() {
        List<String> options = new ArrayList<>();
        for (String raw : binding.customOptionsInput.getText().toString().split(",")) {
            String option = raw.trim();
            if (!option.isEmpty() && !options.contains(option)) {
                options.add(option);
            }
        }
        return options;
    }
}
