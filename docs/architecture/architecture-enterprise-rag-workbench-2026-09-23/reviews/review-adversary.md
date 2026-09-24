# Adversarial Architecture Review

**Verdict:** The spine sets useful boundaries, but it is not yet precise enough to keep independently built capabilities behaviorally compatible. The pairs below can follow all eight ADs and still produce user-visible divergence or data-integrity failures.

## Findings

### 1. Shared DTO vocabulary is not pinned

- **Location:** AD-2; Consistency Conventions
- **Trigger condition:** Two capability teams define endpoint-local schemas for the same concepts (for example, document state, run state, or pagination), choosing different enum values or absent/empty/null semantics. Both schemas are Pydantic-generated, versioned under `/api/v1`, and generate the frontend types, so both comply with AD-2 while the UI must special-case each endpoint.
- **Guard snippet:** Publish canonical shared DTOs and enum tables for KnowledgeBase, Document, Section, Chunk, Run, ProviderResult, pagination, and empty/null behavior; require every endpoint to reference them and check in or deterministically regenerate one OpenAPI snapshot.
- **Potential consequence:** Lists, detail pages, and run views interpret equivalent states differently, and adding a new endpoint silently creates a second dialect.

### 2. Camel-case JSON generation and serialization are underspecified

- **Location:** AD-2; Consistency Conventions, Naming
- **Trigger condition:** One Pydantic model uses explicit aliases and serializes with aliases, while another relies on FastAPI/Pydantic defaults or a different acronym rule. Both produce OpenAPI and TypeScript types, but a payload field such as `knowledge_base_id` can surface as `knowledgeBaseId`, `knowledgebaseId`, or snake_case at runtime.
- **Guard snippet:** Specify one shared alias generator and acronym policy, require request validation and response serialization by alias, and generate the OpenAPI schema from those exact runtime settings.
- **Potential consequence:** Generated frontend types compile while actual request or response bodies use different property names, breaking filters, forms, or citations at runtime.

### 3. Document revisions and chunk identity have no lifecycle rule

- **Location:** AD-3
- **Trigger condition:** On reprocessing, one implementation replaces a document's sections and chunks while another appends a new set. Both preserve the stated hierarchy and ensure currently stored citations reference existing chunks, but old run events can point at deleted chunks in one implementation and remain resolvable in the other.
- **Guard snippet:** Define document revision identity and reprocessing semantics: whether prior sections/chunks are retained, how current-version reads select them, and how historical evidence/citations resolve. Replace a revision atomically or version every reference.
- **Potential consequence:** The same run detail can show missing evidence, stale evidence, or a different citation after a document is reprocessed.

### 4. Fixture ownership and user-write precedence are ambiguous

- **Location:** AD-1; Consistency Conventions, Demo data
- **Trigger condition:** One team loads fixtures into repository tables and overlays writes; another serves immutable fixtures through a separate adapter and merges user records at query time. Both leave source fixtures unchanged and allow record writes, but may return different records, ordering, or values after an update to a fixture-backed document.
- **Guard snippet:** Declare fixtures read-only inputs with stable IDs, define whether writes to fixture IDs are rejected or stored as explicit user overrides, specify merge precedence and ordering, and make seeding/reset idempotent.
- **Potential consequence:** A document edited in one capability reverts or appears unchanged in another, and fixture IDs collide with user-created records or between database resets.

### 5. FileStore and metadata writes have no failure protocol

- **Location:** AD-6; Capability → Architecture Map, Upload and processing state
- **Trigger condition:** One upload use case writes bytes before inserting metadata; another commits metadata before writing bytes. Both assign opaque storage keys and keep bytes outside the database. A disk-full error or process exit between steps leaves an orphaned file in the first design or a document row that cannot be downloaded in the second.
- **Guard snippet:** Specify upload/delete ordering and compensation: reserve a pending metadata record, write to a temporary key, atomically finalize bytes and metadata, and clean up or reconcile incomplete records on startup. Define the corresponding failure state in the run.
- **Potential consequence:** Users see completed documents with missing files, inaccessible document rows, or unbounded orphaned uploads.

### 6. Upload retries can create different numbers of documents and runs

- **Location:** AD-2; AD-5; AD-7
- **Trigger condition:** After a client timeout, one implementation treats a repeated POST as a new upload while another deduplicates by filename or content hash. Both expose an in-process mock processing flow with the required states, but filename/hash deduplication can also merge two intentional uploads.
- **Guard snippet:** Define an upload idempotency key and its retention/scope, state whether same bytes under a new key create a new document, and return the original document/run on a replay of the same key.
- **Potential consequence:** Retries create duplicate documents and event histories, or intentional uploads are unexpectedly collapsed.

### 7. Upload state names lack transition and completion semantics

- **Location:** AD-5; AD-7
- **Trigger condition:** One flow emits `complete` after parsing; another emits it after persistence and chunk creation. One allows `queued → failed`; another exposes `processing → failed` only. Both show queued/processing/complete/failed and run in-process.
- **Guard snippet:** Define a single state machine, legal transitions, terminal-state rules, and the exact operation that makes upload complete. Define startup handling for runs left queued or processing after a process restart, even if Stage A does not retry work.
- **Potential consequence:** The UI can advertise a searchable document before chunks exist, show inconsistent progress, or wait forever on a state that another implementation considers terminal.

### 8. Event sequence allocation and persistence are not atomic

- **Location:** AD-5; Consistency Conventions, Time and events
- **Trigger condition:** Two handlers append to the same run concurrently or a publisher retries after a timeout. One repository allocates `MAX(sequence)+1` without a lock; another serializes appends. Both persist before publishing and use integer sequences, but the first can publish duplicate or out-of-order sequence numbers.
- **Guard snippet:** Make append a repository operation that atomically allocates a unique per-run sequence and commits the event; define idempotent append/retry behavior and require publication to use the committed record.
- **Potential consequence:** Run-detail and SSE consumers disagree on order, skip an event, or display duplicate progress.

### 9. SSE replay and reconnect behavior have no cursor contract

- **Location:** AD-5; Capability → Architecture Map, Run trace
- **Trigger condition:** One SSE endpoint sends only events created after connection; another replays all run events before tailing. Both can claim to replay the same persisted records, but a reconnecting browser may miss events, receive duplicates, or have no way to resume after its last event.
- **Guard snippet:** Specify the stream URL, event ID format, `Last-Event-ID` behavior, initial replay boundary, ordering, duplicate tolerance, and how a client obtains a consistent snapshot before subscribing. Keep run-detail and SSE pagination on the same cursor semantics.
- **Potential consequence:** Refreshing or reconnecting to a run yields an incomplete or duplicated timeline, and answer deltas can disappear or be appended twice.

### 10. Problem shape is fixed, but error meaning is not

- **Location:** AD-2; Consistency Conventions, API and errors
- **Trigger condition:** Separate routes return the same problem fields but assign different codes or HTTP statuses to the same condition (for example, missing document as 404 vs 410, or invalid transition as 400 vs 409). Each code is locally stable, so each route complies with the written rule.
- **Guard snippet:** Add a shared error catalog mapping domain failures to exact stable codes, HTTP statuses, titles, and retryability; define validation-error and unexpected-error mapping plus request_id propagation.
- **Potential consequence:** The frontend cannot handle errors consistently, retries a permanent failure, or treats a recoverable state conflict as a missing resource.

### 11. Adapter selection is not a single validated runtime profile

- **Location:** AD-1; AD-4; AD-7; Provider status
- **Trigger condition:** One composition root selects one adapter bundle at startup; another resolves parser, retriever, answer, and status adapters independently or from different environment variables. Both use deterministic fixtures and emit `mode=mock` in Stage A, yet Provider Status may describe a different registration from the adapter actually serving a request.
- **Guard snippet:** Define one immutable Stage A adapter profile resolved and validated at startup, pass that registry to every use case and status endpoint, and fail startup on unknown or disallowed mode settings. Define exactly which composite results carry mode.
- **Potential consequence:** A displayed provider status does not describe the behavior behind the result; future adapter additions can accidentally create mixed-mode answers while reporting a single mode.

### 12. SQLite may not enforce the source hierarchy that PostgreSQL enforces

- **Location:** AD-3; AD-8
- **Trigger condition:** Both databases use the same SQLAlchemy models and migrations with foreign-key declarations, but SQLite connections do not enable foreign-key enforcement. PostgreSQL rejects a chunk that references a missing section while local SQLite accepts it.
- **Guard snippet:** Require `PRAGMA foreign_keys=ON` on every SQLite connection, specify identical cascade/restrict behavior in migrations, and verify the hierarchy constraints on both supported dialects.
- **Potential consequence:** Local demo data can contain untraceable chunks or citations that fail only after deployment to Compose PostgreSQL.

### 13. Browser-to-API routing is not specified for either deployment

- **Location:** AD-2; AD-8; Structural Seed
- **Trigger condition:** One Compose setup serves the Vue app and proxies `/api/v1` and SSE to FastAPI on the same origin; another serves static assets separately and expects a baked API base URL plus CORS configuration. Both use the versioned contract, but no shared rule selects the URL or ensures SSE is streamed without buffering.
- **Guard snippet:** Specify the browser-visible API base URL for local and Compose modes, proxy/CORS requirements, and SSE proxy buffering/timeout settings; use the same configuration mechanism in generated web builds.
- **Potential consequence:** One deployment's API requests fail due to wrong origin or CORS, or SSE progress appears only after completion because an intermediary buffers events.

### 14. Compose migration and dependency readiness ownership is missing

- **Location:** AD-8; Structural Seed
- **Trigger condition:** One deployment applies migrations in a one-shot job after PostgreSQL is healthy; another runs migrations from every API process at startup. Both use the same repositories and versioned migrations, but neither startup order nor migration ownership is fixed.
- **Guard snippet:** Define a single migration owner and Compose dependency health checks, gate API readiness on the expected schema revision, and specify persistent volume locations/permissions for PostgreSQL and uploads.
- **Potential consequence:** Parallel API startup races on migrations, an API serves against an old schema, or uploaded files disappear after a container recreation despite the mounted-volume intent.

