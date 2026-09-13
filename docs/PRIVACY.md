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
| Plain-text notes, titles, presence, and revision history | Shared editing, organization, and recovery | Current couple only; presence contains account identity, never note text | Archived notes remain restorable for seven days, then are purged; unpair archives remain private |
| Smooch emoji, phrase key, sender, and send time | Deliver a private small signal and calculate weekly totals/history | Current couple and each person's private old-pairing archive; no admin content viewer | Retained across unpairing; permanently erased if either participant account is deleted |
| Smooch encrypted outbox and notification preference | Retry deliberate sends and control lock-screen wording | Device owner only | At most five queued sends for 15 minutes; preference remains until app data removal |
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

## Administrative access

The owner console exposes account state, service health, security events, batch status, reports, and privacy-safe counts. It has no route or viewer for note text, quiz answers, precise locations, or couple exports. Secrets are redacted at the API boundary and again in the web view.

Daily quiz notifications poll only the UTC date, state revision, and completion/reveal booleans. The polling response contains no prompt or answer content. Android may deliver the notification 15 minutes or more after the change because WorkManager controls timing. If either person disables intimacy questions, unrevealed intimacy prompts are replaced immediately, affected drafts are deleted, and both completion markers are reset so the replacement must be reviewed.

Smooch polling returns authenticated pending events only to the recipient. The default lock-screen notification says that the partner is thinking about them and hides the selected emoji; a device-local setting can show the full phrase and emoji. A sender may create at most five events in a rolling hour. The encrypted offline outbox holds at most five deliberate sends for 15 minutes and never invents a send after that window. Weekly history uses the couple's chosen IANA home timezone and Monday-to-Sunday boundaries.

## Location processing

While signed in with local permission and mutual server consent, Android runs a visible foreground location service requesting a high-accuracy fix about every five minutes. A 15-minute WorkManager job remains as an OEM/process-recovery fallback and can collect while offline. Fixes older than two minutes are rejected locally. Clients send bounded encrypted retry queues containing a timestamp, coordinate, accuracy, and stable sample ID. The server accepts storage only while both partners consent, rejects out-of-policy values, and deduplicates uploads. Either partner's opt-out stops the service immediately, clears the local queue, deletes both partners' raw coordinates, and rejects later uploads until both enable sharing again.

The estimate matches the two streams deterministically one-to-one within ten minutes. It counts only intervals bounded by two confident nearby pairs no more than twenty minutes apart, then writes coordinate-free UTC-minute buckets. The current algorithm version and process time are stored so stale results remain visible as estimates rather than facts. Corrections are audited without silently changing raw history.

## AI boundary

Ollama has no published port. The worker reaches it through an internal AI network; the one-shot initializer is the only other caller. Ollama has a separate egress-only bridge so it can download the pinned model manifest, while no gateway, web, API, or database service shares that bridge. Prompts contain a calendar date, public generation rules, and limited recent global question text used for duplicate prevention. Generated candidates are site-wide and stored for administrator quality review. Prompts contain no profiles, answers, custom couple questions, notes, locations, relationship history, email addresses, or identifiers.

The planned 2.0 cycle tracker is outside this policy. It requires a separate health-data privacy, encryption, consent, deletion, abuse-risk, and medical-boundary review before implementation. Cycle data remains outside AI by default.

## App update boundary

The first RC10 launch asks whether automatic update detection should be enabled. If enabled, WorkManager checks public metadata about every six hours; a required compatibility update is checked regardless of that optional preference. The check sends only normal request network metadata plus the installed app name and numeric version code. The public release response and phone/Wear APK endpoints require no account data and contain no relationship data. The gateway receives ordinary download metadata such as IP address, time, requested version, and byte range; bounded operational logs follow the same privacy rules as other public requests. The phone stores the opt-in, last-check instant, release ID, progress phase, byte counts, optional defer state, and sanitized failure code in private app storage. It shows an optional prompt at most once per cold process while keeping a More-tab banner available. Metadata work never downloads an APK. Android's `DownloadManager` and `PackageInstaller` act only after the person chooses to update, and a running or paused download with no progress for five minutes becomes an explicit retryable stalled state.

The in-app Wear installer uses local DNS-SD discovery or addresses typed by the person. It sends the short-lived pairing code only to the selected local watch endpoint, checks privacy-safe device properties, and transfers the already verified public Wear APK over wireless ADB. It keeps the reusable ADB private key encrypted by Android Keystore until the person chooses **Forget watch authorization** or clears app data. The temporary Wear APK is held in the phone's private cache. The server never receives the watch address, pairing code, device model, or security patch.
