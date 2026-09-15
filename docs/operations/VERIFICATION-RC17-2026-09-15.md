# RC17 verification — 2026-09-15

## Scope and privacy-safe diagnosis

This record covers repeated Our Space document creation and an estimated nearby-time counter that remained at zero. The production inspection emitted counts, timestamps, revisions, lengths, and equality groups only. It did not print note text, titles, attachment names, coordinates, account identifiers, or partner identity.

The active couple has two mutually consented location members. The current 24-hour raw window held 208 samples from one phone and 101 from the other, but only eight samples from the first phone fell inside the other phone's seven-hour sampling span. Nine timestamp pairs were possible and none classified within the configured 100-metre threshold. The second phone stopped supplying samples many hours before diagnosis while the first continued. The old server incorrectly advanced `proximity_processed_through` from either stream, making this two-phone estimate appear current.

The note directory held five active documents. Four rows formed one exact-content equality group with four distinct create operation IDs. The original had 68 body revisions; three exact revision-zero copies appeared shortly after its final save, including two 1.5 seconds apart. This proves separate create mutations rather than duplicate card rendering. Content remained unread throughout the probe.

## Corrected invariants

- One new-document workspace retains one operation ID and permits only one create request in flight.
- Reopening the new-document action while that workspace is visible preserves the current workspace instead of resetting its identity.
- Under the current-couple lock, an exact active document updated within five minutes is returned for a second create ID. This bounded recovery protects older clients that lost identity immediately after a save.
- Signing in and starting a signed-in app re-arm the privacy-gated periodic location sampler. A foreground paired screen reconciles permission plus both server consent states and starts the visible sampler when allowed.
- Android may restart the visible sampler after reclaiming its process. Permission removal or either server opt-out still stops collection.
- Nearby freshness is the earlier of the two members' newest retained samples. A lone current stream cannot label the pair estimate current.
- User-facing together-time surfaces show the coordinate-free nearby estimate. The immutable pairing instant remains server metadata and does not masquerade as measured time spent nearby.

## Automated and artifact evidence

- `python infra/scripts/check_quality.py` passes all 397 source files.
- The focused API domain suite passes 12 tests. Ruff passes the changed API/tests and strict mypy passes the changed service modules.
- A fresh disposable PostgreSQL 17.6 database migrated through Alembic head `0024`; the partner-note integration passed and proved two distinct immediate create IDs yield one stored note and one partner-visible snapshot. The disposable container and database were removed.
- Android mobile and widget unit suites pass. Mobile and widget debug lint pass.
- Wear unit tests and debug lint pass after changing the launcher, tile, and complications to nearby-time-first text.
- The signed release build and release lint pass. Phone code 22 is 36,221,117 bytes with SHA-256 `2f74ffaf7c3ea3b5bf98095bec1f34034cbda33bd8e6fdab0b537a3d7cd6a819`; Wear code 17 is 14,189,898 bytes with SHA-256 `d594533bebab85921a075d009378c6183015754479acf059c78c646075e33b0a`. Both verify with certificate SHA-256 `43e83a420c7496ce9121339ab5bd6b01a6357161a83a95042ace56855bd89337`.

## Publication evidence

Publication and live endpoint evidence is appended after the immutable release record, containers, and public downloads are verified.

## Open physical gate

Neither physical phone nor the tablet was connected to ADB during this repair. RC17 therefore does not claim a live two-phone proximity interval. Both phones must install RC17 and produce two confident nearby pairs before the counter can rise; past gaps cannot be recreated without retained evidence. The complete two-phone, tablet, widget, Wear, battery, and permission gate remains open for 1.0.
