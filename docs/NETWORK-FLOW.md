# Network and logic flows

The Mermaid diagrams in this document are the editable architecture source of truth. The overview PNG is a reader-friendly concept and must be regenerated when its flow changes.

![Little Orbit network and logic overview](assets/network-flow-overview.png)

## External routing and trust

```mermaid
flowchart TD
    Clients[Android / Wear OS / Browser] -->|HTTPS or WSS| DNS[lil-orb.pax-kun.com]
    DNS -->|public DNS| NPM[Nginx Proxy Manager<br/>192.168.50.6]
    NPM -->|HTTP :8180<br/>trusted forwarded headers| Gateway[Gateway<br/>192.168.50.182:8180]
    Gateway -->|all other paths| Web[Next.js]
    Gateway -->|/api/* and /ws/*| API[FastAPI]
    API --> DB[(PostgreSQL)]
    Init[One-shot volume ownership init] --> Files[(Private attachment volume)]
    API --> Files
    API -. healthy after Alembic reaches head .-> Worker
    Worker[Worker] --> DB
    Worker --> AI[AI adapter]
    AI --> Ollama[Ollama<br/>no published port]
    Ollama -. model install only .-> Registry[Ollama model registry]
    Worker --> SMTP[SMTP adapter]
    Worker -->|expired-note cleanup| Files
    MediaWorker[Media worker] --> DB
    MediaWorker --> Files
    MediaWorker --> ClamAV[ClamAV<br/>internal network only]

    Untrusted[Other LAN peer] -. spoofed X-Forwarded-For .-> Gateway
    Gateway -. ignore forwarded headers .-> Untrusted
```

Only gateway port 8180 is published by Compose. Windows Firewall allows that production port only from `192.168.50.6`. The address `192.168.50.182` needs a DHCP reservation before production use. The worker waits for API health so migrations finish before maintenance or scheduled generation can query the new schema.

Caddy trusts incoming `X-Forwarded-For` only when its immediate peer is `192.168.50.6`. It overwrites a private `X-Little-Orbit-Client-IP` header before proxying to FastAPI. FastAPI accepts that private header only from Caddy's fixed `gateway-api` address, validates it as exactly one IP address, and does not enable Uvicorn's generic proxy-header trust. Compose reserves `172.30.14.2` for Caddy and `172.30.14.3` for FastAPI so update-time start order cannot give the trusted proxy address to the application container. Direct or malformed values fall back to the socket peer for throttling.

## Authentication and pairing

```mermaid
sequenceDiagram
    actor A as Creator
    actor B as Partner
    participant API
    participant DB as PostgreSQL
    A->>API: Register + 18+/terms + honeypot
    API->>DB: Commit capped IP + email digest counters
    API->>DB: Store Argon2id hash + hashed verification token
    API-->>A: Neutral response; email verification link
    A->>API: Consume verification token once
    A->>API: Create pair code
    API->>DB: Store hashed 8-char code, expires +10m
    B->>API: Redeem code
    API->>DB: Commit capped IP + account digest counters
    API->>DB: Lock both accounts, then code; recheck eligibility and capacity
    API-->>A: Ask creator to confirm B
    A->>API: Confirm pending partner
    API->>DB: Re-lock accounts in UUID order; recheck expiry and eligibility
    API->>DB: One transaction: consume code + create two-member couple
    API-->>A: Return shared paired state
    API-->>B: Pairing becomes visible on the next authenticated refresh
```

Public registration, resend, and recovery responses are identical for known and unknown emails. Login, resend, recovery, reset, pair redemption, and administrator proof limits use capped PostgreSQL counters. The service commits these attempts independently, persists only scope-separated keyed hashes, applies the IP bucket before an attacker-controlled subject, and removes inactive rows within 24 hours plus the worker interval.

Password reset locks the account and all outstanding reset tokens, consumes every link, changes the password, and revokes all sessions in one transaction. Login, rotation, administrator issuance, revocation, unpairing, and deletion share the account row as their outer serialization boundary so a stale credential cannot create a surviving session after reset.

```mermaid
sequenceDiagram
    participant Phone as Android phone
    participant API
    participant Local as Encrypted local state
    Phone->>API: Authenticated Home/profile/background refresh
    alt Session is valid and relationship is active
        API-->>Phone: Authorized current state
        Phone->>Local: Replace bounded cache
    else Session is expired, revoked, suspended, or deleted
        API-->>Phone: 401
        Phone->>Local: Clear token, account/pair caches, drafts, media, alerts, and work
        Phone-->>Phone: Render signed-out Home
    else Account is valid but relationship is inactive
        API-->>Phone: 409 relationship_inactive
        Phone->>Local: Preserve account token; purge relationship state and passive surfaces
        Phone-->>Phone: Render pairing setup
    end
```

Public sign-in and password proof failures do not use the authenticated-session purge path. Home derives its recovery state after the failing request completes so a delayed callback cannot replace the signed-out screen with stale cached identity.

## Big Orbit enrollment and administrator MFA

```mermaid
sequenceDiagram
    actor Console as Trusted server console
    actor Admin as Owner on fresh Big Orbit device
    participant Key as Android Keystore
    participant API
    participant DB as PostgreSQL
    Console->>API: bootstrap-admin owner@example.com
    API->>DB: Invalidate older PIN/setup; store hash with 10-minute expiry
    API-->>Console: Show one 8-digit PIN once
    Admin->>Key: Create non-exportable P-256 key
    Admin->>API: Password + PIN + label + public key
    API->>DB: Commit capped IP + administrator digest counters
    API->>DB: Lock account; verify password; consume PIN; create pending device
    API-->>Admin: Restricted 10-minute setup token
    Admin->>API: Request bootstrap challenge
    API-->>Admin: Single-use bootstrap challenge
    Admin->>Key: Sign canonical bootstrap challenge
    Admin->>API: Challenge + signature
    API->>DB: Consume challenge; prove pending device key
    alt First owner has no enabled MFA
        API-->>Admin: TOTP URI + QR PNG
        Admin->>API: Current 6-digit TOTP
        API->>DB: Enable MFA; hash recovery codes; approve device
        API-->>Admin: Recovery codes once + device credential + session
    else Existing MFA remains enabled
        API->>DB: Approve device without changing MFA
        API-->>Admin: Device credential + session
    end
    opt Final response is lost before local credential storage
        Admin->>API: Request a fresh bootstrap challenge within original expiry
        Admin->>Key: Sign the new challenge with the same key
        API->>DB: Rotate replacement credential and short session
        API-->>Admin: Replacement credential + session
    end
    loop Each session or background rotation
        Admin->>API: Request fresh session challenge
        API-->>Admin: Five-minute single-use challenge
        Admin->>Key: Sign canonical session challenge
        Admin->>API: Credential + signature
        API->>DB: Verify enrolled non-revoked device; bind 30-minute session
    end
    Admin->>API: Read allowlisted operational metadata or queue typed job
    API-->>Admin: No relationship content or arbitrary command surface
```

The setup token is a separate restricted capability and cannot read ordinary administrator metadata or queue operations. A fifth wrong PIN invalidates it; a new console PIN expires every older live setup capability, and ordinary expiry revokes a still-pending device. Process death may resume within the original ten-minute window. If completion committed but its response was lost, recovery requires a fresh single-use signature from the same device key before credentials rotate. The public web app has no `/admin` interface and the final API has no `/v1/admin`. Administrator MFA replacement still requires the current password plus the current factor, keeps the old factor active until confirmation, and revokes earlier sessions after a successful swap. Big Orbit alert acknowledgement is per enrolled device, so one phone cannot consume another owner's action inbox.

## Live notes

```mermaid
sequenceDiagram
    participant A as Partner A
    participant API
    participant DB as PostgreSQL
    participant B as Partner B
    B->>API: GET authorized note directory while library is foreground
    API->>DB: Authorize current couple before listing notes
    API-->>B: Ordered directory snapshot
    A->>API: POST document(operation_id, title, body)
    API->>DB: Lock current couple; resolve exact operation ID
    API->>DB: Recover exact document saved in bounded window or insert once
    API-->>B: notification.available (content-free)
    loop Every 5 s while B's library remains visible
        B->>API: Refresh authorized directory
        API-->>B: Changed snapshot or identical snapshot
    end
    A->>API: Open one WSS editor session(note_id)
    API->>DB: Authorize actor before note lookup
    API->>DB: After hub registration, recheck exact session + account + note access
    API-->>A: Snapshot(revision N) + unique-account presence
    A->>API: Operation(op_id, base N, insert/delete)
    API->>DB: Lock account + exact session, then couple + note
    API->>DB: Dedupe op_id; transform; append revision N+1
    API-->>A: Ack(op_id, current body, revision N+1)
    API-->>B: Applied operation(revision N+1)
    Note over A,B: Body input debounces 750 ms;<br/>ack patches preserve cursor/selection;<br/>duplicate operation IDs return current state
    A--xAPI: Disconnect
    Note over A: Preserve draft and base revision
    A->>API: Reconnect with base revision
    API-->>A: Operations or conflict snapshot
    Note over A: If revisions diverge beyond safe transform, show both versions
    A->>API: Rename or archive with metadata operation ID
    API->>DB: Lock couple + note; dedupe; increment metadata revision
    Note over DB: Archived notes reject body operations<br/>and remain restorable for 7 days
    loop Every operation or 30 s idle heartbeat
        API->>DB: Recheck session, account, and current note access
        DB-->>API: Active or terminal revocation
    end
```

Session expiry, revocation, suspension, deletion, unpairing, or note archival closes the socket. The server retains only the keyed session digest needed for revalidation; the raw bearer token is not kept in connection state. A new Android workspace persists one stable create ID before its first request and serializes create, title, and body mutations. Autosave runs after 800 milliseconds idle and at least every five seconds while typing. A newer server revision stops synchronization; an explicit fork request copies only authorized clean attachments, rewrites their IDs, and leaves the shared source untouched. Android does not rebuild the library for an identical snapshot, and leaving the library stops its directory refresh.

## Private note attachments

```mermaid
sequenceDiagram
    actor A as Current partner
    participant API
    participant DB as PostgreSQL
    participant Files as Private volume
    participant Media as Media worker
    participant AV as ClamAV
    A->>API: Reserve(note_id, op_id, name, type, bytes, SHA-256)
    API->>DB: Authorize before note lookup; lock couple; reserve quota
    API-->>A: Stable attachment ID + exact upload offset
    loop Bounded 1 MiB client chunks
        A->>API: PUT bytes with Upload-Offset
        API->>Files: Append at locked offset
        API-->>A: Current offset and state
    end
    API->>DB: Mark pending_scan only after original SHA-256 matches
    Media->>Files: Stream staged file
    Media->>AV: INSTREAM scan on isolated network
    AV-->>Media: Clean, found, or unavailable
    alt clean and sanitization succeeds
        Media->>Files: Write metadata-free type-specific copy
        Media->>DB: Re-lock couple; recheck final size/quota; mark available
        Media->>DB: Append content-free attachment-ready activity
        A->>API: GET sanitized content
        API->>DB: Reauthorize current couple and note
        API-->>A: Private no-store bytes + exact digest
    else scanner unavailable
        Media->>DB: Return to pending_scan for bounded retry
    else unsafe or invalid
        Media->>DB: Mark rejected with content-free reason
        Media->>Files: Delete staged and output bytes
    end
```

The API accepts only the allow-listed media types, at most 100 MiB per file and 2 GiB per current couple. Request streams are bounded before buffering, operation-ID replays must describe the same bytes, and neither staging nor ClamAV has a published port. The media worker permits bounded sanitizer growth, then rechecks the final 100 MiB limit and couple quota while holding the couple lock. Android inserts an `attachment://` reference only after availability and verifies the sanitized hash before preview or **Keep offline**. Deletion removes server bytes immediately; note expiry removes remaining volume objects after the database transaction.

## Private couple activity

```mermaid
sequenceDiagram
    actor A as Current partner
    participant Feature as Note / attachment / countdown / quiz / Smooch service
    participant API
    participant DB as PostgreSQL
    participant Phone as Android Home panel
    Feature->>DB: Hold couple lock and complete mutation
    Feature->>DB: Append deduped content-free event at sequence N+1
    Note over DB: Kind, actor, target ID/title, optional fixed emoji<br/>No note body, attachment name, quiz answer, or location
    Phone->>API: Fetch newest activity page
    API->>DB: Authorize current active membership before lookup
    DB-->>API: Couple-only events + private seen watermark
    API-->>Phone: Content-free activity page
    A->>Phone: Open right Home panel
    Phone->>API: Mark highest visible sequence seen
    API->>DB: Lock couple and advance watermark monotonically
    DB->>DB: Worker deletes events older than 30 days
    Note over DB: Unpair deletes the active-couple feed immediately
```

The timeline helps each partner notice shared changes without creating another copy of private content. Event insertion shares the mutation's couple lock, dedupe keys make retries harmless, and sequence and seen watermarks only move forward. Administrators have no feed viewer.

## Weekly quiz feedback learning and generation

```mermaid
flowchart TD
    Reveal[Shared reveal for eligible global question] --> Feedback[Private stars + fixed tags<br/>optional separately consented review]
    Feedback --> Linked[Author-readable linked feedback<br/>editable through day 30]
    Linked --> Aggregate{At least 5 distinct accounts<br/>for question and week?}
    Aggregate -->|no| Hold[No admin or AI review surface]
    Aggregate -->|yes| Saturday[Saturday 09:00 America/Los_Angeles<br/>learn new eligible feedback]
    Saturday --> Policy[Evaluate bounded policy<br/>activate only on deterministic pass]
    Saturday --> Theme[Plan one Monday-Sunday arc<br/>7 unique days, at most 2 observances]
    Linked -->|day 30| Unlink[Remove account, couple, and quiz-day links]
    Unlink -->|by day 90| DeleteReview[Hard-delete raw review text]
    Policy --> Sunday[Sunday 09:00 local generation<br/>next Monday-Sunday]
    Theme --> Sunday
    Sources[Exact code-owned HTTPS sources] --> Fetcher[Secret-free fetcher<br/>public DNS, no redirects, 64 KiB]
    Fetcher --> Sunday
    Knowledge[Reviewed manifest-owned Markdown] --> Chunks[Bounded hashed pgvector chunks]
    Chunks --> Sunday
    Sunday --> Qwen[Pinned local Qwen model<br/>strict v4 JSON]
    Qwen --> Validate{Schema, safety, whitespace,<br/>answerability, consent}
    Validate -->|reject| Quarantine[Quarantine with reason codes]
    Validate -->|accept| Semantic{365-day exact + trigram +<br/>concept family + pinned Nomic vectors}
    Semantic -->|duplicate| Quarantine
    Semantic -->|unique| Select[Exactly 3 themed + 2 variety<br/>1 light + 2 reflective + 2 deeper]
    Reserve[One-use reviewed reserve<br/>1,825 general + 365 intimacy] -->|outage or shortage| Select
    Select --> Publish[Exactly 5 global questions per day<br/>plus intimacy alternatives]
    Publish --> Audit[Model digests, prompt/policy versions,<br/>validation and fallback metadata]
```

Invalid model output is quarantined rather than repaired. Tabs, line breaks, control characters, non-breaking spaces, repeated horizontal spaces, and leading or trailing whitespace are rejected before publication so hidden layout characters never reach Android. Global concepts are compared within the batch, planned week, and preceding 365 days; formatting changes do not reset memory. Public context may fall back to its latest sanitized snapshot for at most 30 days, after which reviewed knowledge and reserve content keep coverage while Big Orbit receives a content-free alert. Current plus seven-day coverage is maintained independently of the weekly run, so a model, embedding, feedback, or browsing failure cannot leave a quiz day empty. Neither local model receives answers, account/couple identity, notes, custom questions, locations, or relationship history.

## Daily quiz, custom queue, and reveal

```mermaid
sequenceDiagram
    actor A as Partner A
    actor B as Partner B
    participant API
    participant DB as PostgreSQL
    A->>API: GET today's UTC quiz
    API->>DB: Lock couple; snapshot 5 questions once
    Note over DB: Due custom FIFO slots first,<br/>then eligible global questions
    API-->>A: Stable ordered set; no partner answers
    A->>API: PUT private draft(op_id, answer revision)
    API->>DB: Authorize, dedupe op_id, validate type, increment revision
    A->>API: POST finish(day revision)
    API->>DB: Mark A finished + enqueue partner-finished event
    B->>API: Save all five drafts + finish
    API->>DB: Lock both member rows; set one revealed_at + enqueue results-ready events
    API-->>B: Both complete; include both answer sets
    A->>API: Fetch pending events for random installation ID
    API-->>A: results-ready with UTC date only
    A->>API: GET day
    API-->>A: Side-by-side shared reveal
```

A person may reopen and edit a finished set only before the shared reveal. Past incomplete days remain editable for seven days and remain visible for 30. Custom questions take the next available UTC slot, up to all five questions, and surprise content is hidden from the other partner until its day arrives. Non-surprise custom questions appear in both partners' pending queue. Intimacy-tagged custom or global questions require both partners' current consent. If either person opts out, every unrevealed intimacy prompt is replaced atomically, its drafts are cleared, and both people review the safe replacement before finishing again.

```mermaid
sequenceDiagram
    actor A as Feedback author
    participant Phone as Little Orbit Android
    participant API
    participant DB as PostgreSQL
    Phone->>API: GET /v3 quiz day
    API->>DB: Authorize active member before day lookup
    API-->>Phone: Shared reveal + per-question eligibility + author's feedback only
    A->>Phone: Stars, up to 3 fixed tags, optional review consent
    Phone->>API: PUT feedback(operation_id, expected_revision)
    API->>DB: Reauthorize; lock eligible launch-forward global question
    API->>DB: Sanitize; dedupe operation; create/update author row
    API-->>Phone: Author-only revision and editable-until
    opt Author removes feedback within 30 days
        Phone->>API: DELETE with operation_id and expected_revision
        API->>DB: Lock author row; delete idempotently
    end
    Note over DB: Partner never receives A's linked feedback<br/>Answers never enter feedback or AI inputs
```

## Calendar-aware countdowns and private reminders

```mermaid
sequenceDiagram
    actor A as Partner A
    actor B as Partner B
    participant PhoneA as Android A
    participant API
    participant DB as PostgreSQL
    participant Calendar as Selected calendar app
    A->>PhoneA: Pick timed instant or all-day local date
    PhoneA->>API: Mutation(op_id, revision, timezone, timing kind)
    API->>DB: Authorize; lock couple; validate; dedupe; save
    API->>DB: Enqueue countdown-created/rescheduled event for B
    A->>API: Replace my reminder offsets
    API->>DB: Store only A's fixed offset choices
    API-->>PhoneA: Countdown plus A's private reminders
    PhoneA->>PhoneA: Schedule local alerts; all-day uses 09:00 event time
    B->>API: GET countdowns
    API-->>B: Shared details plus only B's reminder choices
    A->>PhoneA: Add to calendar
    PhoneA->>Calendar: Prefilled user-approved insert intent
    Note over PhoneA,Calendar: One-way copy; no calendar token or later sync
```

Reboot, app replacement, clock change, timezone change, and successful countdown sync all trigger reminder reconciliation. Offline countdown mutations keep their operation IDs and existing reminder selection until the server accepts the change.

## Pairing-based relationship age

```mermaid
sequenceDiagram
    actor A as Pair-code creator
    actor B as Redeemer
    participant API
    participant DB as PostgreSQL
    A->>API: Create pair code
    B->>API: Redeem code
    A->>API: Confirm B
    API->>DB: Atomically create couple(created_at = UTC now)
    A->>API: GET together-time v3
    API->>DB: Authorize current member before couple lookup
    API-->>A: paired_at metadata + observed nearby estimate and bounded live state
    B->>API: GET together-time v3
    API-->>B: Same immutable paired_at metadata + observed nearby estimate and bounded live state
```

The confirmed pair transaction retains the immutable relationship origin without asking either partner to choose a date. Phone, widget, tile, and complication surfaces do not present that age as time spent together; they lead with the accuracy-aware nearby estimate. Legacy v1/v2 together-time writers return `410 Gone`; supported clients use the v3 contract.

## Together-time processing

```mermaid
flowchart TD
    Consent[Both users enable sharing] --> FGS[Visible foreground service<br/>high accuracy about every 2 min]
    SignIn[Sign-in or signed-in process start] --> Fallback[Re-arm WorkManager recovery<br/>about every 15 min]
    Consent --> Fallback
    FGS --> Samples[Queue bounded encrypted samples<br/>relationship + generation + ID + UTC + accuracy + coordinate]
    Fallback --> Samples
    Samples --> Upload[Authenticated v3 idempotent batch]
    Upload --> Checks{Authorize and lock exact couple,<br/>consent current, bounded values, unique ID}
    Checks -->|reject| Audit[Privacy-safe rejection event]
    Checks -->|accept| Timeline[Chronological union of both streams<br/>evaluate every observation]
    Timeline --> Threshold{Two consecutive nearby decisions?<br/>sample skew and interval each at most 5 min}
    Threshold -->|yes| Bucket[Replace rolling uncorrected<br/>UTC-minute observed estimates]
    Threshold -->|no| Skip[Do not count the interval]
    Bucket --> Estimate[Observed total + mutual freshness<br/>from both member streams]
    Skip --> Estimate
    Estimate --> Lease[Optional display-only live lease<br/>expires 5 min after older member evidence]
    Lease --> Phone[Phone ticks with elapsedRealtime<br/>and polls every 30 s]
    Estimate --> Cache[Widget/watch cache observed total only]
    Samples --> Expiry[Schedule expiry at 23 h 55 min<br/>Defensive hard delete at 24 h]
    OptOut[Either partner opts out or permission is removed] --> StopLocal[Stop service + clear local queue]
    StopLocal --> Delete[Delete both partners' raw coordinates]
    Delete --> Stop[Reject future uploads until mutual consent]
    Correction[User correction] --> CorrectionAudit[Append audited correction]
    CorrectionAudit --> Estimate
```

Collection may continue into the relationship-scoped encrypted queue while the network is offline or temporarily throttled. Upload and server processing resume later, except that a sample already inside the five-minute cleanup margin is rejected instead of being reintroduced near its hard retention ceiling. Sign-in and signed-in process startup re-arm recovery work after local account cleanup, while a paired foreground screen reconciles current permission and both consent states.

The estimator walks the chronological union of both sample streams. Direct credit requires nearby decisions and two-phone evidence bounded to five minutes. A later strong nearby anchor may confirm an unknown gap up to 20 minutes only when no intervening observation reports apart or poor accuracy; the stored minute records label that duration as a bridge. Open gaps stay unverified and excluded from the durable total. Freshness and the five-minute live deadline use the older member's newest evidence, so one phone cannot make a stalled pair estimate appear current. Network restoration or a Wi-Fi/cellular transition may request a fresh sample, but network identity never leaves Android and never proves proximity. Widget and Wear records never extrapolate.

```mermaid
sequenceDiagram
    participant Phone as Opted-in phone
    participant API
    participant DB as PostgreSQL
    participant Partner as Active partner
    Phone->>API: PUT installation health (random installation UUID)
    API->>DB: Authorize current couple; replace 24-hour snapshot
    Partner->>API: GET current couple health
    API-->>Partner: Health fields only; no installation IDs
    Phone->>API: DELETE health on opt-out/sign-out
    Note over DB: Unpair deletes snapshots; backups exclude their rows
```

## Smooch delivery and weekly history

```mermaid
sequenceDiagram
    actor A as Sender
    participant PhoneA as Sender phone
    participant API
    participant DB as PostgreSQL
    participant PhoneB as Partner phone
    actor B as Recipient
    A->>PhoneA: Choose one of 9 emoji
    PhoneA->>PhoneA: Queue encrypted send, max 5 / 15 min
    PhoneA->>API: POST emoji + phrase key + operation ID
    API->>DB: Authorize and lock current couple
    API->>DB: Enforce 5 sends in rolling hour; insert once
    API-->>PhoneA: Accepted event + remaining allowance
    API->>DB: Insert short-lived notification event in same transaction
    API-->>PhoneB: Content-free WSS hint while app is foreground
    PhoneB->>API: Fetch pending events for random installation ID
    API-->>PhoneB: Recipient-only authorized event metadata
    PhoneB-->>B: Private notification; generic public lock-screen version
    PhoneB->>API: Acknowledge this installation after Android posts it
    B->>API: GET Monday-Sunday weekly history
    API->>DB: Apply couple home timezone; aggregate both directions
    API-->>B: Current and historical weekly totals
```

Smooch rows survive unpairing in each original participant's private archive and never appear to a later partner. Deleting either participant account permanently erases the relationship's Smooch history.

## Self-hosted partner notifications

```mermaid
sequenceDiagram
    participant Feature as Smooch / note / countdown / quiz transition
    participant DB as PostgreSQL
    participant Hub as API foreground hub
    participant Phone1 as Partner phone 1
    participant Phone2 as Partner phone 2
    Feature->>DB: Insert feature row + short-lived event atomically
    DB->>DB: Create delivery per active enabled installation
    Feature-->>Hub: Commit succeeded; signal recipient account
    Hub-->>Phone1: notification.available (no content)
    loop Every client message or 30 s idle heartbeat
        Phone1->>Hub: Keep foreground subscription open
        Hub->>DB: Recheck exact session, active account, and installation
    end
    Phone1->>Hub: Authenticated pending fetch for installation UUID
    Phone2->>Phone2: WorkManager schedules a background check
    Phone2->>Hub: Authenticated fallback pending fetch
    DB-->>Phone1: Authorized display metadata
    DB-->>Phone2: Same event for independent delivery
    Phone1->>DB: Ack only phone 1 after successful post
    Note over Phone2,DB: Phone 2 stays pending until it posts and acks
```

Installation IDs are random app-generated UUIDs rather than hardware identifiers. Account preferences gate event creation; disabling a category removes its waiting events, while Android runtime permission and notification-channel state gate each phone's post. Delivery backfill uses conflict-safe inserts and ignores the retired account-wide Smooch-consumed marker, so an old client cannot suppress a current installation. Little Orbit uses no Firebase or hosted notification broker and stores no provider-issued address. The foreground socket closes after session expiry or revocation, account suspension or deletion, or installation disablement. Document creation and the first accepted body change inside a 30-minute document/editor window may create a note alert; it is skipped when the partner already has that document open. Countdown metadata excludes notes and private reminder choices; quiz metadata is limited to the UTC date. Preparing a missing daily quiz alert uses an isolated transaction so a pool outage cannot block unrelated pending events. Events are fetchable for 24 hours, retained for at most seven days for bounded recovery, and deleted immediately on unpair; installations unseen for 90 days are purged. The foreground hint hub is process-local, so the current self-hosted deployment runs one API process. Background WorkManager checks are authoritative when the app is not visible, but Android Doze and manufacturer battery policies can delay them beyond the nominal 15-minute interval.

## Email delivery

```mermaid
sequenceDiagram
    participant User
    participant API
    participant DB as PostgreSQL
    participant Worker
    participant SMTP
    User->>API: Signup / resend / forgot password
    API->>DB: Commit capped hashed IP+email counters and cooldown
    API->>DB: Store token hash + expiry + one-use state
    API-->>User: Same neutral response for every email
    API->>DB: Queue template + opaque delivery reference in outbox
    Worker->>DB: Claim due outbox delivery
    Worker->>SMTP: Send provider-neutral message
    SMTP-->>Worker: Accepted or retryable failure
    Worker->>DB: Record redacted delivery outcome
    Worker-->>User: Link carries token in URL fragment
    User->>API: Submit raw token
    API->>DB: Lock account + every reset token; consume complete set if valid
    API->>DB: Replace password + revoke every session in same transaction
```

Email and recovery tokens use URL fragments so browsers do not send them in HTTP request targets or proxy logs. The client submits the token explicitly to the API, where it is hashed. A successful password reset consumes every outstanding link for the account and revokes every active session; a concurrent link cannot survive the account lock. Existing query-string links remain accepted during the transition. Local development uses Mailpit. Production uses configured SMTP and never exposes Mailpit publicly. The worker polls the outbox every 30 seconds by default.

## Android offline and wearable cache

```mermaid
flowchart LR
    UI[Phone UI] --> Room[(Room cache)]
    UI --> Queue[Encrypted ordered mutation queue]
    Queue --> Work[Bounded WorkManager reconnect job]
    Work -->|idempotency key + base revision| API[FastAPI]
    API -->|accepted state| Room
    API -->|stale revision| Conflict[Explicit local/server reconciliation]
    Select[Explicit managed-watch selection] --> Target[Monotonic watch target generation]
    Phone[Phone cache publisher] -->|Relationship + target generations over Wearable Data Layer| Guard[Wear relationship and target guards]
    Target --> Guard
    Purge[Sign-out / unpair / inactive response] -->|Urgent inactive generation| Guard
    Guard -->|Accept current generation| Watch[Wear OS cache]
    Guard -->|Reject non-target, older, or post-purge payload| Drop[Discard]
    Watch -->|24 h without authorization| Delete[Delete display, names, thumbnails, partial files]
    Room --> Sync[Bounded display-cache sync worker]
    Sync --> Render[Unique widget-render worker]
    Render --> Widget[Home-screen widget]
    Widget -->|User refresh| Sync
    Render -->|Cache unavailable| Unavailable[Unavailable state]
    Watch --> Tile[Wear OS tile]
    Watch --> NearbyComplication[Nearby complication]
    Watch --> CountdownComplication[Countdown complication]
    Room -->|age threshold| Stale[Stale-data indicator]
    Watch -->|6 h age threshold| Stale
    Delete --> Unavailable
```

Tokens stay in Android Keystore-backed storage and are never copied to Wear. Offline queues contain encrypted countdown mutations, note drafts, location samples, and at most five unexpired Smooch sends. The watch has its own five-item, 15-minute AES-GCM queue whose operation IDs transfer idempotent ownership to the phone only after target and relationship authorization. An interrupted Our Space editor stores its content and selection in encrypted app storage while Android saved state carries only an opaque workspace key. An exact structured `relationship_inactive` response, sign-out, unpair, or account change clears note workspaces, preview cache, retained media, and transient uploads; an ordinary revision-conflict 409 does not. Widget, tile, and complication caches contain only the confirmed pairing instant, coordinate-free nearby seconds and process time, next countdown, cache-sync time, and opaque local relationship/target generations. The separate Wear launcher profile cache contains only display names and optional server-normalized 128-pixel thumbnails received through the Wearable Data Layer.

The phone advances the relationship generation on sign-out, unpair, account deletion, or `relationship_inactive`. Selecting, switching, or removing a managed watch also advances a separate target generation. The watch handles target and relationship purges before active records, clears old and partial files before a new authority, and rejects records older than either barrier. A non-target watch that observes a newer target generation clears itself. An asynchronous asset checks both current target and relationship authority again before replacing a thumbnail. Fresh values become visibly stale after six hours. At 24 hours without an accepted phone authorization, a best-effort alarm and every passive-surface read delete Wear relationship state and show unavailable. Boot restores the deadline check. The home widget also checks the active phone relationship identity around its Room read and stops rendering data after 24 hours. RC9 coalesces widget rendering through WorkManager so receiver callbacks only enqueue bounded work.

### Watch-originated Smooch ownership

```mermaid
sequenceDiagram
    actor Person
    participant Watch as Selected Wear node
    participant Queue as Encrypted 15-minute queue
    participant Phone as Phone Data Layer service
    participant Outbox as Encrypted phone outbox
    participant API as Authenticated API
    Person->>Watch: Pick approved emoji, then confirm
    Watch->>Queue: Store UUID + emoji + relationship/target generations
    Watch->>Phone: Credential-free idempotent request
    Phone->>Phone: Require selected source node, protocol, current generations, preference, emoji, UUID, and age
    alt accepted
        Phone->>Outbox: Take ownership under same operation ID
        Phone-->>Watch: accepted_queued
        Watch->>Queue: Delete local copy
        Outbox->>API: Send through normal authenticated phone session
    else rejected or expired
        Phone-->>Watch: rejected
        Watch->>Queue: Delete terminal request or let it expire
    end
```

Data Layer transport is not treated as partner delivery. The watch reports only local queued state and the phone acknowledgement. Switching watches, disabling watch Smooches, private removal, relationship purge, or the 15-minute deadline clears the applicable request. Tile and complication surfaces never originate Smooches.

The first valid managed record for an active Wear relationship generation binds the watch to that source phone node. Status and queued actions return only to the bound controller. Requests and acknowledgements from another connected phone are silently rejected, and no rejection discloses whether relationship state exists. Advancing the relationship purge barrier, sign-out, unpairing, or the 24-hour Wear expiry clears the binding before a future generation can bind again.

## Partner-assigned relationship names

```mermaid
sequenceDiagram
    actor Assigner as One active partner
    participant Phone
    participant API
    participant DB as PostgreSQL
    participant Other as Other partner surfaces
    Assigner->>Phone: Enter the name both partners should see
    Phone->>Phone: NFKC + contact/control validation<br/>persist encrypted operation ID + expected revision
    Phone->>API: PUT current partner name
    API->>DB: Authorize active relationship before lookup<br/>lock relationship + apply idempotently
    DB-->>API: New effective name + monotonic name revision
    API-->>Phone: Accepted shared state
    Phone->>Other: Refresh phone, notification, widget, and managed-Wear display cache
    alt stale revision
        API-->>Phone: Conflict without overwrite
        Phone->>API: Refresh authorized profile
    end
    alt unpair / sign-out / relationship inactive
        Phone->>Other: Advance purge generation and clear cached names
        API->>DB: Delete relationship names immediately
    end
```

The caller may name only the other current member; account display identity does not change.
Both members resolve the same result. Mutations carry a stable operation ID and expected
revision, and Android encrypts the one pending operation before network use so an offline retry
or process restart cannot create a second mutation. The API emits only a content-free activity
kind and no partner alert. Big Orbit and AI never receive relationship names.

## Partner-assigned avatar processing and synchronization

```mermaid
sequenceDiagram
    actor Assigner as Partner choosing the image
    participant Phone as Assigner phone
    participant API
    participant DB as PostgreSQL
    participant Subject as Subject phone
    participant Watch as Wear launcher
    Assigner->>Phone: Choose image for partner and approve square crop
    Phone->>API: PUT current relationship partner avatar, max 5 MiB
    API->>DB: Authorize active couple before lookup; reject self-assignment
    API->>API: Decode, orient, strip metadata, crop and bound WebP variants
    API->>DB: Lock couple; atomically replace subject image and revision
    API-->>Phone: Private revision and content hash
    Subject->>API: Authorize current pairing before own assigned image lookup
    API-->>Subject: 128 px WebP with private ETag
    Subject->>Subject: Encrypt both authorized thumbnails in app-private storage
    Subject->>Watch: Authorized names and thumbnails over Wearable Data Layer
    Watch->>Watch: Replace app-private launcher cache
    Note over Phone,Watch: Widget, tile, and complication remain text-only
    Assigner->>API: DELETE partner avatar
    API->>DB: Delete relationship image
    Note over DB: Unpair deletes both avatars; neither transfers or enters archives
```

An unpaired caller never reaches avatar lookup. Replacement and deletion lock the relationship so concurrent first uploads cannot race. Clients compare both revision and content hash, which prevents a deleted then re-added revision from preserving stale bytes. Migration `0016` clears account-owned RC12 photos because converting a self-selected image into a partner-assigned image would misrepresent consent and ownership.

## Self-hosted Wear installation

```mermaid
sequenceDiagram
    actor Person
    participant Phone as Little Orbit phone app
    participant API as Public release API
    participant Embedded as Smoke-only embedded Wear APK
    participant Watch as Wear OS wireless ADB
    Person->>Phone: Settings > Watch settings > Install/update/repair
    alt Production build
        Phone->>API: Fetch current immutable release metadata only
        Person->>Phone: Explicitly continue with APK action
        Phone->>API: Download exact versioned Wear APK
        Phone->>Phone: Verify endpoint, bytes, hash, package, version, watch feature, pinned signer
    else Side-by-side smoke build
        Person->>Phone: Explicitly continue with APK action
        Phone->>Embedded: Copy generated `.smoke` Wear APK after explicit action
        Phone->>Phone: Derive and verify fixed smoke package, size, hash, version, and debug signer
    end
    Phone->>Phone: Track pairing/connect services and port changes with local DNS-SD
    alt discovery unavailable or incomplete
        Person->>Phone: Enter current host, pairing port, and connection port
        Note over Phone: Manual fields stay authoritative until Scan again
    end
    Person->>Phone: Enter the watch's short-lived pairing code
    Phone->>Phone: Copy code into transient request, then clear field
    Phone->>Watch: Pair with reusable phone identity
    Phone->>Watch: Prove authorization with a bounded echo command
    Phone->>Watch: Read watch characteristic, SDK, installed version, security patch
    alt patch before 2026-05-01 or unknown
        Phone-->>Person: Warn, then cancel or explicitly install anyway
    end
    Phone->>Watch: Create package session, write verified APK, and commit with -r
    Watch-->>Person: Little Orbit app, tile, and two complications available
```

The phone checks connected nodes and the `little_orbit_display_v2` capability so Watch settings can distinguish no watch, a missing watch app, and a connected Little Orbit watch. Metadata checks may run in the background; APK download, pairing, installation, reinstall, and removal require an explicit action. The five-stage wizard supports manual addresses when discovery permission is denied, refuses non-watch devices and downgrades, and stores the ADB private key encrypted by Android Keystore. Manual values cannot be overwritten by a late discovery callback; **Scan again** explicitly returns to automatic selection. The pairing-code field disables saved state, autofill, and personalized keyboard learning, clears as soon as installation begins and whenever the screen stops, and never appears in diagnostics. A failed signed-artifact preparation exposes a bounded retry. API 34+ discovery callbacks replace and remove service information continuously; older releases serialize one-shot resolution. Private removal first advances the target purge barrier and clears watch-originated actions, then uninstalls only `com.littleorbit.mobile`, forgets the local ADB key, and tells the person to revoke the phone identity and wireless debugging on the watch. The public website deep-links `/app/install-wear` into this flow and retains a raw Wear APK link for advanced recovery.

The smoke source is build-internal and can target only `com.littleorbit.mobile.smoke`; its APK is generated before the smoke phone is packaged. The production source remains immutable HTTPS metadata plus downloaded bytes and the pinned release certificate. Release and ordinary debug phone artifacts exclude the smoke APK and smoke signing metadata.

## Encrypted backup and non-destructive restore drill

```mermaid
flowchart TD
    Task[Windows scheduled task or typed Big Orbit request] --> Runner[Single-instance host runner]
    Runner --> Pause[Pause API, worker, and media mutations]
    Pause --> PgDump[Dedicated read-only pg_dump role<br/>exclude raw coordinates, health, and raw feedback]
    Pause --> Attach[Stream attachment payload + manifest]
    PgDump --> Age[age encryption<br/>no plaintext host file]
    Attach --> Age
    Age --> Local[Bounded local encrypted files + SHA-256 sidecars]
    Local --> Pair[Atomic pair manifest<br/>exact paths, bytes, and hashes]
    Pair -->|optional verified partial-directory promotion| OffHost[Operator-configured filesystem outside workspace]
    Runner --> Evidence[Content-free backup_runs record]
    Tuesday[Tuesday 07:00 task] --> Pair
    Pair --> Temp[Restore exact paired dump to unique temporary database]
    Temp --> VerifyDB[Verify schema and excluded tables empty]
    Pair --> VerifyArchive[Decrypt exact paired attachment stream into hash/manifest verifier only]
    VerifyDB --> Drop[Force-drop only validated drill database name]
    VerifyArchive --> Evidence
```

The task-registration script is explicit and is never run as part of a build or deployment. The age identity stays outside Git and Docker. A restore drill does not replace live attachment bytes, does not inspect note content, and is recorded as operational evidence rather than a guarantee of full disaster recovery.

## Patch notes and RSS

```mermaid
flowchart LR
    Build[Signed per-module release manifest] --> Publish[Publish immutable APK record]
    Publish --> DB[(PostgreSQL)]
    DB --> History[GET /api/v1/releases/history]
    History --> Notes[/patch-notes]
    History --> RSS[/patch-notes.xml RSS 2.0]
    Fallback[Checked-in latest signed fallback] --> Notes
    Fallback --> RSS
```

Release history contains only public version, checksum, minimum Android, mirror URL, notes, and publication time. Both pages use the checked-in signed-release fallback during an API outage.

## Verified Android phone updates

```mermaid
sequenceDiagram
    actor Person
    participant Phone as Little Orbit phone app
    participant API as Public release API
    participant Files as Read-only release directory
    participant DM as Android DownloadManager
    participant PI as Android PackageInstaller
    Phone->>Phone: First RC10 launch asks whether detection is enabled
    Phone->>API: Enabled or required: metadata check about every 6 h
    API-->>Phone: Immutable version, URLs, size, hashes, floor, optional UTC enforcement
    Phone->>Phone: Validate trusted API path, package, pinned signer, and update policy
    alt optional release
        Phone-->>Person: Prompt once this process; persistent Home banner and App updates destination
    else active compatibility floor excludes installed version
        Phone-->>Person: Update required or exit
    end
    Person->>Phone: Update now
    Phone->>DM: Enqueue versioned Little Orbit API URL
    DM->>API: GET APK, optionally with Range
    API->>Files: Verify exact size and SHA-256
    Files-->>API: Signed immutable APK
    API-->>DM: 200 or 206 with exact length and resume headers
    DM-->>Phone: Android-owned progress / completion
    Phone->>Phone: Verify exact size + SHA-256 + package + newer version + certificate
    alt any verification fails
        Phone->>Phone: Delete APK and offer a clean retry
    else all properties match
        Phone->>PI: Create install session with verified bytes
        PI-->>Person: Android installation approval
        Person->>PI: Approve or cancel
        PI-->>Phone: Installed or retry-safe result
    end
```

The periodic worker fetches metadata only. It cannot download or install an APK. Optional discovery follows the person's opt-in; an active required floor bypasses that preference. Updater state contains the opt-in, last-check time, release ID, phase, byte counts, required flag, and sanitized failure code; it contains no credentials or relationship data. A running or paused transfer with no progress for five minutes becomes a retryable stalled state. Published release records cannot be edited or unpublished.

```mermaid
flowchart LR
    Request[Android HTTP or note WSS request] --> Mobile{Mobile protocol path?}
    Mobile -->|no| Continue[Continue normal routing]
    Mobile -->|yes| Floor{Published floor has reached its UTC required-after time?}
    Floor -->|no| Continue
    Floor -->|yes| Version{Explicit Android version header meets floor?}
    Version -->|yes| Continue
    Version -->|no HTTP| Upgrade[426 client_update_required]
    Version -->|no WSS| Close[Close 4426 before authentication]
```

The compatibility gate runs before authentication and protected resource lookup, so its response cannot disclose account or relationship state. Routine publications leave `required_after` empty and remain optional.
