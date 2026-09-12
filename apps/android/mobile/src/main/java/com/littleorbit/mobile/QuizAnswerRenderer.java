package com.littleorbit.mobile;

import android.content.Context;
import android.view.View;
import android.widget.ArrayAdapter;
import android.widget.LinearLayout;
import android.widget.RadioGroup;
import android.widget.Spinner;
import android.widget.TextView;
import com.google.android.material.checkbox.MaterialCheckBox;
import com.google.android.material.radiobutton.MaterialRadioButton;
import com.google.android.material.textfield.TextInputEditText;
import com.littleorbit.data.remote.QuizApiModels;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

/** Builds accessible interaction-specific answer controls inside the focused card. */
public final class QuizAnswerRenderer {
    private final Context context;
    private final LinearLayout container;
    private QuizApiModels.Question question;
    private TextInputEditText textInput;
    private RadioGroup singleGroup;
    private final List<MaterialCheckBox> checks = new ArrayList<>();
    private Spinner selfChoice;
    private Spinner partnerGuess;
    private final Map<String, RadioGroup> ratingGroups = new LinkedHashMap<>();

    /** Creates a renderer bound to one answer container. */
    public QuizAnswerRenderer(Context context, LinearLayout container) {
        this.context = context;
        this.container = container;
    }

    /** Rebuilds controls for one immutable question snapshot. */
    public void bind(QuizApiModels.Question value) {
        question = value;
        container.removeAllViews();
        checks.clear();
        ratingGroups.clear();
        textInput = null;
        singleGroup = null;
        selfChoice = null;
        partnerGuess = null;
        switch (value.kind) {
            case "single_choice" -> bindSingle();
            case "multiple_choice" -> bindMultiple();
            case "free_text" -> bindText();
            case "partner_guess" -> bindPartnerGuess();
            case "weighted_choice" -> bindWeighted();
            case "weighted_scale" -> bindLegacyRating();
            default -> addHint("This question type needs a newer Little Orbit update.");
        }
    }

    /** Returns a typed answer map, or throws when a required control is incomplete. */
    public Map<String, Object> answer() {
        return switch (question.kind) {
            case "single_choice" -> singleAnswer();
            case "multiple_choice" -> multipleAnswer();
            case "free_text" -> textAnswer();
            case "partner_guess" -> partnerAnswer();
            case "weighted_choice" -> weightedAnswer();
            case "weighted_scale" -> legacyRatingAnswer();
            default -> throw new IllegalStateException("Unsupported question type");
        };
    }

    private void bindSingle() {
        singleGroup = verticalRadioGroup();
        for (QuizApiModels.Option option : question.options) {
            MaterialRadioButton button = radio(option.label, option.id);
            singleGroup.addView(button);
            if (option.id.equals(stringValue(question.myAnswer, "selected_option_id"))) {
                button.setChecked(true);
            }
        }
        container.addView(singleGroup);
    }

    private void bindMultiple() {
        List<String> selected = stringList(question.myAnswer, "selected_option_ids");
        for (QuizApiModels.Option option : question.options) {
            MaterialCheckBox check = new MaterialCheckBox(context);
            check.setText(option.label);
            check.setTag(option.id);
            check.setTextColor(context.getColor(R.color.cloud));
            check.setMinHeight(dp(56));
            check.setPadding(dp(12), 0, dp(12), 0);
            check.setBackgroundResource(R.drawable.quiz_option_background);
            check.setChecked(selected.contains(option.id));
            checks.add(check);
            container.addView(check, marginParams());
        }
    }

    private void bindText() {
        textInput = new TextInputEditText(context);
        textInput.setHint(R.string.your_answer);
        textInput.setText(stringValue(question.myAnswer, "text"));
        textInput.setTextColor(context.getColor(R.color.cloud));
        textInput.setHintTextColor(context.getColor(R.color.muted));
        textInput.setBackgroundResource(R.drawable.card_background_muted);
        textInput.setGravity(android.view.Gravity.TOP);
        textInput.setMinHeight(dp(132));
        textInput.setPadding(dp(16), dp(14), dp(16), dp(14));
        container.addView(textInput, matchParams());
    }

    private void bindPartnerGuess() {
        addHint("First, choose your answer");
        selfChoice = optionSpinner();
        selectSpinner(selfChoice, stringValue(question.myAnswer, "self_option_id"));
        container.addView(selfChoice, matchParams());
        addHint("Then guess your partner’s answer");
        partnerGuess = optionSpinner();
        selectSpinner(partnerGuess, stringValue(question.myAnswer, "guess_option_id"));
        container.addView(partnerGuess, matchParams());
    }

    private void bindWeighted() {
        Map<String, Object> saved = nestedMap(question.myAnswer, "ratings");
        for (QuizApiModels.Option option : question.options) {
            TextView label = label(option.label);
            container.addView(label);
            RadioGroup group = horizontalRatingGroup();
            Number selected = saved.get(option.id) instanceof Number number ? number : null;
            for (int rating = 1; rating <= 5; rating++) {
                MaterialRadioButton button = radio(String.valueOf(rating), String.valueOf(rating));
                group.addView(button, weightedRadioParams());
                if (selected != null && selected.intValue() == rating) {
                    button.setChecked(true);
                }
            }
            ratingGroups.put(option.id, group);
            container.addView(group);
            TextView anchors = label(anchorText());
            anchors.setTextSize(12);
            anchors.setTextColor(context.getColor(R.color.muted));
            container.addView(anchors);
        }
    }

    private void bindLegacyRating() {
        singleGroup = horizontalRatingGroup();
        Number saved = question.myAnswer == null ? null : (Number) question.myAnswer.get("rating");
        for (int rating = 1; rating <= 5; rating++) {
            MaterialRadioButton button = radio(String.valueOf(rating), String.valueOf(rating));
            singleGroup.addView(button, weightedRadioParams());
            if (saved != null && saved.intValue() == rating) {
                button.setChecked(true);
            }
        }
        container.addView(singleGroup);
    }

    private Map<String, Object> singleAnswer() {
        return Map.of("kind", "single_choice", "selected_option_id", checkedTag(singleGroup));
    }

    private Map<String, Object> multipleAnswer() {
        List<String> selected = checks.stream()
                .filter(MaterialCheckBox::isChecked)
                .map(item -> String.valueOf(item.getTag()))
                .collect(Collectors.toList());
        if (selected.isEmpty()) {
            throw new IllegalStateException("Choose at least one option");
        }
        return Map.of("kind", "multiple_choice", "selected_option_ids", selected);
    }

    private Map<String, Object> textAnswer() {
        String text = textInput == null ? "" : String.valueOf(textInput.getText()).trim();
        if (text.isEmpty()) {
            throw new IllegalStateException("Write an answer first");
        }
        return Map.of("kind", "free_text", "text", text);
    }

    private Map<String, Object> partnerAnswer() {
        return Map.of(
                "kind", "partner_guess",
                "self_option_id", selectedOptionId(selfChoice),
                "guess_option_id", selectedOptionId(partnerGuess));
    }

    private Map<String, Object> weightedAnswer() {
        Map<String, Integer> ratings = new LinkedHashMap<>();
        ratingGroups.forEach((id, group) -> ratings.put(id, Integer.parseInt(checkedTag(group))));
        return Map.of("kind", "weighted_choice", "ratings", ratings);
    }

    private Map<String, Object> legacyRatingAnswer() {
        return Map.of("kind", "weighted_scale", "rating", Integer.parseInt(checkedTag(singleGroup)));
    }

    private RadioGroup verticalRadioGroup() {
        RadioGroup group = new RadioGroup(context);
        group.setOrientation(RadioGroup.VERTICAL);
        return group;
    }

    private RadioGroup horizontalRatingGroup() {
        RadioGroup group = new RadioGroup(context);
        group.setOrientation(RadioGroup.HORIZONTAL);
        group.setWeightSum(5);
        return group;
    }

    private MaterialRadioButton radio(String text, String tag) {
        MaterialRadioButton button = new MaterialRadioButton(context);
        button.setId(View.generateViewId());
        button.setText(text);
        button.setTag(tag);
        button.setTextColor(context.getColor(R.color.cloud));
        button.setMinHeight(dp(52));
        button.setPadding(dp(10), 0, dp(10), 0);
        button.setBackgroundResource(R.drawable.quiz_option_background);
        return button;
    }

    private Spinner optionSpinner() {
        Spinner spinner = new Spinner(context);
        List<String> labels = question.options.stream()
                .map(item -> item.label)
                .collect(Collectors.toList());
        ArrayAdapter<String> adapter = new ArrayAdapter<>(
                context, android.R.layout.simple_spinner_dropdown_item, labels);
        spinner.setAdapter(adapter);
        spinner.setBackgroundResource(R.drawable.card_background_muted);
        spinner.setMinimumHeight(dp(56));
        spinner.setPadding(dp(14), 0, dp(14), 0);
        return spinner;
    }

    private void selectSpinner(Spinner spinner, String optionId) {
        if (optionId != null && optionId.matches("o[1-6]")) {
            spinner.setSelection(Integer.parseInt(optionId.substring(1)) - 1);
        }
    }

    private String selectedOptionId(Spinner spinner) {
        if (spinner == null || spinner.getSelectedItemPosition() < 0) {
            throw new IllegalStateException("Choose an option");
        }
        return "o" + (spinner.getSelectedItemPosition() + 1);
    }

    private static String checkedTag(RadioGroup group) {
        if (group == null || group.getCheckedRadioButtonId() == View.NO_ID) {
            throw new IllegalStateException("Choose a rating or option");
        }
        View checked = group.findViewById(group.getCheckedRadioButtonId());
        return String.valueOf(checked.getTag());
    }

    private void addHint(String text) {
        TextView hint = label(text);
        hint.setTextColor(context.getColor(R.color.lavender_soft));
        container.addView(hint);
    }

    private TextView label(String text) {
        TextView view = new TextView(context);
        view.setText(text);
        view.setTextColor(context.getColor(R.color.cloud));
        view.setTextSize(16);
        view.setPadding(dp(4), dp(12), dp(4), dp(8));
        return view;
    }

    private String anchorText() {
        String low = question.scaleLowLabel == null ? "Low" : question.scaleLowLabel;
        String high = question.scaleHighLabel == null ? "High" : question.scaleHighLabel;
        return low + "                                      " + high;
    }

    private LinearLayout.LayoutParams matchParams() {
        return new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
    }

    private LinearLayout.LayoutParams marginParams() {
        LinearLayout.LayoutParams params = matchParams();
        params.bottomMargin = dp(8);
        return params;
    }

    private LinearLayout.LayoutParams weightedRadioParams() {
        return new RadioGroup.LayoutParams(0, dp(54), 1);
    }

    private int dp(int value) {
        return Math.round(value * context.getResources().getDisplayMetrics().density);
    }

    private static String stringValue(Map<String, Object> map, String key) {
        return map == null || map.get(key) == null ? null : String.valueOf(map.get(key));
    }

    @SuppressWarnings("unchecked")
    private static List<String> stringList(Map<String, Object> map, String key) {
        Object value = map == null ? null : map.get(key);
        return value instanceof List<?> list
                ? list.stream().map(String::valueOf).collect(Collectors.toList())
                : List.of();
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> nestedMap(Map<String, Object> map, String key) {
        Object value = map == null ? null : map.get(key);
        return value instanceof Map<?, ?> nested ? (Map<String, Object>) nested : new HashMap<>();
    }
}
