# Privacy design

Little Orbit is designed around two people sharing deliberately. It does not sell personal data, display advertising, or use relationship activity to train or personalize AI. The 1.0 AI pipeline creates the same calendar-based question pool for the service and receives no user data.

This document describes the intended 1.0 behavior while the project is under development. A production privacy notice and legal review are release gates.

## Data and purpose

| Data | Purpose | Access | Intended retention |
|---|---|---|---|
| Email, password hash, verification state | Account access and recovery | Account owner; limited admin metadata | Until deletion plus bounded backup expiry |
| Session identifiers and security events | Authentication and abuse response | Account owner sessions; privacy-limited admins | App sessions expire after 30 days; admin sessions after 30 minutes; revoked sessions are removed on the operational cleanup schedule |
| Pairing state | Connect exactly two verified adults | The two accounts; limited admin metadata | Active pairing plus private archive references |
| Quiz responses | Reveal after both partners answer | Current couple only | Until user deletion/export policy applies |
| Plain-text notes and revision history | Shared editing and recovery | Current couple only | Until deletion or private unpair archive policy applies |
| Countdown details | Shared events and reminders | Current couple only | Until deleted/archive policy applies |
| Location samples and accuracy | Estimate proximity sessions | Processing service; never admin UI | Raw coordinates deleted within 24 hours |
| Together-time estimates and corrections | Display aggregate shared time | Current couple only; admins see operational counts | Until deletion/archive policy applies |
| Question reports | Hide unsafe/poor questions and review content | Reporter status; admin question metadata | Operational moderation window |
| AI batch metadata | Reliability, safety, and reproducibility | Admins | Operational/audit policy set before launch |
| App release and updater state | Discover and safely resume user-approved phone updates | Public release metadata; device-local phase and byte counts | Published records are immutable; local state is replaced by later releases or app removal |

## Consent and control

Registration is for adults and uses 18+ self-attestation without identity documents. Background location and intimacy questions each require separate consent. Location permission alone does not enable collection. Both partners must opt into intimacy questions; either partner can disable them immediately.

Unpairing stops new sharing immediately. Each person receives a private read-only archive. An archive from an old pairing never becomes visible to a future partner. Users can export and delete their account from the Android app; deletion jobs and bounded backup expiry must be visible and documented before launch.

## Administrative access

The owner console exposes account state, service health, security events, batch status, reports, and privacy-safe counts. It has no route or viewer for note text, quiz answers, precise locations, or couple exports. Secrets are redacted at the API boundary and again in the web view.

## Location processing

Clients send consented, bounded batches with timestamp, coordinate, accuracy, and a stable sample ID. The server rejects unauthorized samples and values outside its timestamp, coordinate, and accuracy bounds; deduplicates uploads; applies an initial configurable 100-metre threshold with accuracy-aware distance bounds; and stores at most one estimated bucket per couple and minute. Results are labelled estimates and show last update time. Corrections are audited without rewriting raw history silently.

## AI boundary

Ollama has no published port. The worker reaches it through an internal AI network; the one-shot initializer is the only other caller. Ollama has a separate egress-only bridge so it can download the pinned model manifest, while no gateway, web, API, or database service shares that bridge. Prompts contain a calendar date, public generation rules, and limited recent question text used for duplicate prevention. They contain no profiles, answers, notes, locations, relationship history, email addresses, or identifiers.

The planned 2.0 cycle tracker is outside this policy. It requires a separate health-data privacy, encryption, consent, deletion, abuse-risk, and medical-boundary review before implementation. Cycle data remains outside AI by default.

## App update boundary

The update check sends only the normal request network metadata plus the installed app name and numeric version code. The public release response contains no account or relationship data. The phone stores a release ID, progress phase, byte counts, optional defer time, and sanitized failure code in its private app storage. Android's `DownloadManager` and `PackageInstaller` handle the APK after the person chooses to update. The phone updater does not read or transfer relationship data and never sends an APK to Wear OS.
