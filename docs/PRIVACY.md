# Privacy design

Little Orbit is designed around two people sharing deliberately. It does not sell personal data, display advertising, or use relationship activity to train or personalize AI. The 1.0 AI pipeline creates the same calendar-based question pool for the service and receives no user data.

This document describes the intended 1.0 behavior while the project is under development. A production privacy notice and legal review are release gates.

## Data and purpose

| Data | Purpose | Access | Intended retention |
|---|---|---|---|
| Email, password hash, verification state | Account access and recovery | Account owner; limited admin metadata | Until deletion plus bounded backup expiry |
| Session identifiers and security events | Authentication and abuse response | Account owner sessions; privacy-limited admins | App sessions expire after 30 days; admin sessions after 30 minutes; revoked sessions are removed on the operational cleanup schedule |
| Pairing state | Connect exactly two verified adults | The two accounts; limited admin metadata | Active pairing plus private archive references |
| Profile name and processed photo variants | Show the two people on their phone and Wear launcher | Account owner and current partner; never admin content views | Until photo removal or account deletion; former partners lose access immediately |
| Confirmed pairing instant | Derive relationship age without collecting a separate personal date | Current couple only | Retained with the couple and private unpair archive references |
| Quiz drafts and responses | Private revisioned editing, then one reveal after both people finish all five | Author before reveal; current couple after reveal | Until user deletion/export policy applies |
| Quiz status polling | Notify about partner completion or shared reveal | Device owner; content-free server response | Latest UTC date and booleans in private app storage |
| Markdown notes, titles, presence, and revision history | Shared editing, organization, and recovery | Current couple only; presence contains account identity, never note text | Archived notes remain restorable for seven days, then are purged; unpair archives remain private |
| Note attachments and scan state | Share deliberately attached images, PDFs, text, audio, and video | Current couple only; admins see queue counts, never filenames or bytes | Until attachment deletion, note purge, or account/couple erasure; backup copies follow bounded backup expiry |
| Couple activity metadata and seen position | Show recent shared changes without copying feature content | Current couple only; each seen position belongs to its account | Events expire after 30 days and are deleted immediately on unpair; seen state ends with the couple |
| Smooch emoji, phrase key, sender, and send time | Deliver a private small signal and calculate weekly totals/history | Current couple and each person's private old-pairing archive; no admin content viewer | Retained across unpairing; permanently erased if either participant account is deleted |
| Smooch encrypted outbox | Retry deliberate sends during a short outage | Device owner only | At most five queued sends for 15 minutes; removed after send, expiry, sign-out, or app-data removal |
| Notification preferences, random installation ID, event metadata, and per-device acknowledgement | Deliver enabled partner alerts without a third-party push provider | Account owner and delivery service; no admin content viewer | Preferences until account deletion; events fetchable for 24 hours and purged within seven days; installations unseen for 90 days are removed |
| Countdown details | Shared events and reminders | Current couple only | Until deleted/archive policy applies |
| Location samples and accuracy | Estimate proximity sessions | Processing service; never admin UI | Raw coordinates deleted within 24 hours |
| Nearby-time estimates and corrections | Display coordinate-free estimated nearby time separately from relationship age | Current couple only; admins see operational counts | Until deletion/archive policy applies |
| Question reports | Hide unsafe/poor questions and review content | Reporter status; admin question metadata | Operational moderation window |
| AI batch metadata | Reliability, safety, and reproducibility | Admins | Operational/audit policy set before launch |
| App release and updater state | Discover and safely resume user-approved phone updates | Public release metadata; device-local opt-in, phase, check time, and byte counts | Published records are immutable; local state is replaced by later releases or app removal |
| Wireless-watch authorization key | Reconnect the same phone identity for later Wear updates | Device-local Android app only | Until the person forgets authorization, clears app data, or removes the app |

## Consent and control

Registration is for adults and uses 18+ self-attestation without identity documents. Android asks separately for notification, precise foreground location, and background location permission. Location permission alone does not enable collection: both partners must also enable sharing in Little Orbit. Both partners must opt into intimacy questions; either partner can disable them immediately.

Unpairing stops new sharing immediately, including access to a former partner's profile photo. Each person receives a private read-only archive. Profile photos are account-level and are not copied into relationship archives. Smooch history is included in that private archive and never transfers to a future partner. It remains until either original participant's account-deletion job erases the relationship's Smooch rows. Users can export their own processed profile photo and delete their account from the Android app; deletion jobs and bounded backup expiry must be visible and documented before launch.

The phone crops a chosen image to a square before upload. The server decodes JPEG, PNG, or WebP input, applies orientation, removes source metadata, and creates bounded 512-pixel and 128-pixel WebP variants. Only the owner and current partner can fetch them. The phone keeps encrypted thumbnails and sends authorized names and thumbnails through the private Wearable Data Layer. The Wear launcher stores them in app-private files. Home widgets, tiles, and complications remain text-only.

## Our Space and attachments

Notes open in Markdown preview, but raw HTML is rendered as text and remote images are converted to deliberate links so opening a note cannot silently contact a third-party image host. Only an authorized `attachment://` image from the current note may render inline, after exact size and SHA-256 verification. Sanitized GIF animation stays on device. The Android editor keeps an app-private draft with its base revision. Acknowledgements patch only the changed range and preserve the selection; unsafe revision divergence shows both versions for an explicit choice.

The picker accepts JPEG, PNG, WebP, GIF, PDF, plain text, Markdown, MP3, M4A, Ogg, MP4, and WebM. A file is limited to 100 MiB and the current couple is limited to 2 GiB. Uploads use stable operation IDs and exact offsets, and unscanned bytes stay in a private staging volume. ClamAV must report the file clean, then a type-specific sanitizer removes image, PDF, audio, or video metadata before the API makes the sanitized bytes available. Transparent still and animated images are rebuilt without losing their alpha frames. Because sanitization can change file size, the worker rechecks both limits under the couple lock before availability. Scanner outages fail closed and leave the item pending; malformed, infected, oversized, quota-exceeding, or unsanitizable content is quarantined or rejected. The API and owner console never expose attachment content or filenames to administrators.

Previews download only after current authorization and verify the sanitized SHA-256 digest. Temporary previews use the app cache. **Keep offline** copies a selected sanitized file into app-private storage until the person removes that copy, deletes the attachment, clears app data, or uninstalls Little Orbit. Audio and video previews are handed to a compatible installed viewer with a temporary read-only grant. Deleting an attachment hides it immediately for both partners and removes staging, available, cached, and kept-offline copies as each component next handles it. Note purge also removes its server files.

## Couple activity timeline

The Home right panel shows up to 30 days of recent note, attachment, countdown, quiz, and Smooch changes for the active couple. A row stores a fixed event kind, actor reference, time, navigation target, optional note/countdown title, and the approved Smooch emoji when relevant. It never stores note bodies, attachment names or bytes, quiz prompts or answers, location data, email addresses, or free-form Smooch text. Retry-safe dedupe keys prevent duplicate events, and each partner has a separate monotonic seen watermark. Opening the panel advances only that person's position. Unpairing deletes the active-couple timeline rather than copying it into archives, and the worker purges rows older than 30 days. The owner console has no timeline viewer.

## Administrative access

The owner console exposes account state, service health, security events, batch status, attachment scan/rejection counts, reports, and privacy-safe counts. It has no route or viewer for note text, attachment names or bytes, quiz answers, precise locations, or couple exports. Secrets are redacted at the API boundary and again in the web view.

Daily quiz notifications poll only the UTC date, state revision, and completion/reveal booleans. The polling response contains no prompt or answer content. Android may deliver the notification 15 minutes or more after the change because WorkManager controls timing. If either person disables intimacy questions, unrevealed intimacy prompts are replaced immediately, affected drafts are deleted, and both completion markers are reset so the replacement must be reviewed.

Partner notification choices are stored with the account. Android permission and each notification channel remain local to a random app-installation UUID; Little Orbit does not use a hardware advertising identifier. Smooch and note-edit events are created only after the feature transaction is accepted, and every enabled installation acknowledges independently after Android posts the alert. The foreground WebSocket carries only `notification.available`; the phone then fetches authorized event metadata. A note alert contains the partner display name, note ID, and current title, never the note body or attachment metadata. The public lock-screen version is always generic. A 30-minute document/editor cooldown prevents repetitive edit alerts, and no alert is created while the partner already views that note.

A sender may create at most five Smooches in a rolling hour. The encrypted offline outbox holds at most five deliberate sends for 15 minutes and never invents a send after that window. Weekly history uses the couple's chosen IANA home timezone and Monday-to-Sunday boundaries. Event payloads are fetchable for 24 hours, server records are purged within seven days, and installations unseen for 90 days are removed. WorkManager controls background timing, so a stopped app or OEM battery policy can delay an alert by 15 minutes or longer.

## Location processing

While signed in with local permission and mutual server consent, Android runs a visible foreground location service requesting a high-accuracy fix about every five minutes. A 15-minute WorkManager job remains as an OEM/process-recovery fallback and can collect while offline. Fixes older than two minutes are rejected locally. Clients send bounded encrypted retry queues containing a timestamp, coordinate, accuracy, and stable sample ID. The server accepts storage only while both partners consent, rejects out-of-policy values, and deduplicates uploads. Either partner's opt-out stops the service immediately, clears the local queue, deletes both partners' raw coordinates, and rejects later uploads until both enable sharing again.

The estimate matches the two streams deterministically one-to-one within ten minutes. It counts only intervals bounded by two confident nearby pairs no more than twenty minutes apart, then writes coordinate-free UTC-minute buckets. The current algorithm version and process time are stored so stale results remain visible as estimates rather than facts. Corrections are audited without silently changing raw history.

## AI boundary

Ollama has no published port. The worker reaches it through an internal AI network; the one-shot initializer is the only other caller. Ollama has a separate egress-only bridge so it can download the pinned model manifest, while no gateway, web, API, or database service shares that bridge. Prompts contain a calendar date, public generation rules, and limited recent global question text used for duplicate prevention. Generated candidates are site-wide and stored for administrator quality review. Prompts contain no profiles, answers, custom couple questions, notes, locations, relationship history, email addresses, or identifiers.

The planned 2.0 cycle tracker is outside this policy. It requires a separate health-data privacy, encryption, consent, deletion, abuse-risk, and medical-boundary review before implementation. Cycle data remains outside AI by default.

## App update boundary

The first RC10 launch asks whether automatic update detection should be enabled. If enabled, WorkManager checks public metadata about every six hours; a required compatibility update is checked regardless of that optional preference. The check sends only normal request network metadata plus the installed app name and numeric version code. The public release response and phone/Wear APK endpoints require no account data and contain no relationship data. The gateway receives ordinary download metadata such as IP address, time, requested version, and byte range; bounded operational logs follow the same privacy rules as other public requests. The phone stores the opt-in, last-check instant, release ID, progress phase, byte counts, optional defer state, and sanitized failure code in private app storage. It shows an optional prompt at most once per cold process while keeping an App updates banner available. Metadata work never downloads an APK. Android's `DownloadManager` and `PackageInstaller` act only after the person chooses to update, and a running or paused download with no progress for five minutes becomes an explicit retryable stalled state.

The in-app Wear installer uses local DNS-SD discovery or addresses typed by the person. It sends the short-lived pairing code only to the selected local watch endpoint, proves the encrypted identity with a harmless authenticated command, checks privacy-safe device properties, and transfers the already verified public Wear APK over wireless ADB. It keeps the reusable ADB private key encrypted by Android Keystore until the person chooses **Forget watch authorization** or clears app data. The temporary Wear APK is held in the phone's private cache. Endpoint state stays in memory for the active installer, and safe failure records contain only a stage code. The server never receives the watch address, ports, pairing code, device fingerprint, model, or security patch.
