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
import java.util.List;
import javax.inject.Inject;

/** Thirty-day quiz navigator with server-enforced seven-day catch-up. */
@AndroidEntryPoint
public final class QuizHistoryActivity extends AppCompatActivity {
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
            row.setText(getString(
                    R.string.quiz_history_row,
                    item.quizDate,
                    statusLabel(item.status),
                    item.answeredCount,
                    item.customCount));
            row.setTextColor(getColor(R.color.cloud));
            row.setTextSize(16);
            row.setPadding(dp(16), dp(15), dp(16), dp(15));
            row.setBackgroundResource(R.drawable.card_background_muted);
            row.setOnClickListener(view -> openDay(item.quizDate));
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

    private static String statusLabel(String status) {
        return switch (status) {
            case "revealed" -> "Ready together";
            case "waiting" -> "Waiting for partner";
            case "finished" -> "Finished";
            default -> "In progress";
        };
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }
}
