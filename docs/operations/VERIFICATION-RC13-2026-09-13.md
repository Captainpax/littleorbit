# RC13 verification — 2026-09-13

This record covers calendar-aware countdowns, private reminders, countdown and quiz transition notifications, generated-question whitespace validation, partner-assigned relationship avatars, migration `0016`, the Android compatibility matrix, and signed RC13 publication. Disposable smoke accounts and synthetic images were used unless a physical-device step is named explicitly.

## Automated and contract gates

- Ruff passed and strict mypy passed for 109 Python source and test files.
- Pytest passed all 104 API and AI tests. The only warning is Starlette's upstream `BlockingPortal` alias deprecation.
- Android phone and Wear unit tests and debug lint passed. Phone release lint-vital, assembly, and Android v3 signature verification passed.
- Web ESLint, strict TypeScript, 28 Vitest tests, and the 22-route production build passed.
- Versioned countdown and expanded notification JSON Schemas have valid and invalid fixtures consumed by Python, TypeScript, and Java contract tests.
- Migration `0016` was upgraded, downgraded to `0015` with RC13 notification rows present, and upgraded again in the isolated stack. The downgrade removes newer event kinds before restoring the older database constraint.

## Countdown, notification, avatar, and AI evidence

- The isolated two-account integration smoke created and rescheduled a timed countdown, observed independent partner events, acknowledged one random installation, and proved each account sees only its own reminder offsets.
- Countdown tests cover timed/all-day field combinations, invalid IANA timezones, operation replay, optimistic revision conflicts, all-day canonicalization, reminder allow-listing, privacy, and account/couple cleanup.
- Android reminder tests cover fixed offsets, all-day 9:00 AM event-time scheduling, timed moments, and expired alarms. The app reconciles after sync, reboot, app replacement, clock changes, and timezone changes.
- A missing daily quiz pool is contained in a nested transaction. Its 503 suppresses only the unavailable quiz alert; unrelated pending countdown, note, and Smooch events remain fetchable.
- Notification contracts and tests cover countdown-created, countdown-rescheduled, quiz-available, quiz-partner-finished, and quiz-results-ready metadata without countdown notes, quiz prompts, or answers.
- A synthetic PNG assigned by account A appeared as account B's read-only avatar relationship state. The legacy self-photo write returned HTTP 410, and database/service checks reject subject/assigner equality. Unpair and account deletion remove relationship avatar rows.
- AI safety fixtures reject tabs, line breaks, control characters, non-breaking spaces, repeated spaces, and leading/trailing whitespace rather than silently rewriting generated visible text.

## Android compatibility and visual evidence

- API 29, API 30, and API 36 phone emulators passed fresh install, app-data reset, paired sign-in, Home, drawer, Our Space, Markdown dock, and sanitized attachment smoke using both disposable partners across the matrix.
- Opening Countdowns on API 29 with the pre-fix stale smoke artifact reproduced `NoSuchMethodError: Stream.toList`. Replacing the API 34 Java library call, rebuilding the APK, and reopening the same route eliminated the crash. The expanded editor exposed title, all-day switch, date, time, timezone, all reminder chips, notes, and both save actions.
- The wide API 36 tablet rendered the next-moment hero, upcoming list, static navigation rail, and fully expanded countdown editor without clipping. Screenshots are stored in `docs/assets/` and labeled as emulator evidence.
- The API 36 phone rendered the signed-in person's avatar as read-only and exposed choose/crop/remove controls only for the partner's avatar.
- The independently versioned Wear code 15 companion installed and launched on the round API 34 emulator, showing paired initials, relationship-age fallback, nearby estimate, and an explicit stale/open-phone state. RC13 changes no Wear source behavior.
- The smoke automation itself was repaired after Android autofill restored an older disposable email on API 36; it now clears both login fields before typing, preventing false authentication failures in future matrices.

## Production migration and signed release

- PostgreSQL backup `little-orbit-20260913-193750.dump` and attachment snapshot `little-orbit-attachments-20260913-193756.files` completed before container replacement and migration.
- Production applied migration `0016` transactionally. API, web, gateway, PostgreSQL, ClamAV, and Ollama reported healthy; worker and media worker remained running. Only gateway port 8180 is host-bound.
- Phone: version `1.0.0-rc.13`, code 18, 35,973,846 bytes, SHA-256 `951b9194f57c0daec8b7ddfd6aeebd487a6a3b4cea1eeed19a4157ab7527d8ef`.
- Wear: unchanged independent version code 15, 14,133,466 bytes, SHA-256 `9227bbb70ecf127a36a70d3f33101938df35f4b4cf62d80b71ff4a653a1c1868`.
- Both APKs use signing certificate SHA-256 `43e83a420c7496ce9121339ab5bd6b01a6357161a83a95042ace56855bd89337` and pass Android v3 verification.
- Public metadata reports RC13, phone code 18, Wear code 15, minimum phone API 29, compatibility floor 6, and no new enforcement time. Fresh complete downloads reproduce both manifest hashes. A 1,024-byte phone request returns HTTP 206 with `Content-Range: bytes 0-1023/35973846`.
- `/download`, `/patch-notes`, `/patch-notes.xml`, and `/showcase` return HTTP 200; RSS uses `application/rss+xml`.

## Open gates

- Countdown and quiz notification timing, Android channel overrides, generic lock-screen rendering, process kill, OEM battery behavior, and independent delivery still need a two-physical-phone run.
- The actual installed calendar-provider flow, daylight-saving transitions on a physical phone, and reminder timing through reboot remain open physical-device checks.
- Partner-avatar crop, replacement, removal, Wear transfer, and unpair cleanup remain open across two physical phones and the physical watch.
- No physical phone was connected during this RC13 run. The complete phone/watch installer, tile, complication, battery, background location, destructive restore, DHCP reservation, privacy/permission, and legal gates remain open. RC13 is a prerelease rather than the 1.0 general release.
