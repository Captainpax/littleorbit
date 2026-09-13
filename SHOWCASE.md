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

### Current Android implementation

![Implemented signed-out RC8 home on an API 36 emulator](docs/assets/android-home-rc8-emulator.png)

![Implemented signed RC3 signed-out Android dashboard on an API 36 emulator](docs/assets/android-home-rc3-signed.png)

![Implemented RC3 More screen on an API 36 emulator](docs/assets/android-more-rc3.png)

The RC8 API 36 emulator capture verifies the refreshed signed-out planet hierarchy, action treatment, icon navigation, and status/navigation-bar insets. The earlier RC3 captures preserve the first implemented Inter type system, persistent navigation, More hierarchy, and Wear update boundary. RC4 changed the verified download transport and RC5 brought the daily quiz into the same visual system. RC6 separated relationship age and nearby-time, added guided device setup, and refreshed the widget, tile, and complication cache contract. RC9 gives a revealed quiz a fixed action above navigation, moves widget rendering into lifecycle-safe background work, and adds an inset-safe crop screen. RC10 derives relationship age from pairing, places Smooches at the center spark and in More, turns Notes into a titled workspace with presence and archive recovery, and keeps update availability visible after a one-time optional prompt. RC10.1 physically verifies phone-hosted pairing, remembered reconnect, and session-based installation on a Pixel 8 Pro and Pixel Watch 3. Paired two-phone and live-data captures still remain open.

![Signed RC7 Wear OS fallback state on a round Wear OS 5 emulator](docs/assets/wear-rc7-signed-emulator.png)

The signed RC7 Wear launcher capture verifies that the logo, relationship date fallback, nearby estimate, and stale status fit the round safe area. Its content remains scrollable for large text and smaller displays.

RC8 adds synchronized, app-private couple thumbnails to the Wear launcher with styled initials as the fallback. Tile and complication surfaces remain text-only to keep their cache small and avoid putting faces on passive watch surfaces. The phone's More tab opens a guided installer that downloads and verifies the Wear APK, discovers wireless-debugging endpoints, pairs with the short-lived watch code, remembers the ADB identity in encrypted storage, and asks before proceeding on an old security patch. RC10.1 follows continuously updated service information, proves Kadb's lazy connection with an authenticated command, uses public Conscrypt APIs on Android 17, and commits the APK through a package session.

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
- [x] Pixel 8 Pro to Pixel Watch 3: fresh wireless-debug pairing, desktop authorization cleanup, encrypted phone authorization retention, two remembered reconnects, two package-session installs, Wear launcher render, and no fatal Android runtime event. This used a local diagnostic build only to accept RC10's known Wear metadata mismatch; strict RC10.1 still requires post-publication validation.
- [ ] Real phone follow-up: two-phone profile sync/removal, notification/location setup, pairing, Smooch send/receive/history, focused daily-question entry/review/wait, countdown, multi-note conflict/archive/undo, automatic pair age, nearby-time, and privacy controls.
- [x] API 36 emulator: signed RC8 install, cold launch, signed-out home hierarchy, status/navigation-bar insets, and accessibility-tree dump.
- [ ] Home widget: fresh, stale, signed-out, and server-offline states.
- [ ] Wear OS: in-app wireless install, remembered authorization, old-patch warning, profile-photo sync, phone capability detection, tile, complication, loading, stale, and disconnected states.
- [x] Wear OS 5 round emulator: signed RC7 install, cold launch, safe-area fallback layout, and stale-state rendering.
- [x] Website baseline: desktop landing, mobile landing, signup, and owner login.
- [ ] Website remaining: patch notes/RSS in a feed reader, recovery states, expanded mobile navigation, and dedicated accessibility views.
- [ ] Owner console: TOTP enrollment, health, AI batch review, user metadata, and redacted configuration.
- [ ] Two-device flow: pairing through unpair archive on physical phones.
- [ ] Updater: first-launch opt-in, once-per-process prompt, six-hour discovery, optional deferral, stalled/interrupted recovery, corrupt APK rejection, Android install approval, and scheduled compatibility floor on a physical phone.
