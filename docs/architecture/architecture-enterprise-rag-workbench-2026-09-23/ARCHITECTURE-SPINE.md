---
name: Enterprise RAG Workbench
type: architecture-spine
purpose: build-substrate
altitude: initiative
paradigm: modular monolith with hexagonal boundaries
scope: Stage A local demo workbench and stable seams for later real RAG integration
status: final
created: 2026-09-23
updated: 2026-09-24
binds: [Stage A, Epic 1, Epic 2, Epic 3, Epic 4]
sources:
  - ../../../../outputs/BMAD-企业知识库RAG项目方案.md
  - SOLUTION-DESIGN.md
companions: [SOLUTION-DESIGN.md]
---

# Architecture Spine — Enterprise RAG Workbench

## Design Paradigm

Use a modular monolith with hexagonal boundaries. The web client consumes only the versioned HTTP/SSE contract. API routes call application use cases; use cases coordinate domain rules through ports; mock, persistence, and file adapters implement those ports.

~~~mermaid
flowchart LR
  Browser[Vue web client] -->|REST and SSE /api/v1| API[FastAPI routes]
  API --> UseCases[Application use cases]
  UseCases --> Domain[Domain models and rules]
  UseCases --> Ports[Outbound ports]
  Ports --> Mock[Fixture-backed mock adapters]
  Ports --> Repositories[Repository adapters]
  Repositories --> DB[(SQLite local or PostgreSQL Compose)]
  Ports --> Files[Local file adapter]
~~~

## Invariants & Rules

### AD-1 — Keep one deployable application with inward dependencies

- **Binds:** all Stage A web, API, domain, and adapter modules
- **Prevents:** pages, API routes, and providers implementing conflicting business rules or depending directly on vendor SDKs
- **Rule:** API routes call application use cases only. Use cases depend on domain types and declared ports. Domain modules do not import FastAPI, database libraries, model SDKs, or frontend code. Adapters implement ports and are selected at the composition root.

### AD-2 — The backend contract is the only shared API contract

- **Binds:** knowledge-base, document, chunk, retrieval, chat, provider, and run capabilities
- **Prevents:** frontend mock shapes and backend responses drifting, or provider details leaking into page code
- **Rule:** FastAPI Pydantic DTOs under /api/v1 define the contract and generate OpenAPI. One shared DTO vocabulary, lower-snake enum values, camelCase JSON aliases (including the `Id` suffix rule), ISO-8601 UTC timestamps, and explicit null/omission semantics apply to every endpoint. Frontend types are generated into `apps/web/src/api/generated/` by pinned `@hey-api/openapi-ts` 0.99.0 with its TypeScript-only plugin; a contract check regenerates them and fails on drift. All API errors use the shared catalog and problem shape in SOLUTION-DESIGN.md.

### AD-3 — Source hierarchy and evidence identity are canonical

- **Binds:** document management, Chunk observation, retrieval, citations, and run detail
- **Prevents:** chunks or citations that cannot be traced to their source document
- **Rule:** the hierarchy is KnowledgeBase → Document → immutable DocumentRevision → Section → Chunk. Every Evidence and Citation references an existing `revision_id` and Chunk ID; every Chunk references one Section; every Section references one revision. Reprocessing creates a new revision and never mutates the source identity used by historical runs. Page and heading-path metadata travel with the source record.

### AD-4 — Provider mode is explicit in every result

- **Binds:** fixture-backed parsing, retrieval, answer, and provider-status flows
- **Prevents:** a demo answer, score, or processing state being mistaken for a real RAG result
- **Rule:** every provider result carries mode with value mock or live. Stage A emits mock only. UI views that render evidence or answers show the mode beside the result. Live mode cannot be selected unless a live adapter is configured server-side.

### AD-5 — A run owns its ordered, safe event stream

- **Binds:** upload progress, retrieval debug, streamed chat, and run inspection
- **Prevents:** UI timelines disagreeing with persisted run history or exposing private model reasoning
- **Rule:** each run has one `run_id`; Run transitions are queued → running → completed|failed, with queued → failed also allowed when work cannot start; completed/failed are terminal. A repository append atomically allocates a per-run sequence and commits an allowlisted event payload under a unique `(run_id, sequence)` key. Publish only committed rows. The run-detail cursor and SSE `Last-Event-ID` both resume strictly after that sequence; reconnect replays persisted rows before tailing. Event payloads expose bounded phase summaries, answer deltas, and source references only—never secrets, stack traces, raw exception text, or private reasoning.

### AD-6 — Metadata and file bytes have separate owners

- **Binds:** uploads, document records, database deployment, and future object storage
- **Prevents:** database rows containing unbounded document blobs or provider-specific storage paths leaking into the domain
- **Rule:** repositories own relational metadata and run records. A FileStore port owns uploaded bytes. Stage A uses a local mounted directory and generated opaque storage keys. Uploads stage bytes and metadata, atomically finalize the file on the same volume, and reconcile unfinished records after restart. A pending upload may appear in list/detail as `upload_pending` but is not retrievable; it becomes `uploaded_unprocessed` only after finalization, or `upload_failed` when recovery cannot complete. User uploads are never indexed in Stage A; only read-only, stable-ID fixtures contain parsed Sections/Chunks. Stage B may add an object-store adapter without changing the Document contract.

### AD-7 — Stage A has no external RAG infrastructure dependency

- **Binds:** local start, demo fixtures, upload simulation, retrieval debug, and chat
- **Prevents:** Redis, Milvus, OCR, external model credentials, or production job infrastructure blocking the first workflow
- **Rule:** Stage A uses a single immutable `mock` adapter profile selected and validated at startup. Fixture-backed `KnowledgeRetriever`, `AnswerProvider`, and `ProviderStatus` adapters power the demo; LangGraph is the required deterministic chat-flow orchestrator. User uploads are stored as unprocessed files and never receive fixture Sections/Chunks. No vector database, OCR engine, external LLM call, or browser-held secret is required. Stable Stage B ports are `DocumentParser`, `OCRProvider`, `Chunker`, `EmbeddingProvider`, `VectorStore`, `KeywordRetriever`, `KnowledgeRetriever`, and `AnswerProvider`; their ownership and flow are defined in SOLUTION-DESIGN.md.

### AD-8 — Deployment targets preserve one repository contract

- **Binds:** local development and documented Compose deployment
- **Prevents:** local-only persistence rules diverging from the deployment data model
- **Rule:** local SQLite and Compose PostgreSQL use the same SQLAlchemy repositories and Alembic revision history. Alembic is the sole schema authority: local startup requires the explicit upgrade command; Compose has one migration service that must succeed before API readiness. No ORM `create_all()` startup path is permitted. SQLite enables foreign keys on every connection and both backends enforce the same parent ownership and uniqueness rules. Stage A avoids database-specific SQL and cyclic foreign keys. Browser API base URL and CORS origins are explicit for local and Compose modes; Stage A Compose is a local demo deployment, not a production topology.

## Consistency Conventions

| Concern | Convention |
| --- | --- |
| Naming | Python modules and fields use snake_case; TypeScript uses camelCase; JSON fields are camelCase generated from the API schema; entity IDs are opaque UUID strings. |
| Time and events | Persist UTC ISO 8601 timestamps; run events sort by a transactionally allocated integer sequence, never by client clock. |
| API and errors | Prefix `/api/v1`; nullable fields serialize as `null`, non-applicable optional fields are omitted, and enum values are lower_snake_case. Both documents define Problem as `type, title, status, detail, code, requestId, retryable, runId`; `runId` is required and nullable. Every response carries `X-Request-ID`; Problem JSON also has `requestId` (internal Python attribute `request_id`). Never return stack traces. |
| Demo data | Fixtures use stable `fixture_*` IDs and read-only source data. Seeding is idempotent and cannot overwrite user records. Writes create user-owned IDs; no API mutates a fixture. Every provider result includes `mode=mock`. |
| Secrets | Provider credentials remain server-side; no secret is returned by Provider Status or bundled in the web build. |
| Run visibility | Every upload, retrieval, or answer operation links to `run_id`; the run page reads the persisted event sequence and can resume from `Last-Event-ID`. |

## Stack

| Name | Version |
| --- | --- |
| Python | 3.13.15 (LangGraph upstream classifier-compatible line) |
| FastAPI | 0.141.1 |
| Pydantic | 2.13.5 |
| SQLAlchemy | 2.0.54 |
| Alembic | 1.20.0 |
| LangGraph | 1.2.12 |
| Vue | 3.5.43 stable |
| TypeScript | 6.0.3 (Vue/Volar stable API line) |
| Vite | 8.3.0 |
| Node.js | 24.21.0 LTS |
| @hey-api/openapi-ts | 0.99.0 (TypeScript-only plugin) |
| PostgreSQL | 18.6 |
| psycopg[binary] | 3.3.6 (`postgresql+psycopg://`) |
| SQLite | Runtime-provided; detect and report actual version, do not pin independently |

## Structural Seed

~~~mermaid
flowchart TB
  subgraph Compose[Compose deployment]
    Web[Vue demo web app]
    API[FastAPI process]
    Migrate[One-shot Alembic migration]
    PG[(PostgreSQL 18.6)]
    Uploads[(Mounted uploads volume)]
    Web -->|REST and SSE; explicit browser URL and CORS| API
    Migrate --> PG
    API -->|starts after successful migration| Migrate
    API --> PG
    API --> Uploads
  end
  Local[No-Docker local mode] -->|REST and SSE| API2[FastAPI process]
  API2 --> SQLite[(SQLite file)]
  API2 --> LocalFiles[(Local uploads directory)]
~~~

~~~text
work/
  apps/
    api/src/rag_workbench/
      api/          # HTTP and SSE transport
      application/ # use cases and run coordination
      domain/      # canonical entities, immutable revisions, evidence
      ports/       # repository, FileStore, parser/OCR/chunker/embed/vector/keyword/retriever/answer interfaces
      adapters/    # SQLAlchemy, local files, fixture mocks
      fixtures/    # explicit demo-only data
    web/src/
      pages/       # seven workbench routes
      components/  # shared shell, tables, status, citations
      api/         # generated types and API client
  docs/api/        # OpenAPI and SSE examples
  data/uploads/    # ignored local user files
  docker-compose.yml
~~~

## Capability → Architecture Map

| Capability / Area | Lives in | Governed by |
| --- | --- | --- |
| Knowledge-base and document list | web pages; API use cases; repositories | AD-1, AD-2, AD-6 |
| Upload and file state | upload route; FileStore; upload Run; startup reconciliation | AD-3, AD-5, AD-6, AD-7 |
| Section and Chunk observation | document/chunk queries and pages | AD-2, AD-3, AD-4 |
| Retrieval debug | retrieval use case and KnowledgeRetriever port | AD-1, AD-2, AD-4, AD-5 |
| Agent answer and citations | LangGraph flow, AnswerProvider port, chat page | AD-1, AD-3, AD-4, AD-5 |
| Run trace | Run repository, event stream, run page | AD-2, AD-5 |
| Provider status | server-side adapter registry and status page | AD-1, AD-4, AD-7 |
| Local and Compose operation | app configuration, SQL repositories, FileStore | AD-6, AD-7, AD-8 |

## Deferred

- Real file parsing, OCR, and layout-aware extraction; revisit when the first real corpus is available.
- Real Parser/OCR, Chunker, Embedding, VectorStore and KeywordRetriever adapters; BM25/RRF, reranking, and Milvus versus pgvector; decide before Stage B based on corpus size, Chinese retrieval needs, operations, and evaluation. These implementations replace stable ports rather than changing the API contract.
- Stage B quality evaluation: at least 30 gold questions, Recall@5, citation validity and no-answer detection; calibrate the suggested ≥0.80 Recall@5 against a representative corpus. Stage A makes no retrieval-quality claim.
- Durable asynchronous workers and restart-safe retries; revisit when ingestion outlives a request or needs parallel workers.
- Authentication, multi-user access, tenant isolation, and permission inheritance; revisit before any shared deployment.
- Cloud object storage and production observability; revisit before external deployment.
- LangGraph checkpoint persistence; add only when resumable or human-interruptible runs are required.
