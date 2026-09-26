# ADR 0024: Calendar-aware countdowns and transition alerts

- Status: accepted for RC13
- Date: 2026-09-13

## Context

The original countdown editor required people to type a UTC timestamp and IANA timezone. It did not distinguish an all-day moment from a timed event, reminders were not account-private, and calendar export had no explicit one-way boundary. Quiz polling also described only a final reveal, leaving daily availability and partner completion unclear.

## Decision

A countdown stores either a timed instant with its IANA timezone or an all-day local date. The server validates and canonicalizes both forms, keeps optimistic revisions and operation-ID idempotency, and returns upcoming and past moments. Each member owns a private set of reminder offsets from the fixed values 0, 60, 1,440, and 10,080 minutes. Android schedules those reminders locally, uses 9:00 AM in the event timezone for all-day moments, and reconciles them after sync, reboot, app replacement, clock change, or timezone change.

Android's date and time pickers create the canonical payload. **Add to calendar** launches `CalendarContract` with a prefilled event; it is a one-way user-approved copy, not a Google account integration or a synchronization promise. Calendar edits do not alter Little Orbit, and Little Orbit edits do not silently alter the calendar copy.

The existing per-installation notification ledger gains countdown-created, countdown-rescheduled, quiz-available, quiz-partner-finished, and quiz-results-ready event kinds. Countdown events are inserted in the same database transaction as the accepted mutation. Quiz completion transitions are locked and deduplicated. Daily availability is created lazily during an authorized pending-event fetch, and failure to prepare a quiz pool cannot block unrelated Smooch, note, or countdown delivery.

## Consequences

- Countdown entry follows familiar calendar controls while preserving explicit timezone behavior and offline retries.
- Reminder choices remain private to each account and notification posting remains local to each installation.
- Transition alerts carry only a countdown identifier/title or UTC quiz date; they never include countdown notes, quiz prompts, or answers.
- Local notification timing remains subject to Android and OEM background limits, and calendar copies may diverge after export.
