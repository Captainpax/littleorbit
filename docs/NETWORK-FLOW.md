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
    Schedule[Daily scheduler] --> Dates[Find gaps in next 7 UTC calendar dates]
    Dates --> Prompt[Versioned prompt<br/>no couple data]
    Prompt --> Ollama[Qwen3 4B in Ollama]
    Ollama --> Parse[Strict JSON parse]
    Parse --> Validate{Schema + safety + answerability}
    Validate -->|reject| Quarantine[Quarantine with reasons]
    Validate -->|accept| Dedupe{Exact hash + trigram + repetition}
    Dedupe -->|duplicate| Quarantine
    Dedupe -->|unique| Pool[Candidate pool]
    Pool --> Select[Select 5 general + intimacy alternatives]
    Bank[Curated bank] -->|timeout, OOM, shortage| Select
    Select --> Publish[Publish date pool]
    Publish --> Audit[Model digest, prompt version, parameters, validation, fallback]
```

Invalid model output is quarantined rather than repaired. Curated fallback guarantees five general questions for each of the next seven dates.

## Together-time processing

```mermaid
flowchart TD
    Consent[Both users enable sharing] --> Samples[Clients queue bounded samples<br/>ID, UTC time, accuracy, coordinate]
    Samples --> Upload[Authenticated idempotent batch]
    Upload --> Checks{Authorized, consent current,<br/>within time/accuracy bounds, unique}
    Checks -->|reject| Audit[Privacy-safe rejection event]
    Checks -->|accept| Match[Accuracy-aware proximity match]
    Match --> Threshold{Within configured 100 m?}
    Threshold -->|yes| Bucket[Insert one unique couple/minute bucket]
    Threshold -->|no| Skip[Do not count the minute]
    Bucket --> Estimate[Update aggregate estimate + last-updated]
    Skip --> Estimate
    Estimate --> Cache[Minimal widget/watch cache]
    Samples --> Expiry[Delete raw coordinates within 24 h]
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
    User->>API: Submit raw token
    API->>DB: Hash and consume atomically if valid
```

Local development uses Mailpit. Production uses configured SMTP and never exposes Mailpit publicly.

## Android offline and wearable cache

```mermaid
flowchart LR
    UI[Phone UI] --> Room[(Room cache)]
    UI --> Queue[Encrypted ordered mutation queue]
    Queue --> Work[Bounded WorkManager reconnect job]
    Work -->|idempotency key + base revision| API[FastAPI]
    API -->|accepted state| Room
    API -->|stale revision| Conflict[Explicit local/server reconciliation]
    Phone[Phone cache publisher] -->|Wearable Data Layer| Watch[Wear OS cache]
    Room --> Widget[Home-screen widget]
    Watch --> Tile[Wear OS tile]
    Watch --> Complication[Watch-face complication]
    Room -->|age threshold| Stale[Stale-data indicator]
    Watch -->|age threshold| Stale
```

Tokens stay in Android Keystore-backed storage. The offline queue contains encrypted countdown mutations, while widgets and watch surfaces receive only the minimal cached together-time and next-countdown values they render.
