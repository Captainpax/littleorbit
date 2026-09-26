package com.littleorbit.mobile;

import android.view.View;
import android.widget.ArrayAdapter;
import com.google.android.material.bottomsheet.BottomSheetBehavior;
import com.google.android.material.bottomsheet.BottomSheetDialog;
import com.google.android.material.datepicker.MaterialDatePicker;
import com.google.android.material.dialog.MaterialAlertDialogBuilder;
import com.google.android.material.timepicker.MaterialTimePicker;
import com.google.android.material.timepicker.TimeFormat;
import com.littleorbit.data.remote.CountdownApiModels;
import com.littleorbit.mobile.databinding.DialogCountdownEditorBinding;
import java.time.Instant;
import java.time.LocalDate;
import java.time.LocalTime;
import java.time.ZoneId;
import java.time.ZoneOffset;
import java.time.ZonedDateTime;
import java.time.format.DateTimeFormatter;
import java.time.format.FormatStyle;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.UUID;

/** Focused countdown editor with calendar pickers and account-scoped reminders. */
final class CountdownEditorDialog {
    interface Listener {
        void save(EditResult result);
        void delete(CountdownApiModels.Countdown countdown);
    }

    record EditResult(
            CountdownApiModels.Mutation mutation,
            List<Integer> reminders,
            boolean addToCalendar) {}

    private final CountdownActivity activity;
    private final CountdownApiModels.Countdown existing;
    private final Listener listener;
    private final BottomSheetDialog dialog;
    private final DialogCountdownEditorBinding binding;
    private LocalDate date;
    private LocalTime time;

    CountdownEditorDialog(
            CountdownActivity activity, CountdownApiModels.Countdown existing, Listener listener) {
        this.activity = activity;
        this.existing = existing;
        this.listener = listener;
        dialog = new BottomSheetDialog(activity);
        binding = DialogCountdownEditorBinding.inflate(activity.getLayoutInflater());
        dialog.setContentView(binding.getRoot());
        initialize();
    }

    void show() {
        dialog.setOnShowListener(ignored -> {
            BottomSheetBehavior<?> behavior = dialog.getBehavior();
            behavior.setSkipCollapsed(true);
            behavior.setState(BottomSheetBehavior.STATE_EXPANDED);
        });
        dialog.show();
    }

    private void initialize() {
        ZoneId zone = existingZone();
        ZonedDateTime target = existing == null
                ? ZonedDateTime.now(zone).plusDays(1).withSecond(0).withNano(0)
                : Instant.parse(existing.occursAt).atZone(zone);
        date = existing != null && existing.occursOn != null
                ? LocalDate.parse(existing.occursOn) : target.toLocalDate();
        time = target.toLocalTime();
        binding.editorHeading.setText(existing == null
                ? R.string.new_countdown_heading : R.string.edit_countdown);
        binding.titleInput.setText(existing == null ? "" : existing.title);
        binding.notesInput.setText(existing == null ? "" : existing.notes);
        binding.allDaySwitch.setChecked(existing != null && "all_day".equals(existing.timingKind));
        configureTimezones(zone);
        restoreReminders();
        refreshPickerLabels();
        bindActions();
    }

    private ZoneId existingZone() {
        try {
            return existing == null ? ZoneId.systemDefault() : ZoneId.of(existing.timezone);
        } catch (RuntimeException invalid) {
            return ZoneId.systemDefault();
        }
    }

    private void configureTimezones(ZoneId selected) {
        List<String> zones = new ArrayList<>(ZoneId.getAvailableZoneIds());
        zones.sort(Comparator.naturalOrder());
        binding.timezoneInput.setAdapter(new ArrayAdapter<>(
                activity, android.R.layout.simple_dropdown_item_1line, zones));
        binding.timezoneInput.setText(selected.getId(), false);
        binding.timezoneInput.setThreshold(0);
        binding.timezoneInput.setOnClickListener(view -> binding.timezoneInput.showDropDown());
    }

    private void restoreReminders() {
        List<Integer> values = existing == null ? List.of() : existing.reminderOffsets;
        binding.remindAtTime.setChecked(values.contains(0));
        binding.remindHour.setChecked(values.contains(60));
        binding.remindDay.setChecked(values.contains(1440));
        binding.remindWeek.setChecked(values.contains(10080));
    }

    private void bindActions() {
        binding.dateButton.setOnClickListener(ignored -> chooseDate());
        binding.timeButton.setOnClickListener(ignored -> chooseTime());
        binding.allDaySwitch.setOnCheckedChangeListener((button, checked) -> refreshPickerLabels());
        binding.saveButton.setOnClickListener(ignored -> submit(false));
        binding.saveCalendarButton.setOnClickListener(ignored -> submit(true));
        binding.deleteButton.setVisibility(existing == null ? View.GONE : View.VISIBLE);
        binding.deleteButton.setOnClickListener(ignored -> askToDelete());
    }

    private void chooseDate() {
        long selection = date.atStartOfDay(ZoneOffset.UTC).toInstant().toEpochMilli();
        MaterialDatePicker<Long> picker = MaterialDatePicker.Builder.datePicker()
                .setTitleText(R.string.choose_date)
                .setSelection(selection)
                .build();
        picker.addOnPositiveButtonClickListener(value -> {
            date = Instant.ofEpochMilli(value).atZone(ZoneOffset.UTC).toLocalDate();
            refreshPickerLabels();
        });
        picker.show(activity.getSupportFragmentManager(), "countdown-date");
    }

    private void chooseTime() {
        int format = android.text.format.DateFormat.is24HourFormat(activity)
                ? TimeFormat.CLOCK_24H : TimeFormat.CLOCK_12H;
        MaterialTimePicker picker = new MaterialTimePicker.Builder()
                .setTitleText(R.string.choose_time)
                .setTimeFormat(format)
                .setHour(time.getHour())
                .setMinute(time.getMinute())
                .build();
        picker.addOnPositiveButtonClickListener(value -> {
            time = LocalTime.of(picker.getHour(), picker.getMinute());
            refreshPickerLabels();
        });
        picker.show(activity.getSupportFragmentManager(), "countdown-time");
    }

    private void askToDelete() {
        if (existing == null) return;
        new MaterialAlertDialogBuilder(activity)
                .setTitle(activity.getString(
                        R.string.rc14_countdown_delete_title, existing.title))
                .setMessage(R.string.rc14_countdown_delete_message)
                .setNegativeButton(R.string.cancel, null)
                .setPositiveButton(R.string.rc14_delete_countdown, (ignored, which) -> {
                    dialog.dismiss();
                    listener.delete(existing);
                })
                .show();
    }

    private void refreshPickerLabels() {
        String dateLabel = date.format(DateTimeFormatter.ofLocalizedDate(FormatStyle.MEDIUM));
        String timeLabel = time.format(DateTimeFormatter.ofLocalizedTime(FormatStyle.SHORT));
        binding.dateButton.setText(dateLabel);
        binding.dateButton.setContentDescription(activity.getString(
                R.string.rc14_countdown_date_selected, dateLabel));
        binding.timeButton.setText(timeLabel);
        binding.timeButton.setContentDescription(activity.getString(
                R.string.rc14_countdown_time_selected, timeLabel));
        binding.timeButton.setVisibility(binding.allDaySwitch.isChecked() ? View.GONE : View.VISIBLE);
    }

    private void submit(boolean addToCalendar) {
        String title = String.valueOf(binding.titleInput.getText()).trim();
        binding.titleLayout.setError(null);
        binding.timezoneLayout.setError(null);
        if (title.isEmpty()) {
            binding.titleLayout.setError(activity.getString(
                    R.string.rc14_countdown_title_required));
            binding.titleInput.requestFocus();
            return;
        }
        ZoneId zone;
        try {
            zone = ZoneId.of(binding.timezoneInput.getText().toString().trim());
        } catch (RuntimeException invalid) {
            binding.timezoneLayout.setError(activity.getString(R.string.invalid_timezone));
            binding.timezoneInput.requestFocus();
            return;
        }
        boolean allDay = binding.allDaySwitch.isChecked();
        Instant target = date.atTime(allDay ? LocalTime.MIDNIGHT : time).atZone(zone).toInstant();
        CountdownApiModels.Mutation mutation = new CountdownApiModels.Mutation(
                UUID.randomUUID().toString(), title, target.toString(), zone.getId(),
                allDay ? "all_day" : "timed", allDay ? date.toString() : null,
                String.valueOf(binding.notesInput.getText()),
                existing == null ? null : existing.revision);
        dialog.dismiss();
        listener.save(new EditResult(mutation, reminders(), addToCalendar));
    }

    private List<Integer> reminders() {
        List<Integer> result = new ArrayList<>();
        if (binding.remindAtTime.isChecked()) result.add(0);
        if (binding.remindHour.isChecked()) result.add(60);
        if (binding.remindDay.isChecked()) result.add(1440);
        if (binding.remindWeek.isChecked()) result.add(10080);
        return List.copyOf(result);
    }
}
