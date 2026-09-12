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

### Current Android implementation

![Implemented signed RC3 signed-out Android dashboard on an API 36 emulator](docs/assets/android-home-rc3-signed.png)

![Implemented RC3 More screen on an API 36 emulator](docs/assets/android-more-rc3.png)

The RC3 emulator captures verify the Inter type system, paired planet motif, lavender primary action, persistent Home/Quiz/Notes/More navigation, sparse signed-out states, and Wear update boundary. RC4 keeps that interface and changes the verified download transport. Feature forms share the same cosmic background, inset fields, and action styles. Portrait, large-text, updater installation, widget, and Wear OS captures remain part of the physical-device release gate.

## Public website

![Website landing page concept](docs/assets/web-landing-concept.png)

The website explains the mission, provides the signed APK and checksum, and hosts account and project pages. Relationship features remain in the Android app.

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

- [ ] Real phone: signed-out, pairing, daily question, both-answered reveal, countdown, notes conflict, together-time, privacy controls.
- [x] API 36 emulator: RC3 debug APK install, launch, signed-out dashboard and More hierarchy, landscape rendering, and runtime-crash check.
- [ ] Home widget: fresh, stale, signed-out, and server-offline states.
- [ ] Wear OS: tile, complication, loading, stale, and disconnected states.
- [x] Website baseline: desktop landing, mobile landing, signup, and owner login.
- [ ] Website remaining: recovery states, expanded mobile navigation, and dedicated accessibility views.
- [ ] Owner console: TOTP enrollment, health, AI batch review, user metadata, and redacted configuration.
- [ ] Two-device flow: pairing through unpair archive on physical phones.
- [ ] Updater: optional deferral, interrupted download recovery, corrupt APK rejection, Android install approval, and scheduled compatibility floor on a physical phone.
