# Little Orbit showcase

These concepts define the 1.0 visual target. Product screenshots will replace or sit beside them as screens become release-ready.

## Identity

![Little Orbit logo: two linked orbital hearts](docs/assets/little-orbit-logo-concept.png)

The two linked orbits communicate two independent people choosing a shared path. Deep navy provides a calm base, coral marks warmth and action, and soft lavender supports quieter surfaces.

## Android, widget, and Wear OS

### 1.1.1 watch-hardening concepts

![1.1.1 phone Watch settings concept](docs/assets/watch-settings-concept-1.1.1.png)

![1.1.1 five-step Wear installer concept](docs/assets/wear-installer-concept-1.1.1.png)

![1.1.1 round-watch destinations and state concept](docs/assets/wear-destinations-concept-1.1.1.png)

These three generated sheets are design concepts, not production screenshots. They define the 1.1.1 hierarchy, cosmic navy/lavender/coral language, explicit installer progress and recovery, round-screen safe areas, and the separation between passive relationship information and deliberate actions. Device captures remain release-gate evidence rather than being represented by these images.

![Phone dashboard, quiz, notes, widget and Wear OS concepts](docs/assets/android-wear-concept.png)

The dashboard leads with the relationship rather than system controls. Daily questions, countdowns, and notes use spacious cards. Widgets and watch surfaces show cached together-time and the next countdown, with a visible stale marker when refresh is overdue.

![RC13 countdown concept showing a next-moment orbit, upcoming moments, and a calendar-style editor](docs/assets/android-countdowns-rc13-concept.png)

RC13 replaces timestamp entry with a calm moment timeline. Timed and all-day events use familiar pickers, each partner chooses private reminders, past moments stay available behind an explicit control, and Android calendar export remains a one-way copy that the person approves.

![Updater and More screen concept](docs/assets/android-update-more-concept.png)

This early companion study established the updater and settings language: the same planet motif, a visible verification step, and calm progress wording. The current shell gives Settings and App updates their own selected destinations, while RC4 moved APK transfer to Little Orbit's resumable first-party endpoint.

![Generated RC5 quiz flow concept showing focused questions, partner guessing, private waiting, and shared reveal](docs/assets/android-quiz-rc5-concept.png)

This generated RC5 design study is the visual target for daily questions. The implementation uses one focused card, five progress segments, question-specific controls, private drafts, an explicit Review and Finish step, and a calm side-by-side reveal. Partner guessing records each person's own choice and guess, then celebrates a match without points or rankings.

![RC11 Our Space concept showing the document library, Markdown editor, attachment tray, preview, and conflict recovery](docs/assets/android-our-space-rc11-concept.png)

RC11 makes shared notes feel like a small couple library. The library leads with search and recent documents; opening one moves into a focused Edit/Preview workspace. Formatting helpers insert ordinary Markdown, attachments sit beside their reference at the cursor, and concurrent changes preserve both versions when automatic reconciliation is unsafe.

![RC11 Smooch concept showing the centered tab, emoji picker, orbit pulse, weekly total, and history](docs/assets/android-smooches-rc11-concept.png)

Smooches now have their own centered destination. The primary screen keeps the selected emoji and partner at the center, shows the remaining rolling-hour allowance before sending, and turns successful delivery into a warm orbit pulse. Weekly memories use shared totals and emoji distribution without rankings.

![RC12 application-shell concept with a left destination drawer and a private recent-activity panel](docs/assets/android-shell-rc12-concept.png)

RC12 gives the whole app one predictable shell. A phone opens the complete destination list from the hamburger or a deliberate left-edge swipe, a wide tablet keeps the same list visible in a bounded rail, and the right control appears only when the current screen has actions or recent context. The selected destination remains visible, guest navigation exposes only public routes, and Home's panel uses content-free event metadata with a private per-person seen position.

![RC12 Our Space editor concept with a calm Markdown dock and contextual note directory](docs/assets/android-space-editor-rc12-concept.png)

The RC12 editor keeps the most common formatting actions in a compact dock directly above the keyboard. Less frequent Markdown structures live in the overflow menu. The right panel searches or switches documents without leaving the current editor, while attachments remain explicit cards with Insert, Preview, Delete, and Keep offline actions.

![Implemented RC12.1 preview-first document with verified inline PNG and animated GIF](docs/assets/android-space-preview-rc12-1-emulator.png)

RC12.1 opens existing documents in preview and uses one Edit/Preview action. Authorized private images appear at their Markdown position only after download size and digest verification; the emulator capture shows the PNG and one frame of the sanitized animated GIF. RC14 keeps the current selection stable during live patches, restores an interrupted workspace from encrypted app storage, refreshes the visible library so a partner's new document appears promptly, and closes the editor only for the exact inactive-relationship response. Account-synced notification controls cover Smooches, document creation and editing, quizzes, countdowns, and weekly summaries, while Android permission and channels remain visible per phone.

### Current Android implementation

![Implemented RC13 countdown timeline on a wide API 36 emulator](docs/assets/android-countdowns-rc13-tablet.png)

![Implemented RC13 expanded countdown editor with timed/all-day controls and private reminders](docs/assets/android-countdown-editor-rc13-tablet.png)

![Implemented RC13 partner-assigned avatar screen on an API 36 phone emulator](docs/assets/android-profile-rc13-emulator.png)

The RC13 captures verify that countdowns use the shared responsive shell, keep the next moment prominent, and expose calendar-style controls without typed UTC values. The profile screen makes the ownership rule visible: your own avatar is read-only and only your partner's card has choose, crop, and remove actions.

![Implemented signed-out RC8 home on an API 36 emulator](docs/assets/android-home-rc8-emulator.png)

![Implemented RC12 paired Home on an API 36 emulator](docs/assets/android-home-rc12-emulator.png)

![RC16 expired-session recovery on an API 36 emulator](docs/assets/android-session-expired-rc16-emulator.png)

![Implemented RC12 complete left navigation on an API 36 emulator](docs/assets/android-navigation-rc12-emulator.png)

![Implemented RC12 Markdown dock above the Android keyboard](docs/assets/android-space-rc12-emulator.png)

![Implemented signed RC3 signed-out Android dashboard on an API 36 emulator](docs/assets/android-home-rc3-signed.png)

![Implemented RC3 More screen on an API 36 emulator](docs/assets/android-more-rc3.png)

The RC12 captures verify the paired Home hierarchy, complete left navigation, absence of bottom tabs, and keyboard-adjacent Markdown dock. The same isolated couple passed the Our Space and attachment smoke flow on API 29, API 30, API 36 phone, and a wide API 36 tablet. The tablet uses a static rail so visible navigation never blocks content touches. RC12 also adds the screen-specific right panel and a 30-day privacy-minimized activity view. RC16 removes the Home checklist once pairing, notifications, nearby time, and the widget are ready; Settings retains every setup entry, and Pairing & relationship shows the archive-preserving unpair action only for an active couple. The RC16 capture verifies that a revoked disposable session clears cached partner identity and returns to an honest sign-in action rather than presenting a false half-paired state. RC17 keeps this shell and changes its together-time card, widget, and Wear surfaces to lead with the estimated nearby duration; it also prevents repeated create/save actions from adding another document card.

The 1.0 Together Time detail is deliberately different from relationship age. A large timer shows observed nearby hours, minutes, and seconds, while a separate state explains whether both phones currently provide nearby, confirming, apart, inaccurate, waiting, or stale evidence. Only the foreground phone detail may animate a bounded provisional value, and it stops at the server deadline. Home, widget, tile, and complication remain on the authoritative observed value with a freshness label. A paired physical 1.0 capture remains open.

![1.0.1 Together Time dashboard concept with collection health and evidence timeline](docs/assets/together-time-1.0.1-concept.png)

The approved 1.0.1 concept separates the durable total, current counting state, per-phone collection health, and coordinate-free weekly evidence. **Fix counting** exposes direct Android settings without pretending same Wi-Fi proves proximity. Daily details distinguish observed time, later-confirmed bridges, gaps, apart readings, poor accuracy, and disabled collection. This image is concept art; implemented-device captures remain part of the release gate.

![1.0.1 Our Space autosave and offline-conflict concept](docs/assets/our-space-1.0.1-concept.png)

The 1.0.1 Our Space concept removes the ordinary Save action. A small status communicates saving, recent success, device-only offline storage, or review required. When a newer shared revision meets an offline draft, the editor stops and offers review/merge, an idempotent copy with remapped attachments, or the shared version. This image is concept art pending the physical paired-device capture.

![Signed RC7 Wear OS fallback state on a round Wear OS 5 emulator](docs/assets/wear-rc7-signed-emulator.png)

![RC12 Wear fallback state on a round API 34 emulator](docs/assets/wear-rc12-emulator.png)

![RC13 compatibility launch of the unchanged Wear companion on a round API 34 emulator](docs/assets/wear-rc13-emulator.png)

The signed RC7 Wear launcher capture verifies that the logo, relationship date fallback, nearby estimate, and stale status fit the round safe area. Its content remains scrollable for large text and smaller displays.

RC8 adds synchronized, app-private couple thumbnails to the Wear launcher with styled initials as the fallback. Tile and complication surfaces remain text-only to keep their cache small and avoid putting faces on passive watch surfaces. The phone's Settings destination opens a guided installer that downloads and verifies the Wear APK, discovers wireless-debugging endpoints, pairs with the short-lived watch code, remembers the ADB identity in encrypted storage, and asks before proceeding on an old security patch. RC10.1 follows continuously updated service information, proves Kadb's lazy connection with an authenticated command, uses public Conscrypt APIs on Android 17, and commits the APK through a package session.

The RC14 implementation scopes passive records to an opaque relationship generation. Sign-out, unpair, deletion, and an inactive-relationship response publish an urgent purge that wins over delayed records. A disconnected watch keeps the six-hour stale state, then deletes display values, names, thumbnails, and partial files at 24 hours and shows a simple open-phone prompt. The home widget selects a compact, one-glance layout below 180 dp and keeps a 48 dp countdown action while expanded widgets retain the complete card. The installer keeps typed manual endpoints stable while discovery continues, never saves or autofills the pairing code, offers signed-artifact retry, and still detects current, incompatible, and downgrade states before install.

The RC14 visual pass keeps each shell destination to one title, lets Home cards grow under large text, and uses the same lavender, coral, amber, deep-navy, 24 dp card language across Home, Quiz, Countdowns, and private archives. Form fields now declare meaningful keyboard and autofill behavior, archive and quiz-history dates follow the device locale, passive widget labels remain readable at Android's minimum text guidance, and Android 13 launchers receive a purpose-built monochrome orbit mark. The Wear tile picker now shows representative square and round previews, while launcher, tile, and complication wording comes from localized resources.

The signed 1.1.0 implementation adds a dedicated phone Watch settings page rather than overloading the main Settings list. One explicitly selected watch receives target-scoped content. The page controls profile photos, countdown titles, watch Smooches, update alerts, and the default watch destination, and it exposes install/update, repair, diagnostics, and private removal. All switches default on only after explicit watch selection.

Wear code 19 uses vertically scrolling Together, Countdown, and Smooch activities instead of a horizontal carousel. Countdown preserves timed versus all-day timezone semantics. Smooch uses only the nine approved choices, requires a confirmation screen, and queues at most five encrypted actions for 15 minutes without holding a phone account token. Tile and watch-face surfaces remain passive; Nearby and Countdown are separate complications and Smooch is never offered as a passive action. These remain implementation descriptions rather than physical-device captures; the owner approved release with the 1.1.0 round-watch capture checklist still open.

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
- [x] RC13 compatibility matrix: API 29, API 30, and API 36 phones passed fresh paired-account smoke; the API 29 countdown crash was reproduced with the stale artifact and eliminated after the compatibility fix. The wide API 36 tablet verified the timeline and expanded editor, API 36 verified partner-only avatar controls, and the unchanged Wear code 15 companion launched on the round API 34 emulator.
- [ ] Home widget: fresh, stale, signed-out, and server-offline states.
- [ ] Wear OS: in-app wireless install, remembered authorization, old-patch warning, profile-photo sync, phone capability detection, tile, complication, loading, stale, and disconnected states.
- [x] Wear OS 5 round emulator: signed RC7 install, cold launch, safe-area fallback layout, and stale-state rendering.
- [x] Wear API 34 round emulator: RC12 package launch, pairing-date fallback, nearby estimate, and explicit stale/open-phone state with no fatal runtime event.
- [x] RC14 Wear API 34 round emulator: synthetic fresh, six-hour stale, unavailable, and 24-hour expiry states; expiry removed names, thumbnails, and interrupted thumbnail files, and 150% text remained reachable by scrolling.
- [x] RC14 paired-note regression: partner B listed partner A's document and sanitized attachments, bidirectional live edits converged through a disconnect, and a document created while partner B remained in the library appeared automatically inside the foreground refresh window.
- [x] RC16 API 36 regression: a paired account opened the shared-note directory and verified inline attachments; after its server session was revoked, cold launch removed the encrypted token and profile thumbnails and rendered signed out without a crash.
- [x] RC16 physical Pixel check: an in-place code-21 upgrade preserved the valid session, hid the completed Home setup card, and showed the connected-only unpair action without executing it against the real couple.
- [x] RC17 isolated data check: four identical visible cards were proved to be distinct create rows without reading their title/body, and a disposable PostgreSQL run proved different immediate create IDs now resolve to one partner-visible document.
- [ ] RC17 physical pair: install code 22 on both phones, confirm one save remains one document, collect two confident nearby pairs, and capture the nearby-only Home/widget/Wear presentation.
- [ ] 1.0.1 physical pair: the owner waived this unavailable tablet gate for publication. A future paired-device soak should still cover foreground and screen-off collection through Wi-Fi/cellular/offline transitions and a forced 15-minute gap followed by confirmation.
- [x] Website baseline: desktop landing, mobile landing, signup, and owner login.
- [ ] Website remaining: patch notes/RSS in a feed reader, recovery states, expanded mobile navigation, and dedicated accessibility views.
- [ ] Owner console: TOTP enrollment, health, AI batch review, user metadata, and redacted configuration.
- [ ] Two-device flow: pairing through unpair archive on physical phones.
- [ ] Updater: first-launch opt-in, once-per-process prompt, six-hour discovery, optional deferral, stalled/interrupted recovery, corrupt APK rejection, Android install approval, and scheduled compatibility floor on a physical phone.
- [ ] Our Space on two phones: cursor stability during acknowledgements, simultaneous emoji edits, reconnect, explicit conflict choices, attachment scan/rejection, offline preview, delete, archive purge, and quota boundaries.
