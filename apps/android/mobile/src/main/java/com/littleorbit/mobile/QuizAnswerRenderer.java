package com.littleorbit.mobile;

import android.content.Context;
import android.content.res.Configuration;
import android.text.InputType;
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
    private final boolean stackedRatings;

    /** Creates a renderer bound to one answer container. */
    public QuizAnswerRenderer(Context context, LinearLayout container) {
        this.context = context;
        this.container = container;
        Configuration configuration = context.getResources().getConfiguration();
        stackedRatings = configuration.screenWidthDp < 380 || configuration.fontScale >= 1.3f;
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
            default -> addHint(context.getString(R.string.rc14_unsupported_question));
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
            default -> throw new IllegalStateException(
                    context.getString(R.string.rc14_unsupported_question));
        };
    }

    private void bindSingle() {
        singleGroup = verticalRadioGroup();
        for (QuizApiModels.Option option : question.options) {
            MaterialRadioButton button = radio(QuizTypography.inline(option.label), option.id);
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
            check.setText(QuizTypography.inline(option.label));
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
        textInput.setInputType(InputType.TYPE_CLASS_TEXT
                | InputType.TYPE_TEXT_FLAG_CAP_SENTENCES
                | InputType.TYPE_TEXT_FLAG_MULTI_LINE);
        textInput.setMinHeight(dp(132));
        textInput.setPadding(dp(16), dp(14), dp(16), dp(14));
        container.addView(textInput, matchParams());
    }

    private void bindPartnerGuess() {
        addHint(context.getString(R.string.rc14_self_answer));
        selfChoice = optionSpinner();
        selectSpinner(selfChoice, stringValue(question.myAnswer, "self_option_id"));
        container.addView(selfChoice, matchParams());
        addHint(context.getString(R.string.rc14_partner_guess));
        partnerGuess = optionSpinner();
        selectSpinner(partnerGuess, stringValue(question.myAnswer, "guess_option_id"));
        container.addView(partnerGuess, matchParams());
    }

    private void bindWeighted() {
        Map<String, Object> saved = nestedMap(question.myAnswer, "ratings");
        for (QuizApiModels.Option option : question.options) {
            String optionLabel = QuizTypography.inline(option.label);
            TextView label = label(optionLabel);
            container.addView(label);
            RadioGroup group = ratingGroup();
            Number selected = saved.get(option.id) instanceof Number number ? number : null;
            for (int rating = 1; rating <= 5; rating++) {
                MaterialRadioButton button = ratingButton(optionLabel, rating);
                group.addView(button, ratingParams());
                if (selected != null && selected.intValue() == rating) {
                    button.setChecked(true);
                }
            }
            ratingGroups.put(option.id, group);
            container.addView(group);
            if (!stackedRatings) container.addView(anchorRow());
        }
    }

    private void bindLegacyRating() {
        singleGroup = ratingGroup();
        Number saved = question.myAnswer == null ? null : (Number) question.myAnswer.get("rating");
        for (int rating = 1; rating <= 5; rating++) {
            MaterialRadioButton button = ratingButton(
                    QuizTypography.inline(question.prompt), rating);
            singleGroup.addView(button, ratingParams());
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
            throw new IllegalStateException(context.getString(R.string.rc14_choose_multiple));
        }
        return Map.of("kind", "multiple_choice", "selected_option_ids", selected);
    }

    private Map<String, Object> textAnswer() {
        String text = textInput == null ? "" : String.valueOf(textInput.getText()).trim();
        if (text.isEmpty()) {
            throw new IllegalStateException(context.getString(R.string.rc14_write_answer));
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

    private RadioGroup ratingGroup() {
        RadioGroup group = new RadioGroup(context);
        group.setOrientation(stackedRatings ? RadioGroup.VERTICAL : RadioGroup.HORIZONTAL);
        if (!stackedRatings) group.setWeightSum(5);
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

    private MaterialRadioButton ratingButton(String optionLabel, int rating) {
        String anchor = rating == 1
                ? scaleLow() : rating == 5 ? scaleHigh()
                : context.getString(R.string.rc14_rating_middle);
        String visible = stackedRatings && (rating == 1 || rating == 5)
                ? rating + " · " + anchor : String.valueOf(rating);
        MaterialRadioButton button = radio(visible, String.valueOf(rating));
        button.setContentDescription(context.getString(
                R.string.rc14_rating_description, optionLabel, rating, anchor));
        return button;
    }

    private Spinner optionSpinner() {
        Spinner spinner = new Spinner(context);
        List<String> labels = question.options.stream()
                .map(item -> QuizTypography.inline(item.label))
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
        if (optionId == null) return;
        for (int index = 0; index < question.options.size(); index++) {
            if (optionId.equals(question.options.get(index).id)) {
                spinner.setSelection(index);
                return;
            }
        }
    }

    private String selectedOptionId(Spinner spinner) {
        if (spinner == null || spinner.getSelectedItemPosition() < 0) {
            throw new IllegalStateException(context.getString(R.string.rc14_choose_option));
        }
        return question.options.get(spinner.getSelectedItemPosition()).id;
    }

    private String checkedTag(RadioGroup group) {
        if (group == null || group.getCheckedRadioButtonId() == View.NO_ID) {
            throw new IllegalStateException(context.getString(R.string.rc14_choose_option));
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

    private LinearLayout anchorRow() {
        LinearLayout row = new LinearLayout(context);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.addView(anchor(scaleLow(), android.view.Gravity.START));
        row.addView(anchor(scaleHigh(), android.view.Gravity.END));
        return row;
    }

    private TextView anchor(String text, int gravity) {
        TextView view = label(text);
        view.setTextSize(12);
        view.setTextColor(context.getColor(R.color.muted));
        view.setGravity(gravity);
        view.setPadding(dp(4), dp(4), dp(4), dp(12));
        rowParams(view);
        return view;
    }

    private void rowParams(TextView view) {
        view.setLayoutParams(new LinearLayout.LayoutParams(0,
                LinearLayout.LayoutParams.WRAP_CONTENT, 1));
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

    private RadioGroup.LayoutParams ratingParams() {
        if (stackedRatings) {
            RadioGroup.LayoutParams params = new RadioGroup.LayoutParams(
                    RadioGroup.LayoutParams.MATCH_PARENT,
                    RadioGroup.LayoutParams.WRAP_CONTENT);
            params.bottomMargin = dp(4);
            return params;
        }
        return new RadioGroup.LayoutParams(0, dp(54), 1);
    }

    private String scaleLow() {
        return QuizTypography.inline(question.scaleLowLabel == null
                ? context.getString(R.string.rc14_scale_low) : question.scaleLowLabel);
    }

    private String scaleHigh() {
        return QuizTypography.inline(question.scaleHighLabel == null
                ? context.getString(R.string.rc14_scale_high) : question.scaleHighLabel);
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
