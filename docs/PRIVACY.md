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
| Relationship start date and proposals | Show mutually agreed calendar relationship age | Current couple only | Accepted date follows the pairing archive policy; retry records expire after 30 days and resolved proposals after 90 days |
| Quiz drafts and responses | Private revisioned editing, then one reveal after both people finish all five | Author before reveal; current couple after reveal | Until user deletion/export policy applies |
| Quiz status polling | Notify about partner completion or shared reveal | Device owner; content-free server response | Latest UTC date and booleans in private app storage |
| Plain-text notes and revision history | Shared editing and recovery | Current couple only | Until deletion or private unpair archive policy applies |
| Countdown details | Shared events and reminders | Current couple only | Until deleted/archive policy applies |
| Location samples and accuracy | Estimate proximity sessions | Processing service; never admin UI | Raw coordinates deleted within 24 hours |
| Nearby-time estimates and corrections | Display coordinate-free estimated nearby time separately from relationship age | Current couple only; admins see operational counts | Until deletion/archive policy applies |
| Question reports | Hide unsafe/poor questions and review content | Reporter status; admin question metadata | Operational moderation window |
| AI batch metadata | Reliability, safety, and reproducibility | Admins | Operational/audit policy set before launch |
| App release and updater state | Discover and safely resume user-approved phone updates | Public release metadata; device-local phase and byte counts | Published records are immutable; local state is replaced by later releases or app removal |
| Wireless-watch authorization key | Reconnect the same phone identity for later Wear updates | Device-local Android app only | Until the person forgets authorization, clears app data, or removes the app |

## Consent and control

Registration is for adults and uses 18+ self-attestation without identity documents. Android asks separately for notification, precise foreground location, and background location permission. Location permission alone does not enable collection: both partners must also enable sharing in Little Orbit. Both partners must opt into intimacy questions; either partner can disable them immediately.

Unpairing stops new sharing immediately, including access to a former partner's profile photo. Each person receives a private read-only archive. Profile photos are account-level and are not copied into relationship archives. An archive from an old pairing never becomes visible to a future partner. Users can export their own processed profile photo and delete their account from the Android app; deletion jobs and bounded backup expiry must be visible and documented before launch.

The phone crops a chosen image to a square before upload. The server decodes JPEG, PNG, or WebP input, applies orientation, removes source metadata, and creates bounded 512-pixel and 128-pixel WebP variants. Only the owner and current partner can fetch them. The phone keeps encrypted thumbnails and sends authorized names and thumbnails through the private Wearable Data Layer. The Wear launcher stores them in app-private files. Home widgets, tiles, and complications remain text-only.

## Administrative access

The owner console exposes account state, service health, security events, batch status, reports, and privacy-safe counts. It has no route or viewer for note text, quiz answers, precise locations, or couple exports. Secrets are redacted at the API boundary and again in the web view.

Daily quiz notifications poll only the UTC date, state revision, and completion/reveal booleans. The polling response contains no prompt or answer content. Android may deliver the notification 15 minutes or more after the change because WorkManager controls timing. If either person disables intimacy questions, unrevealed intimacy prompts are replaced immediately, affected drafts are deleted, and both completion markers are reset so the replacement must be reviewed.

## Location processing

Clients request a balanced-power fix about every 15 minutes while signed in, locally permitted, and server consent remains enabled. Fixes older than two minutes are rejected locally. Clients send bounded encrypted retry queues containing a timestamp, coordinate, accuracy, and stable sample ID. The server accepts storage only while both partners consent, rejects out-of-policy values, and deduplicates uploads. Either partner's opt-out deletes both partners' raw coordinates.

The estimate matches the two streams deterministically one-to-one within ten minutes. It counts only intervals bounded by two confident nearby pairs no more than twenty minutes apart, then writes coordinate-free UTC-minute buckets. The current algorithm version and process time are stored so stale results remain visible as estimates rather than facts. Corrections are audited without silently changing raw history.

## AI boundary

Ollama has no published port. The worker reaches it through an internal AI network; the one-shot initializer is the only other caller. Ollama has a separate egress-only bridge so it can download the pinned model manifest, while no gateway, web, API, or database service shares that bridge. Prompts contain a calendar date, public generation rules, and limited recent global question text used for duplicate prevention. Generated candidates are site-wide and stored for administrator quality review. Prompts contain no profiles, answers, custom couple questions, notes, locations, relationship history, email addresses, or identifiers.

The planned 2.0 cycle tracker is outside this policy. It requires a separate health-data privacy, encryption, consent, deletion, abuse-risk, and medical-boundary review before implementation. Cycle data remains outside AI by default.

## App update boundary

The update check sends only the normal request network metadata plus the installed app name and numeric version code. The public release response and phone/Wear APK endpoints require no account data and contain no relationship data. The self-hosted gateway receives ordinary download metadata such as IP address, time, requested version, and byte range; bounded operational logs follow the same privacy rules as other public requests. The phone stores a release ID, progress phase, byte counts, optional defer time, and sanitized failure code in its private app storage. Android's `DownloadManager` and `PackageInstaller` handle the phone APK after the person chooses to update.

The in-app Wear installer uses local DNS-SD discovery or addresses typed by the person. It sends the short-lived pairing code only to the selected local watch endpoint, checks privacy-safe device properties, and transfers the already verified public Wear APK over wireless ADB. It keeps the reusable ADB private key encrypted by Android Keystore until the person chooses **Forget watch authorization** or clears app data. The temporary Wear APK is held in the phone's private cache. The server never receives the watch address, pairing code, device model, or security patch.
