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
    Worker[Worker] --> DB
    Worker --> AI[AI adapter]
    AI --> Ollama[Ollama<br/>no published port]
    Ollama -. model install only .-> Registry[Ollama model registry]
    Worker --> SMTP[SMTP adapter]

    Untrusted[Other LAN peer] -. spoofed X-Forwarded-For .-> Gateway
    Gateway -. ignore forwarded headers .-> Untrusted
```

Only gateway port 8180 is published by Compose. Windows Firewall allows that production port only from `192.168.50.6`. The address `192.168.50.182` needs a DHCP reservation before production use.

Caddy trusts incoming `X-Forwarded-For` only when its immediate peer is `192.168.50.6`. It overwrites a private `X-Little-Orbit-Client-IP` header before proxying to FastAPI. FastAPI validates that value as one IP address and does not enable Uvicorn's generic proxy-header trust.

## Authentication and pairing

```mermaid
sequenceDiagram
    actor A as Creator
    actor B as Partner
    participant API
    participant DB as PostgreSQL
    A->>API: Register + 18+/terms + honeypot
    API->>DB: Store Argon2id hash + hashed verification token
    API-->>A: Neutral response; email verification link
    A->>API: Consume verification token once
    A->>API: Create pair code
    API->>DB: Store hashed 8-char code, expires +10m
    B->>API: Redeem code
    API->>DB: Lock code; verify B and capacity; mark pending
    API-->>A: Ask creator to confirm B
    A->>API: Confirm pending partner
    API->>DB: One transaction: consume code + create two-member couple
    API-->>A: Return shared paired state
    API-->>B: Pairing becomes visible on the next authenticated refresh
```

Public registration, resend, and recovery responses are identical for known and unknown emails. Rate limits apply to IP and normalized email keys.

## Live notes

```mermaid
sequenceDiagram
    participant A as Partner A
    participant API
    participant DB as PostgreSQL
    participant B as Partner B
    A->>API: WSS authenticate + subscribe(note_id)
    API->>DB: Authorize actor before note lookup
    API-->>A: Snapshot(revision N)
    A->>API: Operation(op_id, base N, insert/delete)
    API->>DB: Lock note; dedupe op_id; transform; append revision N+1
    API-->>A: Ack(op_id, revision N+1)
    API-->>B: Applied operation(revision N+1)
    Note over A,B: Out-of-order or duplicate operations are idempotent
    A--xAPI: Disconnect
    Note over A: Preserve draft and base revision
    A->>API: Reconnect with base revision
    API-->>A: Operations or conflict snapshot
    Note over A: If revisions diverge beyond safe transform, show both versions
```

## Daily AI generation

```mermaid
flowchart LR
    Schedule[Daily scheduler] --> Dates[Find gaps for today + 7 future UTC dates]
    Dates --> Prompt[Versioned prompt<br/>no couple data]
    Prompt --> Ollama[Qwen3 4B in Ollama]
    Ollama --> Parse[Strict v2 JSON parse<br/>exactly 10 candidates]
    Parse --> Validate{Schema + safety + answerability}
    Validate -->|reject| Quarantine[Quarantine with reasons]
    Validate -->|accept| Dedupe{Exact hash + trigram + repetition}
    Dedupe -->|duplicate| Quarantine
    Dedupe -->|unique| Pool[Candidate pool]
    Pool --> Select[Balance tone, type, and category<br/>select 5 general + intimacy alternatives]
    Bank[Curated bank] -->|timeout, OOM, shortage| Select
    Select --> Publish[Publish date pool]
    Publish --> Audit[Model digest, prompt version, parameters, validation, fallback]
```

Invalid model output is quarantined rather than repaired. A 180-question curated bank guarantees five general questions plus a consent-gated intimacy alternative for today and seven future dates while the model is unavailable.

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
    API->>DB: Mark A finished; keep reveal closed
    B->>API: Save all five drafts + finish
    API->>DB: Lock both member rows; set one revealed_at timestamp
    API-->>B: Both complete; include both answer sets
    A->>API: Poll content-free status through WorkManager
    API-->>A: revealed=true; no answer content in notification response
    A->>API: GET day
    API-->>A: Side-by-side shared reveal
```

A person may reopen and edit a finished set only before the shared reveal. Past incomplete days remain editable for seven days and remain visible for 30. Custom questions take the next available UTC slot, up to all five questions, and surprise content is hidden from the other partner until its day arrives. Non-surprise custom questions appear in both partners' pending queue. Intimacy-tagged custom or global questions require both partners' current consent. If either person opts out, every unrevealed intimacy prompt is replaced atomically, its drafts are cleared, and both people review the safe replacement before finishing again.

## Relationship start-date agreement

```mermaid
sequenceDiagram
    actor A as Proposer
    actor B as Partner
    participant API
    participant DB as PostgreSQL
    A->>API: Propose date + operation ID
    API->>DB: Authorize member; lock couple and pending proposal
    API->>DB: Replace A's earlier proposal; expire after 7 days
    API-->>A: Pending proposal
    B->>API: Accept or decline + operation ID
    API->>DB: Authorize member; lock current proposal
    alt accepted and still current
        API->>DB: Store shared start date atomically
        API-->>A: Relationship age updates on refresh
        API-->>B: Relationship age updates on refresh
    else stale, expired, reused, or wrong role
        API-->>B: 409; refresh current state
    end
```

Only the proposer may cancel. Only the other partner may accept or decline. Operation IDs return the original response after a safe retry, and the database permits only one pending proposal per couple.

## Together-time processing

```mermaid
flowchart TD
    Consent[Both users enable sharing] --> Samples[Clients queue bounded samples<br/>ID, UTC time, accuracy, coordinate]
    Samples --> Upload[Authenticated idempotent batch]
    Upload --> Checks{Authorized, consent current,<br/>within time/accuracy bounds, unique}
    Checks -->|reject| Audit[Privacy-safe rejection event]
    Checks -->|accept| Match[Deterministic one-to-one match<br/>within 10 minutes]
    Match --> Threshold{Two consecutive confident pairs<br/>within 100 m and at most 20 min apart?}
    Threshold -->|yes| Bucket[Replace rolling uncorrected<br/>UTC-minute estimates]
    Threshold -->|no| Skip[Do not count the interval]
    Bucket --> Estimate[Update aggregate estimate + last-updated]
    Skip --> Estimate
    Estimate --> Cache[Minimal widget/watch cache]
    Samples --> Expiry[Delete raw coordinates within 24 h]
    OptOut[Either partner opts out] --> Delete[Delete both partners' raw coordinates]
    Delete --> Stop[Reject future uploads until mutual consent]
    Correction[User correction] --> CorrectionAudit[Append audited correction]
    CorrectionAudit --> Estimate
```

## Email delivery

```mermaid
sequenceDiagram
    participant User
    participant API
    participant DB as PostgreSQL
    participant Worker
    participant SMTP
    User->>API: Signup / resend / forgot password
    API->>DB: Apply IP+email limit and cooldown
    API->>DB: Store token hash + expiry + one-use state
    API-->>User: Same neutral response for every email
    API->>DB: Queue template + opaque delivery reference in outbox
    Worker->>DB: Claim due outbox delivery
    Worker->>SMTP: Send provider-neutral message
    SMTP-->>Worker: Accepted or retryable failure
    Worker->>DB: Record redacted delivery outcome
    Worker-->>User: Link carries token in URL fragment
    User->>API: Submit raw token
    API->>DB: Hash and consume atomically if valid
```

Email and recovery tokens use URL fragments so browsers do not send them in HTTP request targets or proxy logs. The client submits the token explicitly to the API, where it is hashed and consumed once. Existing query-string links remain accepted during the transition. Local development uses Mailpit. Production uses configured SMTP and never exposes Mailpit publicly. The worker polls the outbox every 30 seconds by default.

## Android offline and wearable cache

```mermaid
flowchart LR
    UI[Phone UI] --> Room[(Room cache)]
    UI --> Queue[Encrypted ordered mutation queue]
    Queue --> Work[Bounded WorkManager reconnect job]
    Work -->|idempotency key + base revision| API[FastAPI]
    API -->|accepted state| Room
    API -->|stale revision| Conflict[Explicit local/server reconciliation]
    Phone[Phone cache publisher] -->|Versioned Wearable Data Layer| Watch[Wear OS cache]
    Room --> Widget[Home-screen widget]
    Watch --> Tile[Wear OS tile]
    Watch --> Complication[Watch-face complication]
    Room -->|age threshold| Stale[Stale-data indicator]
    Watch -->|age threshold| Stale
```

Tokens stay in Android Keystore-backed storage. The offline queue contains encrypted countdown mutations. Widget and watch caches contain only the accepted relationship start date, coordinate-free nearby seconds and process time, next countdown, and cache-sync time. RC6 publishes the v2 cache plus the legacy v1 path for one release so an older watch fails stale rather than displaying a new value with the wrong meaning.

## Self-hosted Wear installation

```mermaid
sequenceDiagram
    actor Person
    participant Guide as /download#wear
    participant Script as Signed installer script
    participant API as Public release API
    participant Watch as Wear OS wireless ADB
    Person->>Guide: Choose Install on Wear OS
    Guide-->>Person: Explain wireless-debugging steps
    Person->>Script: Enter watch pairing and connection addresses
    Script->>API: Fetch current immutable release metadata
    Script->>API: Download versioned Wear APK
    Script->>Script: Verify endpoint, bytes, hash, package, version, signer
    Script->>Watch: Pair, verify watch characteristic, install -r
    Watch-->>Person: Little Orbit app, tile, and complication available
```

The phone checks connected nodes and the `little_orbit_display_v2` capability so More can distinguish no watch, a missing watch app, and a connected Little Orbit watch. Platform security prevents the phone app from silently sideloading a self-hosted APK.

## Verified Android phone updates

```mermaid
sequenceDiagram
    actor Person
    participant Phone as Little Orbit phone app
    participant API as Public release API
    participant Files as Read-only release directory
    participant DM as Android DownloadManager
    participant PI as Android PackageInstaller
    Phone->>API: GET /api/v1/releases/current
    API-->>Phone: Immutable version, URLs, size, hashes, floor, optional UTC enforcement
    Phone->>Phone: Validate trusted API path, package, pinned signer, and update policy
    alt optional release
        Phone-->>Person: Update now or defer 24 hours
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

The daily worker fetches metadata only. It cannot download or install an APK. Updater state contains a release ID, phase, byte counts, required flag, and sanitized failure code; it contains no credentials or relationship data. Published release records cannot be edited or unpublished.

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
