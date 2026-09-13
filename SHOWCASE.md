# Little Orbit showcase

These concepts define the 1.0 visual target. Product screenshots will replace or sit beside them as screens become release-ready.

## Identity

![Little Orbit logo: two linked orbital hearts](docs/assets/little-orbit-logo-concept.png)

The two linked orbits communicate two independent people choosing a shared path. Deep navy provides a calm base, coral marks warmth and action, and soft lavender supports quieter surfaces.

## Android, widget, and Wear OS

![Phone dashboard, quiz, notes, widget and Wear OS concepts](docs/assets/android-wear-concept.png)

The dashboard leads with the relationship rather than system controls. Daily questions, countdowns, and notes use spacious cards. Widgets and watch surfaces show cached together-time and the next countdown, with a visible stale marker when refresh is overdue.

![Updater and More screen concept](docs/assets/android-update-more-concept.png)

The companion study defines the updater and settings direction: the same planet motif, a visible verification step, calm progress language, and one More destination for pairing, privacy, archives, and app updates. RC4 moves the actual APK transfer to Little Orbit's resumable first-party endpoint.

![Generated RC5 quiz flow concept showing focused questions, partner guessing, private waiting, and shared reveal](docs/assets/android-quiz-rc5-concept.png)

This generated RC5 design study is the visual target for daily questions. The implementation uses one focused card, five progress segments, question-specific controls, private drafts, an explicit Review and Finish step, and a calm side-by-side reveal. Partner guessing records each person's own choice and guess, then celebrates a match without points or rankings.

![RC11 Our Space concept showing the document library, Markdown editor, attachment tray, preview, and conflict recovery](docs/assets/android-our-space-rc11-concept.png)

RC11 makes shared notes feel like a small couple library. The library leads with search and recent documents; opening one moves into a focused Edit/Preview workspace. Formatting helpers insert ordinary Markdown, attachments sit beside their reference at the cursor, and concurrent changes preserve both versions when automatic reconciliation is unsafe.

![RC11 Smooch concept showing the centered tab, emoji picker, orbit pulse, weekly total, and history](docs/assets/android-smooches-rc11-concept.png)

Smooches now have their own centered destination. The primary screen keeps the selected emoji and partner at the center, shows the remaining rolling-hour allowance before sending, and turns successful delivery into a warm orbit pulse. Weekly memories use shared totals and emoji distribution without rankings.

![RC12 application-shell concept with a left destination drawer and a private recent-activity panel](docs/assets/android-shell-rc12-concept.png)

RC12 gives the whole app one predictable shell. A phone opens the complete destination list from the left, a wide tablet keeps the same list visible as a rail, and the right control opens actions and recent context for the current screen. Home's panel uses content-free event metadata and a private per-person seen position.

![RC12 Our Space editor concept with a calm Markdown dock and contextual note directory](docs/assets/android-space-editor-rc12-concept.png)

The RC12 editor keeps the most common formatting actions in a compact dock directly above the keyboard. Less frequent Markdown structures live in the overflow menu. The right panel searches or switches documents without leaving the current editor, while attachments remain explicit cards with Insert, Preview, Delete, and Keep offline actions.

![Implemented RC12.1 preview-first document with verified inline PNG and animated GIF](docs/assets/android-space-preview-rc12-1-emulator.png)

RC12.1 opens existing documents in preview and uses one Edit/Done editing action. Authorized private images appear at their Markdown position only after download size and digest verification; the emulator capture shows the PNG and one frame of the sanitized animated GIF. Account-synced notification controls now cover Smooches, document editing, quizzes, countdowns, and weekly summaries, while Android permission and channels remain visible per phone.

### Current Android implementation

![Implemented signed-out RC8 home on an API 36 emulator](docs/assets/android-home-rc8-emulator.png)

![Implemented RC12 paired Home on an API 36 emulator](docs/assets/android-home-rc12-emulator.png)

![Implemented RC12 complete left navigation on an API 36 emulator](docs/assets/android-navigation-rc12-emulator.png)

![Implemented RC12 Markdown dock above the Android keyboard](docs/assets/android-space-rc12-emulator.png)

![Implemented signed RC3 signed-out Android dashboard on an API 36 emulator](docs/assets/android-home-rc3-signed.png)

![Implemented RC3 More screen on an API 36 emulator](docs/assets/android-more-rc3.png)

The RC12 captures verify the paired Home hierarchy, complete left navigation, absence of bottom tabs, and keyboard-adjacent Markdown dock. The same isolated couple passed the Our Space and attachment smoke flow on API 29, API 30, API 36 phone, and a wide API 36 tablet. The tablet uses a static rail so visible navigation never blocks content touches. RC12 also adds the screen-specific right panel and a 30-day privacy-minimized activity view. Paired physical-phone and live-data captures remain open.

![Signed RC7 Wear OS fallback state on a round Wear OS 5 emulator](docs/assets/wear-rc7-signed-emulator.png)

![RC12 Wear fallback state on a round API 34 emulator](docs/assets/wear-rc12-emulator.png)

The signed RC7 Wear launcher capture verifies that the logo, relationship date fallback, nearby estimate, and stale status fit the round safe area. Its content remains scrollable for large text and smaller displays.

RC8 adds synchronized, app-private couple thumbnails to the Wear launcher with styled initials as the fallback. Tile and complication surfaces remain text-only to keep their cache small and avoid putting faces on passive watch surfaces. The phone's Settings destination opens a guided installer that downloads and verifies the Wear APK, discovers wireless-debugging endpoints, pairs with the short-lived watch code, remembers the ADB identity in encrypted storage, and asks before proceeding on an old security patch. RC10.1 follows continuously updated service information, proves Kadb's lazy connection with an authenticated command, uses public Conscrypt APIs on Android 17, and commits the APK through a package session.

## Public website

![Website landing page concept](docs/assets/web-landing-concept.png)

The website explains the mission, provides the signed APK and checksum, and hosts account and project pages. Its patch-notes page and RSS feed are generated from immutable public release records. Relationship features remain in the Android app.

### Current implementation

![Implemented desktop landing page](docs/assets/site-home-desktop.png)

![Implemented mobile landing page](docs/assets/site-home-mobile.png)

![Implemented registration page](docs/assets/site-signup.png)

![Implemented owner MFA login](docs/assets/site-admin-login.png)

Regenerate these images from the running gateway with `npm --prefix apps/web run capture:showcase`. The capture command fails on HTTP or browser-console errors.

## Owner console

![Privacy-limited owner console concept](docs/assets/admin-console-concept.png)

The console exposes service health, delivery and generation status, moderation queues, and account metadata. It deliberately has no viewer for notes, answers, precise locations, or exports.

## Screenshot checklist

- [x] Real Pixel 8 Pro: signed RC9 upgrade with retained account data, revealed-quiz Done return, profile crop approval/upload, and no new widget or Android runtime crash after the reproduced RC8 failure.
- [x] Real Pixel 8 Pro: signed RC10 upgrade with retained pairing, Home/More rendering, automatic pair age, Smooch entry points, update-detection state, and a visible foreground location service whose first cycle reached the API.
- [x] Pixel 8 Pro to Pixel Watch 3: fresh wireless-debug pairing, desktop authorization cleanup, encrypted phone authorization retention, package-session installs, Wear launcher render, and no fatal Android runtime event. The published strict RC10.1 phone build upgraded the watch from RC10's actual code 9 to code 10, then reconnected without another pairing code and reported the watch current.
- [ ] Real phone follow-up: two-phone profile sync/removal, notification/location setup, pairing, Smooch send/receive/history, focused daily-question entry/review/wait, countdown, multi-note conflict/archive/undo, automatic pair age, nearby-time, and privacy controls.
- [x] API 36 emulator: signed RC8 install, cold launch, signed-out home hierarchy, status/navigation-bar insets, and accessibility-tree dump.
- [x] RC12 isolated emulator matrix: paired-account Home, left navigation, Our Space, Markdown dock, transparent PNG/GIF availability, API 29, API 30, API 36 phone, and API 36 wide tablet.
- [x] RC12 API 36 phone: dynamic Notes panel opened from the right and an authorized sanitized PNG downloaded, passed digest verification, and rendered in-app.
- [x] RC12.1 API 36 phone: preview-first document rendered an authorized PNG inline and visibly advanced a sanitized GIF between frames; Edit/Done editing state changed correctly.
- [x] RC12.1 compatibility matrix: both disposable partners passed Home, drawer/rail, Our Space, preview/editor, Markdown dock, and attachment checks on API 29, API 30, API 36 phone, and API 36 tablet.
- [ ] Home widget: fresh, stale, signed-out, and server-offline states.
- [ ] Wear OS: in-app wireless install, remembered authorization, old-patch warning, profile-photo sync, phone capability detection, tile, complication, loading, stale, and disconnected states.
- [x] Wear OS 5 round emulator: signed RC7 install, cold launch, safe-area fallback layout, and stale-state rendering.
- [x] Wear API 34 round emulator: RC12 package launch, pairing-date fallback, nearby estimate, and explicit stale/open-phone state with no fatal runtime event.
- [x] Website baseline: desktop landing, mobile landing, signup, and owner login.
- [ ] Website remaining: patch notes/RSS in a feed reader, recovery states, expanded mobile navigation, and dedicated accessibility views.
- [ ] Owner console: TOTP enrollment, health, AI batch review, user metadata, and redacted configuration.
- [ ] Two-device flow: pairing through unpair archive on physical phones.
- [ ] Updater: first-launch opt-in, once-per-process prompt, six-hour discovery, optional deferral, stalled/interrupted recovery, corrupt APK rejection, Android install approval, and scheduled compatibility floor on a physical phone.
- [ ] Our Space on two phones: cursor stability during acknowledgements, simultaneous emoji edits, reconnect, explicit conflict choices, attachment scan/rejection, offline preview, delete, archive purge, and quota boundaries.
