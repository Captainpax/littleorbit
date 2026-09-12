package com.littleorbit.mobile;

import android.os.Bundle;
import android.view.View;
import android.widget.ArrayAdapter;
import android.widget.LinearLayout;
import android.widget.TextView;
import androidx.appcompat.app.AppCompatActivity;
import com.littleorbit.data.remote.QuizApiModels;
import com.littleorbit.data.repository.OrbitRepository;
import com.littleorbit.mobile.databinding.ActivityCustomQuestionBinding;
import dagger.hilt.android.AndroidEntryPoint;
import java.util.ArrayList;
import java.util.List;
import javax.inject.Inject;

/** Three-step custom question composer with automatic FIFO scheduling. */
@AndroidEntryPoint
public final class CustomQuestionActivity extends AppCompatActivity {
    private static final List<String> KINDS = List.of(
            "single_choice", "multiple_choice", "free_text", "partner_guess", "weighted_choice");
    private static final List<String> CATEGORIES = List.of(
            "everyday", "memories", "dreams", "values", "playful", "connection", "intimacy");
    private static final List<String> ICONS = List.of("heart", "chat", "star", "play", "home", "travel");
    @Inject OrbitRepository orbit;
    private ActivityCustomQuestionBinding binding;
    private int step = 1;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        binding = ActivityCustomQuestionBinding.inflate(getLayoutInflater());
        setContentView(binding.getRoot());
        bindSpinners();
        binding.previousButton.setOnClickListener(view -> previous());
        binding.nextButton.setOnClickListener(view -> next());
        renderStep();
        loadQueue();
    }

    private void bindSpinners() {
        binding.kindInput.setAdapter(new ArrayAdapter<>(
                this, android.R.layout.simple_spinner_dropdown_item, KINDS));
        binding.categoryInput.setAdapter(new ArrayAdapter<>(
                this, android.R.layout.simple_spinner_dropdown_item, CATEGORIES));
    }

    private void next() {
        if (step == 1 && !validBasics()) return;
        if (step == 2 && !validDetails()) return;
        if (step < 3) {
            step++;
            renderStep();
        } else {
            create();
        }
    }

    private void previous() {
        if (step == 1) {
            finish();
        } else {
            step--;
            renderStep();
        }
    }

    private void renderStep() {
        binding.stepText.setText(getString(R.string.custom_step, step));
        binding.basicsStep.setVisibility(step == 1 ? View.VISIBLE : View.GONE);
        binding.detailsStep.setVisibility(step == 2 ? View.VISIBLE : View.GONE);
        binding.previewStep.setVisibility(step == 3 ? View.VISIBLE : View.GONE);
        binding.previousButton.setText(step == 1 ? R.string.cancel : R.string.back);
        binding.nextButton.setText(step == 3 ? R.string.queue_question : R.string.next_question);
        int guidance = step == 1 ? R.string.custom_basics_hint
                : step == 2 ? R.string.custom_details_hint : R.string.custom_preview_hint;
        binding.guidanceText.setText(guidance);
        if (step == 2) renderDetailFields();
        if (step == 3) binding.previewText.setText(preview());
    }

    private void renderDetailFields() {
        String kind = selected(binding.kindInput);
        binding.optionsInput.setVisibility(
                "free_text".equals(kind) ? View.GONE : View.VISIBLE);
        int anchorVisibility = "weighted_choice".equals(kind) ? View.VISIBLE : View.GONE;
        binding.lowAnchorInput.setVisibility(anchorVisibility);
        binding.highAnchorInput.setVisibility(anchorVisibility);
    }

    private boolean validBasics() {
        String prompt = text(binding.promptInput);
        if (prompt.length() < 12 || prompt.length() > 240) {
            binding.statusText.setText(R.string.complete_required_fields);
            return false;
        }
        binding.statusText.setText("");
        return true;
    }

    private boolean validDetails() {
        String kind = selected(binding.kindInput);
        List<String> options = options();
        boolean choice = !"free_text".equals(kind);
        int upper = "weighted_choice".equals(kind) ? 5 : 6;
        boolean anchors = !"weighted_choice".equals(kind)
                || (text(binding.lowAnchorInput).length() >= 2
                        && text(binding.highAnchorInput).length() >= 2);
        if ((choice && (options.size() < 2 || options.size() > upper)) || !anchors) {
            binding.statusText.setText(R.string.complete_required_fields);
            return false;
        }
        binding.statusText.setText("");
        return true;
    }

    private String preview() {
        String kind = selected(binding.kindInput).replace('_', ' ');
        String choices = options().isEmpty() ? "Write your own answer" : String.join("  ·  ", options());
        return text(binding.promptInput) + "\n\n" + kind + "\n" + choices;
    }

    private void create() {
        List<QuizApiModels.Option> choices = new ArrayList<>();
        List<String> labels = options();
        for (int index = 0; index < labels.size(); index++) {
            choices.add(new QuizApiModels.Option(
                    "o" + (index + 1), labels.get(index), ICONS.get(index % ICONS.size())));
        }
        String kind = selected(binding.kindInput);
        String category = selected(binding.categoryInput);
        QuizApiModels.CustomMutation mutation = new QuizApiModels.CustomMutation(
                kind,
                text(binding.promptInput),
                category,
                "intimacy".equals(category),
                choices,
                "weighted_choice".equals(kind) ? text(binding.lowAnchorInput) : null,
                "weighted_choice".equals(kind) ? text(binding.highAnchorInput) : null,
                binding.surpriseInput.isChecked());
        AsyncUi.observe(this, orbit.createCustomQuiz(mutation), binding.statusText, created -> {
            binding.statusText.setText(getString(R.string.custom_queued_for, created.publishDate));
            resetComposer();
            loadQueue();
        });
    }

    private void resetComposer() {
        binding.promptInput.setText("");
        binding.optionsInput.setText("");
        binding.lowAnchorInput.setText("");
        binding.highAnchorInput.setText("");
        step = 1;
        renderStep();
    }

    private void loadQueue() {
        AsyncUi.observe(this, orbit.customQuizQueue(), binding.statusText, queue -> {
            binding.queueContainer.removeAllViews();
            if (queue.mine.isEmpty()) addQueueText(getString(R.string.custom_queue_empty));
            for (QuizApiModels.CustomQuestion item : queue.mine) {
                addQueueText(getString(
                        R.string.custom_queue_row, item.publishDate, item.customSlot, item.prompt));
            }
            for (QuizApiModels.CustomQuestion item : queue.shared) {
                addQueueText(getString(
                        R.string.custom_shared_row, item.publishDate, item.customSlot, item.prompt));
            }
            if (queue.partnerSurpriseCount > 0) {
                addQueueText(getString(R.string.partner_surprises, queue.partnerSurpriseCount));
            }
        });
    }

    private void addQueueText(String content) {
        TextView row = new TextView(this);
        row.setText(content);
        row.setTextColor(getColor(R.color.cloud));
        row.setPadding(dp(14), dp(12), dp(14), dp(12));
        row.setBackgroundResource(R.drawable.card_background_muted);
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        params.bottomMargin = dp(8);
        binding.queueContainer.addView(row, params);
    }

    private List<String> options() {
        List<String> values = new ArrayList<>();
        for (String raw : text(binding.optionsInput).split("[,\\n]")) {
            String value = raw.trim();
            if (!value.isEmpty() && !values.contains(value)) values.add(value);
        }
        return values;
    }

    private static String text(android.widget.EditText input) {
        return String.valueOf(input.getText()).trim();
    }

    private static String selected(android.widget.Spinner input) {
        return String.valueOf(input.getSelectedItem());
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }
}
