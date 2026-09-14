package com.littleorbit.mobile;

import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.provider.CalendarContract;
import android.widget.Toast;
import com.littleorbit.data.remote.CountdownApiModels;
import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneId;

/** Sends a one-way prefilled event to the person's chosen calendar application. */
final class CountdownCalendarExporter {
    private CountdownCalendarExporter() {}

    static void open(CountdownActivity activity, CountdownApiModels.Countdown value) {
        ZoneId zone = ZoneId.of(value.timezone);
        boolean allDay = "all_day".equals(value.timingKind) && value.occursOn != null;
        LocalDate calendarDate = allDay ? LocalDate.parse(value.occursOn) : null;
        long begin = allDay
                ? calendarDate.atStartOfDay(zone).toInstant().toEpochMilli()
                : Instant.parse(value.occursAt).toEpochMilli();
        long end = allDay
                ? calendarDate.plusDays(1).atStartOfDay(zone).toInstant().toEpochMilli()
                : begin + 3_600_000L;
        Intent intent = new Intent(Intent.ACTION_INSERT, CalendarContract.Events.CONTENT_URI)
                .putExtra(CalendarContract.Events.TITLE, value.title)
                .putExtra(CalendarContract.Events.DESCRIPTION, value.notes)
                .putExtra(CalendarContract.Events.EVENT_TIMEZONE, value.timezone)
                .putExtra(CalendarContract.EXTRA_EVENT_BEGIN_TIME, begin)
                .putExtra(CalendarContract.EXTRA_EVENT_END_TIME, end)
                .putExtra(CalendarContract.EXTRA_EVENT_ALL_DAY, allDay);
        try {
            activity.startActivity(intent);
        } catch (ActivityNotFoundException missing) {
            Toast.makeText(activity, R.string.calendar_app_missing, Toast.LENGTH_LONG).show();
        }
    }
}
