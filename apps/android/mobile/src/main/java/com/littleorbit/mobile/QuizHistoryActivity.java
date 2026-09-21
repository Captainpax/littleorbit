package com.littleorbit.mobile;

import android.content.Intent;
import android.os.Bundle;
import android.widget.LinearLayout;
import android.widget.TextView;
import androidx.appcompat.app.AppCompatActivity;
import com.littleorbit.data.remote.QuizApiModels;
import com.littleorbit.data.repository.OrbitRepository;
import com.littleorbit.mobile.databinding.ActivityQuizHistoryBinding;
import dagger.hilt.android.AndroidEntryPoint;
import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.time.format.DateTimeParseException;
import java.time.format.FormatStyle;
import java.util.List;
import javax.inject.Inject;

/** Thirty-day quiz navigator with server-enforced seven-day catch-up. */
@AndroidEntryPoint
public final class QuizHistoryActivity extends InsetAwareActivity {
    @Inject OrbitRepository orbit;
    private ActivityQuizHistoryBinding binding;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        binding = ActivityQuizHistoryBinding.inflate(getLayoutInflater());
        setContentView(binding.getRoot());
        AsyncUi.observe(this, orbit.quizHistory(), binding.statusText, this::render);
    }

    private void render(List<QuizApiModels.HistoryItem> history) {
        binding.historyContainer.removeAllViews();
        binding.statusText.setText(
                history.isEmpty() ? getString(R.string.quiz_history_empty) : "");
        for (QuizApiModels.HistoryItem item : history) {
            TextView row = new TextView(this);
            String date = displayDate(item.quizDate);
            String status = statusLabel(item.status);
            row.setText(getString(
                    R.string.visual_quiz_history_row,
                    date,
                    status,
                    quantity(R.plurals.visual_quiz_answers, item.answeredCount),
                    quantity(R.plurals.visual_custom_questions, item.customCount))
                    + "\n" + quantity(R.plurals.quiz_feedback_history_count, item.ratedCount));
            row.setTextColor(getColor(R.color.cloud));
            row.setTextSize(16);
            row.setLineSpacing(0, 1.12f);
            row.setMinHeight(dp(64));
            row.setPadding(dp(16), dp(15), dp(16), dp(15));
            row.setBackgroundResource(R.drawable.card_background_muted);
            row.setOnClickListener(view -> openDay(item.quizDate));
            row.setFocusable(true);
            row.setContentDescription(getString(
                    R.string.visual_open_quiz_history, date, status));
            LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.MATCH_PARENT,
                    LinearLayout.LayoutParams.WRAP_CONTENT);
            params.bottomMargin = dp(10);
            binding.historyContainer.addView(row, params);
        }
    }

    private void openDay(String quizDate) {
        Intent intent = new Intent(this, QuizActivity.class);
        intent.putExtra(QuizActivity.EXTRA_QUIZ_DATE, quizDate);
        startActivity(intent);
    }

    private String statusLabel(String status) {
        return switch (status) {
            case "revealed" -> getString(R.string.visual_quiz_ready);
            case "waiting" -> getString(R.string.visual_quiz_waiting);
            case "finished" -> getString(R.string.visual_quiz_finished);
            default -> getString(R.string.visual_quiz_in_progress);
        };
    }

    private String displayDate(String value) {
        try {
            return LocalDate.parse(value).format(DateTimeFormatter.ofLocalizedDate(
                    FormatStyle.MEDIUM));
        } catch (DateTimeParseException invalid) {
            return value;
        }
    }

    private String quantity(int resource, int count) {
        return getResources().getQuantityString(resource, count, count);
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }
}
